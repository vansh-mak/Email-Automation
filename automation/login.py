import logging
from typing import Callable, Awaitable
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
from services.job_registry import ActiveJob

logger = logging.getLogger(__name__)

async def run_login(
    page: Page,
    job: ActiveJob,
    login_url: str,
    update_status_cb: Callable[[str, str, bool, str], Awaitable[None]]
) -> bool:
    """
    Execute login workflow to verify access with the newly created credentials.
    """
    logger.info(f"Navigating to login URL: {login_url}")
    await update_status_cb("RUNNING", "NAVIGATING_TO_LOGIN", False, "")
    await page.goto(login_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(1000)

    # 1. Fill Username / Email
    await update_status_cb("RUNNING", "ENTERING_LOGIN_USERNAME", False, "")
    for sel in ['#login_username', 'input[type="email"]:visible', 'input[name*="user" i]:visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(job.username)
            break

    for sel in ['#btn-login-next', 'button:has-text("Next"):visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(1000)
            break

    # 2. Fill Password
    await update_status_cb("RUNNING", "ENTERING_LOGIN_PASSWORD", False, "")
    for sel in ['#login_password', 'input[type="password"]:visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.fill(job.password)
            break

    for sel in ['#btn-login-submit', 'button:has-text("Sign in"):visible', 'button:has-text("Log in"):visible', 'button[type="submit"]:visible']:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            await loc.click()
            await page.wait_for_timeout(1500)
            break

    # 3. Check for login success indicators
    success_indicators = [
        '#inbox-view',
        '#login-success',
        'text="Inbox"',
        'text="Signed in as"'
    ]

    for sel in success_indicators:
        loc = page.locator(sel).first
        if await loc.count() > 0 and await loc.is_visible():
            logger.info(f"Login verified successfully for user '{job.username}'")
            return True

    if "login" not in page.url.lower() and "signin" not in page.url.lower():
        return True

    return False
