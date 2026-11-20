import json
import logging
from enum import Enum
from typing import Callable, Awaitable, Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from services.job_registry import ActiveJob
from schemas.automation import SignupInput

logger = logging.getLogger(__name__)

class RegistrationStep(str, Enum):
    NAME = "NAME"
    BIRTHDAY_GENDER = "BIRTHDAY_GENDER"
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    PHONE_VERIFICATION = "PHONE_VERIFICATION"
    RECOVERY_INFORMATION = "RECOVERY_INFORMATION"
    ACCOUNT_REVIEW = "ACCOUNT_REVIEW"
    SELFIE_VERIFICATION = "SELFIE_VERIFICATION"
    FINAL_VERIFICATION = "FINAL_VERIFICATION"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"

async def detect_page_step(page: Page) -> RegistrationStep:
    """
    Inspect the current DOM structure and URL to dynamically determine the active registration step.
    Does not assume a fixed sequence. Uses specific leaf tag selectors to avoid false parent matches.
    """
    # 1. Check for Completed State
    for sel in ['#welcome-username:visible', '.success-box:visible', '#step-completed:visible', 'h2:has-text("Welcome"):visible', 'h1:has-text("Welcome"):visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.COMPLETED

    current_url = page.url.lower()
    if "myaccount.google.com" in current_url or "mail.google.com" in current_url:
        return RegistrationStep.COMPLETED

    # 2. Check for Validation Errors
    for sel in ['[role="alert"]:visible', '.EkSpEc:visible', '.o6cuMc:visible', 'span:has-text("That username is taken"):visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.VALIDATION_ERROR

    # 3. Birthday and Gender Step (must be before phone verification)
    dob_indicators = [
        '#step-dob:visible',
        '#dob_year:visible',
        'h1:has-text("Basic information"):visible',
        '#gender:visible',
        'select[name*="gender" i]:visible'
    ]
    for sel in dob_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.BIRTHDAY_GENDER

    # 4. Phone Verification Checkpoint
    phone_indicators = [
        '#step-phone:visible',
        '#verification_code:visible',
        '.challenge-box:visible',
        'input[type="tel"]:visible',
        'h1:has-text("Confirm you’re not a robot"):visible',
        'h1:has-text("Verify your phone"):visible',
        'iframe[src*="recaptcha"]:visible'
    ]
    for sel in phone_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.PHONE_VERIFICATION

    # 4. Selfie / Identity Verification Checkpoint
    selfie_indicators = [
        '#step-selfie:visible',
        'h1:has-text("Take a video selfie"):visible',
        'h1:has-text("Selfie verification"):visible',
        '#selfie-challenge:visible',
        '#btn-skip-selfie:visible'
    ]
    for sel in selfie_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.SELFIE_VERIFICATION

    # 5. Recovery Information (Email / Phone)
    recovery_indicators = [
        '#step-recovery:visible',
        '#recovery_email:visible',
        '#recovery-box:visible',
        'h1:has-text("Add recovery"):visible',
        '#btn-skip-recovery:visible',
        'input[name*="recovery" i]:visible'
    ]
    for sel in recovery_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.RECOVERY_INFORMATION

    # 6. Account Review & Privacy / Terms Acceptance
    review_indicators = [
        '#step-terms:visible',
        '#terms-box:visible',
        '#btn-agree-terms:visible',
        'h1:has-text("Review your account"):visible',
        'h1:has-text("Privacy and Terms"):visible',
        'button:has-text("I agree"):visible'
    ]
    for sel in review_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.ACCOUNT_REVIEW

    # 7. Password Step
    password_indicators = [
        '#step-password:visible',
        '#password:visible',
        'input[name="Passwd"]:visible',
        'input[name="password" i]:visible',
        'h1:has-text("Create a strong password"):visible'
    ]
    for sel in password_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.PASSWORD

    # 8. Username Step (Suggested Radios or Custom Handle Input)
    username_indicators = [
        '#step-username:visible',
        '#username:visible',
        'input[type="radio"]:visible',
        '[role="radio"]:visible',
        'h1:has-text("Choose your Gmail address"):visible',
        'h1:has-text("Create a Gmail address"):visible'
    ]
    for sel in username_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.USERNAME

    # 9. Birthday and Gender Step
    dob_indicators = [
        '#step-dob:visible',
        '#dob_year:visible',
        'h1:has-text("Basic information"):visible',
        '#gender:visible',
        'select[name*="gender" i]:visible'
    ]
    for sel in dob_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.BIRTHDAY_GENDER

    # 10. Name Step (First Name & Last Name)
    name_indicators = [
        '#step-name:visible',
        '#first_name:visible',
        'h1:has-text("Create a Google Account"):visible',
        'input[name*="first" i]:visible'
    ]
    for sel in name_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            return RegistrationStep.NAME

    return RegistrationStep.UNKNOWN

# --- Individual Step Handlers ---

async def handle_name_step(page: Page, signup_input: SignupInput) -> bool:
    """Fill first and last name, verify values, then click Next.
    If any required element is missing, log the selector and raise an error.
    """
    logger.info("Executing Step: NAME")
    # First name input
    first_input = page.locator('input[name*="first" i], input[id*="first" i]').first
    if await first_input.count() == 0 or not await first_input.is_visible():
        logger.error("First name input not found. Selector: input[name*='first' i], input[id*='first' i]")
        raise RuntimeError("First name input missing for NAME step")
    await first_input.fill(signup_input.first_name)
    # Verify fill
    if (await first_input.input_value()) != signup_input.first_name:
        logger.error(f"Failed to set first name. Expected: {signup_input.first_name}, Got: {await first_input.input_value()}")
        raise RuntimeError("First name verification failed")

    # Last name input (optional but fill if present)
    last_input = page.locator('input[name*="last" i], input[id*="last" i]').first
    if await last_input.count() > 0 and await last_input.is_visible():
        await last_input.fill(signup_input.last_name)
        if (await last_input.input_value()) != signup_input.last_name:
            logger.error(f"Failed to set last name. Expected: {signup_input.last_name}, Got: {await last_input.input_value()}")
            raise RuntimeError("Last name verification failed")

    # Click Next button
    next_selectors = [
        '#btn-step-name-next',
        '#btn-step-1-next',
        'button:has-text("Next"):visible',
        'button[type="submit"]:visible'
    ]
    for sel in next_selectors:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
            return True
    logger.error(f"Next button not found for NAME step. Tried selectors: {next_selectors}")
    raise RuntimeError("Next button missing for NAME step")

async def handle_birthday_gender_step(page: Page, signup_input: SignupInput) -> bool:
    """Fill day, month, year, and gender using supplied input, then click Next.
    This version waits for the BIRTHDAY_GENDER step to become active before locating
    controls, logs the discovered element types, and supports both native <select>
    dropdowns and custom implementations.
    """
    logger.info("Executing Step: BIRTHDAY_GENDER")

    # Wait for the step container to be active – ensures the DOM has rendered the fields.
    try:
        await page.wait_for_selector('#step-dob.active', timeout=5000)
        logger.debug("BIRTHDAY_GENDER step is now active.")
    except Exception as e:
        logger.error(f"BIRTHDAY_GENDER step never became active: {e}")
        raise RuntimeError("BIRTHDAY_GENDER step not reachable")

    # Helper to log element details
    async def log_element(selector: str, name: str):
        el = page.locator(selector).first
        if await el.count() > 0:
            tag = await el.evaluate("el => el.tagName")
            role = await el.get_attribute('role')
            logger.debug(f"{name}: found selector '{selector}' – tag={tag}, role={role}")
        else:
            logger.debug(f"{name}: selector '{selector}' not found.")

    # ----------- Day (text input) -----------
    day_selector = '#dob_day'
    await log_element(day_selector, 'Day input')
    day_loc = page.locator(day_selector).first
    if await day_loc.count() == 0 or not await day_loc.is_visible():
        logger.error("Day input not found or not visible.")
        raise RuntimeError("Day input missing for BIRTHDAY_GENDER step")
    await day_loc.fill(str(signup_input.birth_day))
    if (await day_loc.input_value()) != str(signup_input.birth_day):
        logger.error(f"Failed to set day. Expected {signup_input.birth_day}, got {await day_loc.input_value()}")
        raise RuntimeError("Day input verification failed")

    # ----------- Month (native <select> or custom) -----------
    month_selector = '#dob_month'
    await log_element(month_selector, 'Month control')
    month_el = page.locator(month_selector).first
    if await month_el.count() == 0:
        logger.error("Month control not found.")
        raise RuntimeError("Month control missing for BIRTHDAY_GENDER step")
    tag_name = await month_el.evaluate("el => el.tagName")
    if tag_name.lower() == 'select':
        # Native select – use select_option()
        try:
            await month_el.select_option(str(signup_input.birth_month))
        except Exception as e:
            logger.debug(f"Native select_option failed for month {signup_input.birth_month}: {e}")
            # fallback to first option
            await month_el.select_option(index=0)
    else:
        # Custom dropdown – click to open, then click the visible option text
        await month_el.click()
        option_locator = f"text={signup_input.birth_month}"  # Playwright text selector
        option = page.locator(option_locator).first
        if await option.count() == 0:
            logger.error(f"Month option '{signup_input.birth_month}' not found in custom dropdown.")
            raise RuntimeError("Month option not found")
        await option.click()
    # Verify month selection (for native select we can read value; for custom we trust click)
    if tag_name.lower() == 'select':
        selected_month = await month_el.input_value()
        if selected_month.lower() != str(signup_input.birth_month).lower():
            logger.warning(f"Month selection mismatch. Desired {signup_input.birth_month}, got {selected_month}")

    # ----------- Year (text input) -----------
    year_selector = '#dob_year'
    await log_element(year_selector, 'Year input')
    year_loc = page.locator(year_selector).first
    if await year_loc.count() == 0 or not await year_loc.is_visible():
        logger.error("Year input not found or not visible.")
        raise RuntimeError("Year input missing for BIRTHDAY_GENDER step")
    await year_loc.fill(str(signup_input.birth_year))
    if (await year_loc.input_value()) != str(signup_input.birth_year):
        logger.error(f"Failed to set year. Expected {signup_input.birth_year}, got {await year_loc.input_value()}")
        raise RuntimeError("Year input verification failed")

    # ----------- Gender (native <select> or custom) -----------
    gender_selector = '#gender'
    await log_element(gender_selector, 'Gender control')
    gender_el = page.locator(gender_selector).first
    if await gender_el.count() == 0:
        logger.error("Gender control not found.")
        raise RuntimeError("Gender control missing for BIRTHDAY_GENDER step")
    tag_name_gender = await gender_el.evaluate("el => el.tagName")
    if tag_name_gender.lower() == 'select':
        try:
            await gender_el.select_option(signup_input.gender.lower())
        except Exception as e:
            logger.debug(f"Native select_option failed for gender {signup_input.gender}: {e}")
            await gender_el.select_option(index=0)
    else:
        await gender_el.click()
        gender_option = page.locator(f"text={signup_input.gender}").first
        if await gender_option.count() == 0:
            logger.error(f"Gender option '{signup_input.gender}' not found in custom dropdown.")
            raise RuntimeError("Gender option not found")
        await gender_option.click()
    if tag_name_gender.lower() == 'select':
        selected_gender = await gender_el.input_value()
        if selected_gender.lower() != signup_input.gender.lower():
            logger.warning(f"Gender selection mismatch. Desired {signup_input.gender}, got {selected_gender}")

    # ----------- Click Next -----------
    next_clicked = False
    for sel in ['#btn-step-dob-next', '#btn-step-2-next', 'button:has-text("Next"):visible', 'button[type="submit"]:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            next_clicked = True
            logger.debug(f"Clicked Next button using selector '{sel}'")
            break
    if not next_clicked:
        logger.error("Next button not found for BIRTHDAY_GENDER step")
        raise RuntimeError("Next button missing for BIRTHDAY_GENDER step")

    # Wait for transition to USERNAME step (or at least for the next step container)
    try:
        await page.wait_for_selector('#step-username.active', timeout=5000)
        logger.debug("Transitioned to USERNAME step.")
    except Exception as e:
        logger.warning(f"Did not detect USERNAME step after BIRTHDAY_GENDER: {e}")
    return True
    """Fill day, month, year, and gender using supplied input, then click Next.
    Verifies each field after filling and raises detailed errors if missing.
    """
    logger.info("Executing Step: BIRTHDAY_GENDER")

    # Day input
    day_loc = page.locator('#dob_day:visible, input[name*="day" i]:visible, input[id*="day" i]:visible').first
    if await day_loc.count() == 0 or not await day_loc.is_visible():
        logger.error("Day input not found. Selector: #dob_day")
        raise RuntimeError("Day input missing for BIRTHDAY_GENDER step")
    await day_loc.fill(str(signup_input.birth_day))
    if (await day_loc.input_value()) != str(signup_input.birth_day):
        logger.error(f"Failed to set day. Expected: {signup_input.birth_day}, Got: {await day_loc.input_value()}")
        raise RuntimeError("Day input verification failed")

    # Month select
    month_select = page.locator('#dob_month:visible, select[name*="month" i]:visible, select[id*="month" i]:visible').first
    if await month_select.count() == 0 or not await month_select.is_visible():
        logger.error("Month select not found. Selector: #dob_month")
        raise RuntimeError("Month select missing for BIRTHDAY_GENDER step")
    try:
        await month_select.select_option(str(signup_input.birth_month))
    except Exception as e:
        logger.debug(f"select_option failed for month {signup_input.birth_month}: {e}")
        await month_select.select_option(index=0)
    selected_month = await month_select.input_value()
    if selected_month.lower() != str(signup_input.birth_month).lower():
        logger.warning(f"Month selection mismatch. Desired: {signup_input.birth_month}, Got: {selected_month}")

    # Year input
    year_loc = page.locator('#dob_year:visible, input[name*="year" i]:visible, input[id*="year" i]:visible').first
    if await year_loc.count() == 0 or not await year_loc.is_visible():
        logger.error("Year input not found. Selector: #dob_year")
        raise RuntimeError("Year input missing for BIRTHDAY_GENDER step")
    await year_loc.fill(str(signup_input.birth_year))
    if (await year_loc.input_value()) != str(signup_input.birth_year):
        logger.error(f"Failed to set year. Expected: {signup_input.birth_year}, Got: {await year_loc.input_value()}")
        raise RuntimeError("Year input verification failed")

    # Gender select
    gender_select = page.locator('#gender:visible, select[name*="gender" i]:visible, select[id*="gender" i]:visible').first
    if await gender_select.count() == 0 or not await gender_select.is_visible():
        logger.error("Gender select not found. Selector: #gender")
        raise RuntimeError("Gender select missing for BIRTHDAY_GENDER step")
    try:
        await gender_select.select_option(signup_input.gender.lower())
    except Exception as e:
        logger.debug(f"select_option failed for gender {signup_input.gender}: {e}")
        await gender_select.select_option(index=0)
    selected_gender = await gender_select.input_value()
    if selected_gender.lower() != signup_input.gender.lower():
        logger.warning(f"Gender selection mismatch. Desired: {signup_input.gender}, Got: {selected_gender}")

    # Click Next button
    next_clicked = False
    for sel in ['#btn-step-dob-next', '#btn-step-2-next', 'button:has-text("Next"):visible', 'button[type="submit"]:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            next_clicked = True
            break
    if not next_clicked:
        logger.error("Next button not found for BIRTHDAY_GENDER step")
        raise RuntimeError("Next button missing for BIRTHDAY_GENDER step")

    # Wait for transition to USERNAME step
    try:
        await page.wait_for_selector('#step-username.active', timeout=5000)
    except Exception as e:
        logger.warning(f"Transition to USERNAME step not detected: {e}")
    return True
    """Fill day, month, year, and gender using supplied input, then click Next."""
    logger.info("Executing Step: BIRTHDAY_GENDER")

    # Day
    day_loc = page.locator('#dob_day:visible, input[name*="day" i]:visible, input[id*="day" i]:visible').first
    if await day_loc.count() > 0:
        await day_loc.fill(str(signup_input.birth_day))

    # Month (handles select dropdown or text input)
    month_select = page.locator('#dob_month:visible, select[name*="month" i]:visible, select[id*="month" i]:visible').first
    if await month_select.count() > 0:
        try:
            await month_select.select_option(str(signup_input.birth_month))
        except Exception:
            try:
                await month_select.select_option(index=1)
            except Exception:
                pass
    else:
        month_input = page.locator('input[name*="month" i]:visible, input[id*="month" i]:visible').first
        if await month_input.count() > 0:
            await month_input.fill(str(signup_input.birth_month))

    # Year
    year_loc = page.locator('#dob_year:visible, input[name*="year" i]:visible, input[id*="year" i]:visible').first
    if await year_loc.count() > 0:
        await year_loc.fill(str(signup_input.birth_year))

    # Gender
    gender_select = page.locator('#gender:visible, select[name*="gender" i]:visible, select[id*="gender" i]:visible').first
    if await gender_select.count() > 0:
        try:
            await gender_select.select_option(signup_input.gender.lower())
        except Exception:
            try:
                await gender_select.select_option(index=1)
            except Exception:
                pass

    # Click Next
    for sel in ['#btn-step-dob-next', '#btn-step-2-next', 'button:has-text("Next"):visible', 'button[type="submit"]:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
            return True
    return False

async def handle_username_step(page: Page, signup_input: SignupInput, job: ActiveJob) -> bool:
    """
    Select the first suggested Gmail username option if Google presents radio buttons,
    otherwise fill the preferred handle, capture the selected username into job.username, and click Next.
    """
    logger.info("Executing Step: USERNAME")

    # 1. Check if Google presents suggested username radio buttons
    radios = page.locator('input[type="radio"]:visible, [role="radio"]:visible')
    radio_count = await radios.count()

    if radio_count > 0:
        logger.info(f"Google presented {radio_count} suggested username options. Selecting the first option.")
        first_radio = radios.first
        await first_radio.click()

        # Capture selected username
        try:
            val = await first_radio.get_attribute("value")
            if val and not val.startswith("custom"):
                job.username = val.split("@")[0].strip()
            else:
                radio_id = await first_radio.get_attribute("id")
                if radio_id:
                    lbl = page.locator(f'label[for="{radio_id}"]')
                    if await lbl.count() > 0:
                        lbl_text = await lbl.first.inner_text()
                        job.username = lbl_text.split("@")[0].strip().replace("\n", " ").split()[0]
            logger.info(f"Captured Google-suggested username: {job.username}")
        except Exception as e:
            logger.debug(f"Could not extract radio label: {e}")

    else:
        # Fallback to custom text input
        user_input = page.locator('#username:visible, input[name*="user" i]:visible, input[id*="user" i]:visible').first
        if await user_input.count() > 0:
            target_user = signup_input.preferred_username or job.username
            await user_input.fill(target_user)
            job.username = target_user

    # Click Next
    for sel in ['#btn-step-username-next', '#btn-step-2-next', 'button:has-text("Next"):visible', 'button[type="submit"]:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
            return True
    return False

async def handle_password_step(page: Page, signup_input: SignupInput) -> bool:
    """
    Validate and fill the password and confirmation password fields, then click Next.
    Zero plaintext credentials logged.
    """
    logger.info("Executing Step: PASSWORD (validating confirmation before filling)")

    # Client-side / In-memory confirmation check
    if signup_input.confirm_password and signup_input.password != signup_input.confirm_password:
        raise ValueError("Password confirmation mismatch. Cannot submit mismatched credentials.")

    # Primary password
    pwd_input = page.locator('#password:visible, input[name="Passwd"]:visible, input[type="password"]:visible').first
    if await pwd_input.count() > 0:
        await pwd_input.fill(signup_input.password)

    # Confirmation password (if distinct confirmation field exists)
    confirm_pwd_input = page.locator('#confirm_password:visible, input[name="PasswdAgain"]:visible, input[name*="confirm" i]:visible').first
    if await confirm_pwd_input.count() > 0:
        await confirm_pwd_input.fill(signup_input.password)

    # Click Next
    for sel in ['#btn-step-password-next', '#btn-step-3-next', 'button:has-text("Next"):visible', 'button[type="submit"]:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
            return True
    return False

async def handle_phone_verification_step(
    page: Page,
    job: ActiveJob,
    update_status_cb: Callable[[str, str, bool, str], Awaitable[None]]
) -> bool:
    """
    Pause automation for human intervention when Google presents phone verification or SMS challenges.
    Leaves browser context fully responsive on the user's desktop.
    """
    logger.info(f"Phone verification challenge detected for job '{job.job_id}'. Pausing for human intervention.")
    job.resume_event.clear()

    await update_status_cb(
        "WAITING_FOR_USER",
        "PHONE_VERIFICATION_REQUIRED",
        True,
        "Phone verification challenge presented. Complete verification in the browser window and click Resume."
    )

    # Pause until user sends resume signal
    await job.resume_event.wait()
    logger.info(f"Job '{job.job_id}' resumed after phone verification.")

    await update_status_cb("RUNNING", "PHONE_VERIFICATION_COMPLETED", False, "")
    await page.wait_for_timeout(1000)
    return True

async def handle_recovery_step(page: Page) -> bool:
    """
    If Google offers an explicit skip/Not now option for optional recovery information, use it.
    Does not invent or submit recovery details.
    """
    logger.info("Executing Step: RECOVERY_INFORMATION (selecting Skip/Not now)")
    for sel in ['button:has-text("Skip"):visible', 'button:has-text("Not now"):visible', '#btn-skip-recovery:visible']:
        btn = page.locator(sel).first
        if await btn.count() > 0 and await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(1000)
            return True

    # If no skip button is visible, try clicking Next if fields are optional
    next_btn = page.locator('button:has-text("Next"):visible, #btn-recovery-next:visible').first
    if await next_btn.count() > 0 and await next_btn.is_visible():
        await next_btn.click()
        await page.wait_for_timeout(1000)
        return True

    return False

async def handle_account_review_step(page: Page) -> bool:
    """
    Handle Review account info (Next) and Terms of Service (click 'I agree').
    """
    logger.info("Executing Step: ACCOUNT_REVIEW & TERMS")
    # 1. Review Info Next
    review_next = page.locator('#btn-review-next:visible, button:has-text("Next"):visible').first
    if await review_next.count() > 0 and await review_next.is_visible():
        await review_next.click()
        await page.wait_for_timeout(1000)

    # 2. Terms I Agree
    agree_btn = page.locator('button:has-text("I agree"):visible, button:has-text("Agree"):visible, #btn-agree-terms:visible').first
    if await agree_btn.count() > 0 and await agree_btn.is_visible():
        await agree_btn.click()
        await page.wait_for_timeout(1500)
        return True

    return False

async def handle_selfie_verification_step(
    page: Page,
    job: ActiveJob,
    update_status_cb: Callable[[str, str, bool, str], Awaitable[None]]
) -> bool:
    """
    If selfie verification offers 'Not now' or 'Skip', click it.
    If mandatory, pause for user intervention.
    """
    logger.info("Executing Step: SELFIE_VERIFICATION")
    skip_btn = page.locator('button:has-text("Not now"):visible, button:has-text("Skip"):visible, #btn-skip-selfie:visible').first
    if await skip_btn.count() > 0 and await skip_btn.is_visible():
        logger.info("Selfie verification optional; clicking 'Not now'.")
        await skip_btn.click()
        await page.wait_for_timeout(1000)
        return True

    # Mandatory challenge
    logger.info(f"Selfie verification mandatory for job '{job.job_id}'. Pausing for user interaction.")
    job.resume_event.clear()
    await update_status_cb(
        "WAITING_FOR_USER",
        "SELFIE_VERIFICATION_REQUIRED",
        True,
        "Mandatory selfie/identity verification presented. Please complete in browser window and click Resume."
    )
    await job.resume_event.wait()
    await update_status_cb("RUNNING", "SELFIE_VERIFICATION_COMPLETED", False, "")
    await page.wait_for_timeout(1000)
    return True

# --- Main Registration Orchestrator Loop ---

async def run_signup(
    page: Page,
    job: ActiveJob,
    update_status_cb: Callable[[str, str, bool, str], Awaitable[None]]
) -> bool:
    """
    Master registration assistance workflow.
    Iteratively detects page state, executes idempotent step handlers,
    pauses for verification challenges, and verifies final account creation.
    """
    job.page = page
    signup_input = job.signup_input or SignupInput(
        first_name=job.first_name,
        last_name=job.last_name,
        password=job.password or "DefaultPass123!"
    )

    target_url = job.target_url or "https://accounts.google.com/signup"
    logger.info(f"Initiating registration assistance workflow at URL: {target_url}")

    await update_status_cb("RUNNING", "NAVIGATING_TO_SIGNUP", False, "")
    await page.goto(target_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)

    max_iterations = 25
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        current_step = await detect_page_step(page)
        logger.info(f"[Step Loop {iteration}] Detected page state: {current_step.value} (URL: {page.url})")

        # 1. Terminal Success Check
        if current_step == RegistrationStep.COMPLETED:
            logger.info(f"Registration confirmed complete for job '{job.job_id}'.")
            job.completed_steps.add(RegistrationStep.FINAL_VERIFICATION.value)
            return True

        # 2. Form Validation Error Handling
        if current_step == RegistrationStep.VALIDATION_ERROR:
            err_text = "Validation error on page. Please resolve in the browser window."
            try:
                alert_elem = page.locator('[role="alert"]:visible, .o6cuMc:visible').first
                if await alert_elem.count() > 0:
                    err_text = f"Form validation error: {await alert_elem.inner_text()}"
            except Exception:
                pass
            logger.warning(f"Validation error encountered: {err_text}")
            job.resume_event.clear()
            await update_status_cb("WAITING_FOR_USER", "VALIDATION_ERROR_DETECTED", True, err_text)
            await job.resume_event.wait()
            await update_status_cb("RUNNING", "RESUMING_AFTER_VALIDATION_ERROR", False, "")
            await page.wait_for_timeout(1000)
            continue

        # 3. Dispatch specific step handlers idempotently
        await update_status_cb("RUNNING", f"EXECUTING_{current_step.value}", False, "")

        if current_step == RegistrationStep.NAME:
            await handle_name_step(page, signup_input)
            job.completed_steps.add(RegistrationStep.NAME.value)

        elif current_step == RegistrationStep.BIRTHDAY_GENDER:
            await handle_birthday_gender_step(page, signup_input)
            job.completed_steps.add(RegistrationStep.BIRTHDAY_GENDER.value)

        elif current_step == RegistrationStep.USERNAME:
            await handle_username_step(page, signup_input, job)
            job.completed_steps.add(RegistrationStep.USERNAME.value)

        elif current_step == RegistrationStep.PASSWORD:
            await handle_password_step(page, signup_input)
            job.completed_steps.add(RegistrationStep.PASSWORD.value)

        elif current_step == RegistrationStep.PHONE_VERIFICATION:
            await handle_phone_verification_step(page, job, update_status_cb)
            job.completed_steps.add(RegistrationStep.PHONE_VERIFICATION.value)

        elif current_step == RegistrationStep.RECOVERY_INFORMATION:
            await handle_recovery_step(page)
            job.completed_steps.add(RegistrationStep.RECOVERY_INFORMATION.value)

        elif current_step == RegistrationStep.ACCOUNT_REVIEW:
            await handle_account_review_step(page)
            job.completed_steps.add(RegistrationStep.ACCOUNT_REVIEW.value)

        elif current_step == RegistrationStep.SELFIE_VERIFICATION:
            await handle_selfie_verification_step(page, job, update_status_cb)
            job.completed_steps.add(RegistrationStep.SELFIE_VERIFICATION.value)

        else:
            # Step UNKNOWN: Pause for human supervision rather than blind failure
            logger.warning(f"Unrecognized page state at {page.url}. Pausing for human intervention.")
            job.resume_event.clear()
            await update_status_cb(
                "WAITING_FOR_USER",
                "UNRECOGNIZED_PAGE_DETECTED",
                True,
                f"Page requires manual action. Current URL: {page.url}"
            )
            await job.resume_event.wait()
            await update_status_cb("RUNNING", "RESUMED_FROM_MANUAL_INTERACTION", False, "")
            await page.wait_for_timeout(1000)

        # Check if page transitioned to completed state
        post_step = await detect_page_step(page)
        if post_step == RegistrationStep.COMPLETED:
            logger.info("Post-action check confirmed account registration completed.")
            job.completed_steps.add(RegistrationStep.FINAL_VERIFICATION.value)
            return True

    logger.warning(f"Registration workflow exceeded max iterations without confirmed completion.")
    return False
