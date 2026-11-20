import logging
from typing import Tuple, Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext, Page
from config import settings

logger = logging.getLogger(__name__)

class BrowserManager:
    """Manages the lifecycle of Playwright browser instances, contexts, and pages."""

    @staticmethod
    async def create_session(headless: Optional[bool] = None) -> Tuple[Playwright, Browser, BrowserContext, Page]:
        """
        Launch a Chromium browser session with standard desktop viewport and locale.
        """
        is_headless = settings.HEADLESS if headless is None else headless
        logger.info(f"Launching Chromium browser (headless={is_headless})...")

        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=is_headless,
            slow_mo=50  # Modest humanized pacing
        )

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="en-US"
        )

        page = await context.new_page()
        page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)

        return p, browser, context, page

    @staticmethod
    async def close_session(
        p: Optional[Playwright],
        browser: Optional[Browser],
        context: Optional[BrowserContext],
        page: Optional[Page]
    ) -> None:
        """Safely close page, context, browser, and playwright instance."""
        try:
            if page and not page.is_closed():
                await page.close()
        except Exception as e:
            logger.debug(f"Error closing page: {e}")

        try:
            if context:
                await context.close()
        except Exception as e:
            logger.debug(f"Error closing context: {e}")

        try:
            if browser:
                await browser.close()
        except Exception as e:
            logger.debug(f"Error closing browser: {e}")

        try:
            if p:
                await p.stop()
        except Exception as e:
            logger.debug(f"Error stopping playwright: {e}")

        logger.info("Browser session resources released.")
