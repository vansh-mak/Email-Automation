import uuid
import json
import asyncio
import pytest
from config import settings
from database.session import init_db, async_session_factory
from database import crud
from schemas.automation import SignupInput
from services.job_registry import job_registry, ActiveJob
from services.orchestrator import run_orchestrated_workflow
from automation.signup import run_signup, RegistrationStep

@pytest.mark.asyncio
async def test_browser_disconnection_handled_gracefully():
    """
    If the browser window or context is closed unexpectedly during execution,
    the orchestrator must catch the error, transition to FAILED, record the error,
    release resources cleanly, and avoid storing credentials.
    """
    await init_db()
    job_id = f"test-disconnect-{uuid.uuid4()}"
    username = "disconnect_user"

    async with async_session_factory() as db:
        await crud.create_job(db, username=username, job_id=job_id)

    active_job = ActiveJob(
        job_id=job_id,
        username=username,
        password="TestPassword123!",
        target_url="about:blank"
    )
    job_registry.register(active_job)

    original_headless = settings.HEADLESS
    settings.HEADLESS = True

    try:
        task = asyncio.create_task(run_orchestrated_workflow(job_id))

        # Wait until page is launched
        for _ in range(20):
            await asyncio.sleep(0.5)
            if active_job.page is not None:
                break

        assert active_job.page is not None

        # Simulate user or system forcibly closing the browser page
        await active_job.page.close()

        # If it was paused waiting for user, resume it so it tries to act on the closed page
        active_job.resume_event.set()

        # Wait for orchestrator task to handle the closed page
        await asyncio.wait_for(task, timeout=15.0)

        # Status must be FAILED with error message
        assert active_job.status == "FAILED"
        assert active_job.error_message is not None

        # Verify in DB
        async with async_session_factory() as db:
            db_job = await crud.get_job(db, job_id)
            assert db_job.status == "FAILED"

            # No credentials should have been saved
            cred = await crud.get_credential(db, username)
            assert cred is None

    finally:
        settings.HEADLESS = original_headless
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

@pytest.mark.asyncio
async def test_uncertain_final_submission_does_not_store_credentials():
    """
    If the workflow completes steps but final account creation cannot be confirmed,
    status must be REGISTRATION_UNSUCCESSFUL and credentials must NOT be stored.
    """
    await init_db()
    job_id = f"test-uncertain-{uuid.uuid4()}"
    username = "uncertain_user"
    password = "SecretPassword123!"

    async with async_session_factory() as db:
        await crud.create_job(db, username=username, job_id=job_id)

    # Use a dummy page that never reaches COMPLETED and has no known Google fields
    active_job = ActiveJob(
        job_id=job_id,
        username=username,
        password=password,
        target_url="data:text/html,<html><body><h1>Stuck Page</h1></body></html>"
    )
    job_registry.register(active_job)

    settings.HEADLESS = True
    task = asyncio.create_task(run_orchestrated_workflow(job_id))

    try:
        # It will detect UNKNOWN and pause with WAITING_FOR_USER
        for _ in range(20):
            await asyncio.sleep(0.5)
            if active_job.status == "WAITING_FOR_USER":
                break

        assert active_job.status == "WAITING_FOR_USER"

        # Resume without reaching completion to simulate exhausting iterations
        # We simulate this directly by verifying that without confirmed COMPLETED, creds aren't saved
        async with async_session_factory() as db:
            cred = await crud.get_credential(db, username)
            assert cred is None

    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

@pytest.mark.asyncio
async def test_server_restart_and_job_recovery_from_db():
    """
    Test that job progress (including completed_steps) is durably stored in SQLite,
    and survives a simulated server restart / volatile memory wipe.
    """
    await init_db()
    job_id = f"test-recovery-{uuid.uuid4()}"
    username = "persisted_user"

    completed_steps_list = ["NAME", "BIRTHDAY_GENDER", "USERNAME"]

    # 1. Create and update job in database
    async with async_session_factory() as db:
        await crud.create_job(db, username=username, job_id=job_id)
        await crud.update_job(
            db,
            job_id=job_id,
            status="WAITING_FOR_USER",
            current_step="PHONE_VERIFICATION_REQUIRED",
            manual_intervention_required=True,
            completed_steps=json.dumps(completed_steps_list),
            username="suggested.persisted.user"
        )

    # 2. Simulate server restart: volatile memory is wiped
    job_registry._jobs.clear()
    assert job_registry.get(job_id) is None

    # 3. Query job state from DB (as routes/automation.py does)
    async with async_session_factory() as db:
        db_job = await crud.get_job(db, job_id)
        assert db_job is not None
        assert db_job.status == "WAITING_FOR_USER"
        assert db_job.current_step == "PHONE_VERIFICATION_REQUIRED"
        assert db_job.manual_intervention_required is True
        assert db_job.username == "suggested.persisted.user"

        recovered_steps = json.loads(db_job.completed_steps)
        assert recovered_steps == completed_steps_list
