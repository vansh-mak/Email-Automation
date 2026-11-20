import json
import logging
from config import settings
from database.session import async_session_factory
from database import crud
from security.encryption import encrypt_password
from services.job_registry import job_registry, ActiveJob
from automation.browser import BrowserManager
from automation.signup import run_signup
from automation.login import run_login

logger = logging.getLogger(__name__)

async def run_orchestrated_workflow(job_id: str) -> None:
    """
    Main background orchestrator coordinating browser launch, multi-step signup assistance,
    human pause/resume handling, credential encryption, and login verification.
    """
    job = job_registry.get(job_id)
    if not job:
        logger.error(f"Cannot orchestrate workflow: Job '{job_id}' not found in registry.")
        return

    p = None
    browser = None
    context = None
    page = None

    async def update_status(
        status: str,
        step: str,
        intervention: bool = False,
        error_msg: str = ""
    ) -> None:
        """Helper to synchronize status and completed steps across memory and SQLite database."""
        job.status = status
        job.current_step = step
        job.manual_intervention_required = intervention
        job.error_message = error_msg or None

        completed_json = json.dumps(sorted(list(job.completed_steps)))

        async with async_session_factory() as db:
            await crud.update_job(
                db,
                job_id=job.job_id,
                username=job.username,
                status=status,
                current_step=step,
                manual_intervention_required=intervention,
                error_message=error_msg or None,
                completed_steps=completed_json
            )

    try:
        logger.info(f"Starting orchestration for job '{job_id}' (Initial User: {job.username})...")
        await update_status("RUNNING", "LAUNCHING_BROWSER", False)

        # 1. Launch Browser Session
        p, browser, context, page = await BrowserManager.create_session()

        # 2. Run Registration Assistance
        signup_success = await run_signup(page, job, update_status)

        if not signup_success:
            logger.warning(f"Registration workflow for job '{job_id}' did not confirm success.")
            await update_status(
                "FAILED",
                "REGISTRATION_UNSUCCESSFUL",
                False,
                "Registration was not confirmed or could not be completed."
            )
            return

        # 3. Securely Encrypt & Save Credentials ONLY After Verified Registration
        # Use job.username which may have been updated to Google's selected suggestion!
        await update_status("RUNNING", "ENCRYPTING_CREDENTIALS", False)
        final_password = job.password or (job.signup_input.password if job.signup_input else "")
        encrypted_token = encrypt_password(final_password, settings.ENCRYPTION_KEY)

        async with async_session_factory() as db:
            # Also update username in DB in case an alternative suggested handle was chosen
            await crud.update_job(db, job_id=job.job_id, current_step="CREDENTIALS_SAVED")
            await crud.save_credential(
                db,
                username=job.username,
                encrypted_password=encrypted_token,
                job_id=job.job_id
            )
        logger.info(f"Credentials for '{job.username}' encrypted and stored in SQLite.")

        # 4. Open Login and Verify Session Access
        login_url = settings.GOOGLE_LOGIN_URL
        if job.target_url and ("8001" in job.target_url or "mock" in job.target_url):
            login_url = settings.MOCK_LOGIN_URL

        login_success = await run_login(page, job, login_url, update_status)

        if login_success:
            logger.info(f"Full workflow completed successfully for job '{job_id}'!")
            await update_status("COMPLETED", "ALL_STEPS_COMPLETED", False, "")
        else:
            logger.warning(f"Registration succeeded but login verification failed for job '{job_id}'.")
            await update_status(
                "FAILED",
                "LOGIN_VERIFICATION_FAILED",
                False,
                "Registration succeeded but automated login verification failed."
            )

    except Exception as e:
        logger.exception(f"Unexpected error in orchestration workflow for job '{job_id}': {e}")
        await update_status("FAILED", "ERROR_ENCOUNTERED", False, str(e))

    finally:
        # 5. Clean up browser session
        await BrowserManager.close_session(p, browser, context, page)
        # Clear plaintext password from volatile memory
        job.password = ""
        if job.signup_input:
            job.signup_input.password = ""
            job.signup_input.confirm_password = ""
