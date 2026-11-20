import pytest
from playwright.async_api import async_playwright
from schemas.automation import SignupInput
from services.job_registry import ActiveJob
from automation.signup import (
    RegistrationStep,
    detect_page_step,
    handle_name_step,
    handle_birthday_gender_step,
    handle_username_step,
    handle_password_step,
    handle_recovery_step,
    handle_account_review_step,
    handle_selfie_verification_step
)
from tests.mock_site.mock_app import SIGNUP_TEMPLATE

@pytest.fixture
def file_url():
    return f"file:///{SIGNUP_TEMPLATE.replace('\\', '/')}"

@pytest.mark.asyncio
async def test_detect_and_execute_name_step(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # 1. Detection
        step = await detect_page_step(page)
        assert step == RegistrationStep.NAME

        # 2. Execution
        signup_input = SignupInput(first_name="Jane", last_name="Doe", password="SecretPassword123!")
        result = await handle_name_step(page, signup_input)
        assert result is True

        # 3. Post-execution detection should be BIRTHDAY_GENDER
        post_step = await detect_page_step(page)
        assert post_step == RegistrationStep.BIRTHDAY_GENDER

        await browser.close()

@pytest.mark.asyncio
async def test_birthday_gender_step(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Advance to step 2
        signup_input = SignupInput(first_name="Jane", last_name="Doe", password="SecretPassword123!", birth_day=20, birth_month="February", birth_year=1998, gender="female")
        await handle_name_step(page, signup_input)

        # Execute birthday gender
        res = await handle_birthday_gender_step(page, signup_input)
        assert res is True

        # Post-execution detection should be USERNAME
        assert await detect_page_step(page) == RegistrationStep.USERNAME

        await browser.close()

@pytest.mark.asyncio
async def test_username_suggested_selection(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        signup_input = SignupInput(first_name="Jane", last_name="Doe", password="SecretPassword123!")
        job = ActiveJob(job_id="test-job", username="initial_placeholder", password="SecretPassword123!")

        # Advance to username step
        await handle_name_step(page, signup_input)
        await handle_birthday_gender_step(page, signup_input)

        # Execute username step
        assert await detect_page_step(page) == RegistrationStep.USERNAME
        res = await handle_username_step(page, signup_input, job)
        assert res is True

        # Verify Google's suggested username was selected and captured!
        assert job.username == "alexhamster.suggested"

        # Post-execution detection should be PASSWORD
        assert await detect_page_step(page) == RegistrationStep.PASSWORD

        await browser.close()

@pytest.mark.asyncio
async def test_password_step_validation_and_confirm(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        signup_input = SignupInput(first_name="Jane", last_name="Doe", password="SecretPassword123!", confirm_password="SecretPassword123!")
        job = ActiveJob(job_id="test-job", username="testuser", password="SecretPassword123!")

        # Advance to password step
        await handle_name_step(page, signup_input)
        await handle_birthday_gender_step(page, signup_input)
        await handle_username_step(page, signup_input, job)

        assert await detect_page_step(page) == RegistrationStep.PASSWORD
        res = await handle_password_step(page, signup_input)
        assert res is True

        # Post-execution detection should be PHONE_VERIFICATION
        assert await detect_page_step(page) == RegistrationStep.PHONE_VERIFICATION

        await browser.close()

@pytest.mark.asyncio
async def test_recovery_step_skips(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Directly navigate to recovery step in mock DOM
        await page.evaluate("() => { document.getElementById('step-name').classList.remove('active'); document.getElementById('step-recovery').classList.add('active'); }")

        assert await detect_page_step(page) == RegistrationStep.RECOVERY_INFORMATION
        res = await handle_recovery_step(page)
        assert res is True

        # Post-step should be ACCOUNT_REVIEW (Terms)
        assert await detect_page_step(page) == RegistrationStep.ACCOUNT_REVIEW

        await browser.close()

@pytest.mark.asyncio
async def test_account_review_accepts_terms(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Directly navigate to terms step in mock DOM
        await page.evaluate("() => { document.getElementById('step-name').classList.remove('active'); document.getElementById('step-terms').classList.add('active'); }")

        assert await detect_page_step(page) == RegistrationStep.ACCOUNT_REVIEW
        res = await handle_account_review_step(page)
        assert res is True

        # Post-step should be SELFIE_VERIFICATION
        assert await detect_page_step(page) == RegistrationStep.SELFIE_VERIFICATION

        await browser.close()

@pytest.mark.asyncio
async def test_optional_selfie_skips(file_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Directly navigate to selfie step in mock DOM
        await page.evaluate("() => { document.getElementById('step-name').classList.remove('active'); document.getElementById('step-selfie').classList.add('active'); }")

        assert await detect_page_step(page) == RegistrationStep.SELFIE_VERIFICATION
        job = ActiveJob(job_id="test", username="test", password="pwd")
        async def mock_cb(status, step, req, err): pass

        res = await handle_selfie_verification_step(page, job, mock_cb)
        assert res is True

        # Post-step should be COMPLETED!
        assert await detect_page_step(page) == RegistrationStep.COMPLETED

        await browser.close()

@pytest.mark.asyncio
async def test_mandatory_selfie_pauses_for_user(file_url):
    """When no 'Not now' or 'Skip' button exists, selfie verification must pause for user intervention."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Activate selfie step and remove skip button to simulate mandatory challenge
        await page.evaluate("""() => {
            document.getElementById('step-name').classList.remove('active');
            document.getElementById('step-selfie').classList.add('active');
            const skipBtn = document.getElementById('btn-skip-selfie');
            if (skipBtn) skipBtn.remove();
        }""")

        assert await detect_page_step(page) == RegistrationStep.SELFIE_VERIFICATION
        job = ActiveJob(job_id="test-selfie-job", username="testuser", password="pwd")

        status_updates = []
        async def mock_cb(status, step, req, err):
            status_updates.append((status, step, req))

        # Launch handler in background task because it will pause awaiting resume_event
        import asyncio
        task = asyncio.create_task(handle_selfie_verification_step(page, job, mock_cb))

        # Give it a moment to pause
        await asyncio.sleep(0.5)
        assert len(status_updates) == 1
        assert status_updates[0] == ("WAITING_FOR_USER", "SELFIE_VERIFICATION_REQUIRED", True)

        # Simulate user completing selfie and signaling resume
        job.resume_event.set()
        res = await asyncio.wait_for(task, timeout=5.0)
        assert res is True
        assert status_updates[-1][0] == "RUNNING"
        assert status_updates[-1][1] == "SELFIE_VERIFICATION_COMPLETED"

        await browser.close()

@pytest.mark.asyncio
async def test_username_taken_validation_error(file_url):
    """When a username is taken, page presents a validation error alert and detect_page_step detects it."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Switch to username step and inject validation error alert
        await page.evaluate("""() => {
            document.getElementById('step-name').classList.remove('active');
            document.getElementById('step-username').classList.add('active');
            const alertDiv = document.createElement('div');
            alertDiv.setAttribute('role', 'alert');
            alertDiv.innerText = 'That username is taken. Try another.';
            document.getElementById('step-username').prepend(alertDiv);
        }""")

        detected = await detect_page_step(page)
        assert detected == RegistrationStep.VALIDATION_ERROR

        await browser.close()

@pytest.mark.asyncio
async def test_password_mismatch_raises_error(file_url):
    """Mismatched passwords must be caught in-memory before submitting to Google."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(file_url)

        # Switch to password step
        await page.evaluate("""() => {
            document.getElementById('step-name').classList.remove('active');
            document.getElementById('step-password').classList.add('active');
        }""")

        mismatched_input = SignupInput(
            first_name="Alice",
            last_name="Smith",
            password="StrongPassword123!",
            confirm_password="DifferentPassword456!"
        )

        with pytest.raises(ValueError, match="Password confirmation mismatch"):
            await handle_password_step(page, mismatched_input)

        await browser.close()
