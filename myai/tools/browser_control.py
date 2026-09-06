"""Small, optional Playwright browser-control tool."""
from pathlib import Path


class BrowserUnavailable(RuntimeError):
    """Raised when Playwright or its browser binaries are unavailable."""


class BrowserControl:
    def __init__(self, headless=True):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    def _page_or_start(self):
        if self._page is not None:
            return self._page
        try:
            from playwright.sync_api import Error, sync_playwright
        except ImportError as exc:
            raise BrowserUnavailable(
                "Playwright is not installed. Install dependencies and run "
                "'playwright install'."
            ) from exc
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=self.headless)
            self._page = self._browser.new_page()
        except (Error, OSError) as exc:
            self.close()
            raise BrowserUnavailable(
                "Playwright browser binaries are unavailable. Run 'playwright install'."
            ) from exc
        return self._page

    def navigate(self, url):
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are supported")
        page = self._page_or_start()
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        return {"url": page.url, "title": page.title(), "text": page.locator("body").inner_text()}

    def take_screenshot(self, filepath):
        path = Path(filepath).resolve()
        page = self._page_or_start()
        page.screenshot(path=str(path), full_page=True)
        return str(path)

    def click_and_type(self, selector, text):
        if not isinstance(selector, str) or not selector:
            raise ValueError("selector must be a non-empty string")
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        page = self._page_or_start()
        page.locator(selector).click()
        page.locator(selector).fill(text)
        return {"url": page.url, "selector": selector}

    def close(self):
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = self._playwright = self._page = None


_browser = BrowserControl()


def navigate(url):
    return _browser.navigate(url)


def take_screenshot(filepath):
    return _browser.take_screenshot(filepath)


def click_and_type(selector, text):
    return _browser.click_and_type(selector, text)
