import uuid
import asyncio
import pytest
import uvicorn
import threading
import time

from config import settings
from database.session import init_db, async_session_factory
from database import crud
from security.encryption import decrypt_password
from schemas.automation import SignupInput
from services.job_registry import job_registry, ActiveJob
from services.orchestrator import run_orchestrated_workflow
from tests.mock_site.mock_app import app as mock_server_app

@pytest.fixture(scope="module")
def mock_server():
    """Start local mock server on port 8001 in a background daemon thread."""
    config = uvicorn.Config(mock_server_app, host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    time.sleep(1)
    yield
    server.should_exit = True

@pytest.mark.asyncio
async def test_full_mock_orchestration_flow(mock_server):
    await init_db()

    job_id = f"test-e2e-{uuid.uuid4()}"
    password = "SuperSecretPassword2026!"

    signup_data = SignupInput(
        first_name="Alex",
        last_name="Hamster",
        birth_day=15,
        birth_month="January",
        birth_year=1995,
        gender="female",
        password=password,
        confirm_password=password,
        preferred_username="alexhamster"
    )

    # 1. Create job in DB & Registry
    async with async_session_factory() as db:
        await crud.create_job(db, username=signup_data.preferred_username, job_id=job_id)

    active_job = ActiveJob(
        job_id=job_id,
        username=signup_data.preferred_username,
        password=password,
        signup_input=signup_data,
        target_url="http://127.0.0.1:8001/signup"
    )
    job_registry.register(active_job)

    original_headless = settings.HEADLESS
    settings.HEADLESS = True

    try:
        # 2. Start orchestration task in background
        task = asyncio.create_task(run_orchestrated_workflow(job_id))

        # 3. Wait for automation to hit the phone challenge step and pause
        for _ in range(40):
            await asyncio.sleep(0.5)
            if active_job.status == "WAITING_FOR_USER":
                break

        assert active_job.status == "WAITING_FOR_USER"
        assert active_job.manual_intervention_required is True
        assert active_job.current_step == "PHONE_VERIFICATION_REQUIRED"
        assert active_job.page is not None

        # 4. Simulate human solving the phone challenge in the browser window
        await active_job.page.get_by_label("Enter 6-digit verification code (Use 123456)").fill("123456")
        await active_job.page.get_by_role("button", name="Next").click()
        await asyncio.sleep(1)

        # 5. User signals completion via resume
        resumed = job_registry.resume(job_id)
        assert resumed is True

        # 6. Wait for workflow to finish remaining steps (Recovery Skip -> Terms Agree -> Selfie Skip -> Login)
        await asyncio.wait_for(task, timeout=30.0)

        # 7. Check final job state
        assert active_job.status == "COMPLETED"
        assert active_job.current_step == "ALL_STEPS_COMPLETED"

        # Verify Google's suggested username was captured!
        assert active_job.username == "alexhamster.suggested"

        # Check DB state
        async with async_session_factory() as db:
            db_job = await crud.get_job(db, job_id)
            assert db_job is not None
            assert db_job.status == "COMPLETED"

            # Check that credentials were saved and encrypted for the captured username
            cred = await crud.get_credential(db, "alexhamster.suggested")
            assert cred is not None
            assert cred.encrypted_password != password.encode("utf-8")

            # Verify decryption returns original password
            decrypted = decrypt_password(cred.encrypted_password, settings.ENCRYPTION_KEY)
            assert decrypted == password

    finally:
        settings.HEADLESS = original_headless
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

@pytest.mark.asyncio
async def test_unexpected_page_pauses_for_user():
    """Test that unexpected pages trigger WAITING_FOR_USER rather than blind failure."""
    await init_db()
    job_id = f"test-unexpected-{uuid.uuid4()}"

    active_job = ActiveJob(
        job_id=job_id,
        username="testuser",
        password="PassWord123!",
        target_url="about:blank"  # Blank page is an unexpected registration page
    )
    job_registry.register(active_job)

    settings.HEADLESS = True
    task = asyncio.create_task(run_orchestrated_workflow(job_id))

    try:
        for _ in range(20):
            await asyncio.sleep(0.5)
            if active_job.status == "WAITING_FOR_USER":
                break

        assert active_job.status == "WAITING_FOR_USER"
        assert active_job.current_step == "UNRECOGNIZED_PAGE_DETECTED"
        assert active_job.manual_intervention_required is True
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
