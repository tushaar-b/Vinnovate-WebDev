import time
from dataclasses import dataclass
from typing import Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from app.services.security import validate_target_url, SecurityValidationError
from app.services.normalizer import normalize_text, calculate_content_hash


@dataclass
class CaptureResult:
    title: str
    final_url: str
    visible_text: str
    normalized_text: str
    content_hash: str
    screenshot_bytes: bytes
    http_status: int
    duration_ms: int


class BrowserCaptureError(Exception):
    def __init__(self, message: str, error_code: str = "CHECK_FAILED", http_status: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status


def capture_page(url: str, is_fixture: bool = False, timeout_ms: int = 20000) -> CaptureResult:
    """
    Captures a target webpage using headless Playwright Chromium:
    - Validates target URL against SSRF policy
    - Intercepts subresources and redirects to prevent SSRF bypass / DNS rebinding
    - Bounded navigation timeout (default 20s) with domcontentloaded
    - Extracts title, final URL, visible text, content hash, and full screenshot
    - Guarantees browser, page, and context resources are always closed.
    """
    # Pre-navigation URL safety check
    is_safe, error_reason = validate_target_url(url, is_fixture_check=is_fixture)
    if not is_safe:
        raise SecurityValidationError(error_reason, code="BLOCKED_TARGET")

    start_time = time.time()
    playwright_instance = None
    browser = None
    context = None
    page = None

    try:
        playwright_instance = sync_playwright().start()
        # Launch Chromium headless with security sandboxing
        browser = playwright_instance.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check"],
        )
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="WebsiteChangeDetector/1.0 (+precision-observability-engine)",
            accept_downloads=False,
            ignore_https_errors=False,
        )
        page = context.new_page()

        # Intercept and validate all subresource requests and redirects
        redirect_blocked = []

        def route_interceptor(route):
            request = route.request
            req_url = request.url

            # Verify each request URL against SSRF rules
            safe, reason = validate_target_url(req_url, is_fixture_check=is_fixture)
            if not safe:
                redirect_blocked.append((req_url, reason))
                route.abort("blockedbyclient")
            else:
                route.continue_()

        page.route("**/*", route_interceptor)

        # Track navigation responses
        response_status = [200]

        def on_response(response):
            if response.request.is_navigation_request():
                response_status[0] = response.status
                # Check redirects
                if response.status in (301, 302, 303, 307, 308):
                    loc = response.headers.get("location")
                    if loc:
                        safe, reason = validate_target_url(loc, is_fixture_check=is_fixture)
                        if not safe:
                            redirect_blocked.append((loc, reason))

        page.on("response", on_response)

        # Navigate to target
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if response:
                response_status[0] = response.status
        except PlaywrightTimeoutError:
            raise BrowserCaptureError(
                f"Navigation timed out after {timeout_ms / 1000} seconds.",
                error_code="TIMEOUT",
            )
        except PlaywrightError as e:
            if redirect_blocked:
                blocked_url, reason = redirect_blocked[0]
                raise SecurityValidationError(
                    f"Redirect or request to prohibited destination '{blocked_url}' was blocked: {reason}",
                    code="BLOCKED_TARGET",
                )
            raise BrowserCaptureError(f"Navigation error: {str(e)}", error_code="NAVIGATION_ERROR")

        if redirect_blocked:
            blocked_url, reason = redirect_blocked[0]
            raise SecurityValidationError(
                f"Prohibited network target was blocked: {reason}",
                code="BLOCKED_TARGET",
            )

        # Bounded settle pause
        page.wait_for_timeout(1000)

        # Check for HTTP error status
        final_http_status = response_status[0]
        if final_http_status >= 500:
            raise BrowserCaptureError(
                f"Web server returned HTTP {final_http_status} server error.",
                error_code="HTTP_5XX",
                http_status=final_http_status,
            )
        elif final_http_status == 403 or final_http_status == 401:
            raise BrowserCaptureError(
                f"Web server denied access with HTTP {final_http_status}.",
                error_code="BLOCKED",
                http_status=final_http_status,
            )
        elif final_http_status >= 400:
            raise BrowserCaptureError(
                f"Web page returned client error HTTP {final_http_status}.",
                error_code=f"HTTP_{final_http_status}",
                http_status=final_http_status,
            )

        # Extract title and visible text
        title = page.title() or ""
        final_url = page.url or url

        # Extract visible innerText from document body
        raw_text = page.evaluate("() => document.body ? document.body.innerText : ''") or ""
        normalized = normalize_text(raw_text)
        content_hash = calculate_content_hash(normalized)

        # Capture screenshot
        screenshot_bytes = page.screenshot(type="png", full_page=False)

        duration_ms = int((time.time() - start_time) * 1000)

        return CaptureResult(
            title=title,
            final_url=final_url,
            visible_text=raw_text,
            normalized_text=normalized,
            content_hash=content_hash,
            screenshot_bytes=screenshot_bytes,
            http_status=final_http_status,
            duration_ms=duration_ms,
        )

    finally:
        # Guaranteed cleanup of all Playwright browser resources
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright_instance is not None:
            try:
                playwright_instance.stop()
            except Exception:
                pass
