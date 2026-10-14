import json
import base64
import hashlib
import time
from typing import Optional, Tuple, Dict, Any, List
from playwright.sync_api import sync_playwright

from app.redis_client import redis_client
from app.services.browser import CaptureResult, normalize_text, calculate_content_hash, BrowserCaptureError


FETCH_COALESCE_WINDOW_SECONDS = 30


def get_fetch_cache_key(canonical_url: str) -> str:
    """Generates a stable cache key for a canonical URL."""
    url_hash = hashlib.sha256(canonical_url.strip().encode("utf-8")).hexdigest()
    return f"cache:fetch:{url_hash}"


class SharedFetchService:
    """
    Manages bounded coalescing and safe reuse of browser page fetches
    for compatible monitors watching the same canonical URL.
    """

    def __init__(self, redis_conn=None):
        self.r = redis_conn or redis_client

    def is_compatible_for_shared_fetch(self, monitor_a, monitor_b) -> bool:
        """
        Determines if two monitors have compatible fetch requirements to share a captured render:
        - Must share identical canonical_url
        - Both must be enabled public HTTP/HTTPS monitors
        - Neither requires sensitive user-specific authentication or custom session cookies
        """
        if not monitor_a or not monitor_b:
            return False
        if monitor_a.canonical_url != monitor_b.canonical_url:
            return False
        return True

    def clear_cache(self, canonical_url: str) -> None:
        """Clears the cached fetch for a canonical URL."""
        cache_key = get_fetch_cache_key(canonical_url)
        self.r.delete(cache_key)

    def store_cached_fetch(
        self,
        canonical_url: str,
        result: CaptureResult,
        raw_html: str,
        ttl_seconds: int = FETCH_COALESCE_WINDOW_SECONDS,
    ) -> None:
        """
        Caches a successful raw capture (screenshot, HTML DOM, title, status) in Redis.
        """
        cache_key = get_fetch_cache_key(canonical_url)
        data = {
            "canonical_url": canonical_url,
            "title": result.title,
            "final_url": result.final_url,
            "http_status": result.http_status,
            "duration_ms": result.duration_ms,
            "raw_html": raw_html,
            "screenshot_b64": base64.b64encode(result.screenshot_bytes).decode("ascii"),
            "elements": result.elements or [],
            "cached_at": time.time(),
        }
        try:
            self.r.set(cache_key, json.dumps(data), ex=ttl_seconds)
        except Exception:
            pass

    def get_cached_fetch(self, canonical_url: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a fresh cached fetch for a canonical URL if within the coalescing window.
        """
        cache_key = get_fetch_cache_key(canonical_url)
        try:
            raw = self.r.get(cache_key)
            if not raw:
                return None
            data = json.loads(raw)
            data["screenshot_bytes"] = base64.b64decode(data["screenshot_b64"].encode("ascii"))
            return data
        except Exception:
            return None

    def evaluate_monitor_rules_on_dom(
        self,
        raw_html: str,
        rules: Optional[List[Any]] = None,
    ) -> Tuple[str, str, str]:
        """
        Evaluates a monitor's independent watch and ignore selectors against captured DOM HTML.
        Does not perform any network requests.
        Returns: (visible_text, normalized_text, content_hash)
        Raises BrowserCaptureError if any configured watch selector is missing in the DOM.
        """
        watch_selectors = [
            (r["css_selector"] if isinstance(r, dict) else r.css_selector).strip()
            for r in (rules or [])
            if (
                str(r.get("rule_type", "") if isinstance(r, dict) else getattr(r, "rule_type", "")).lower().endswith("watch")
            )
            and (r["css_selector"] if isinstance(r, dict) else r.css_selector).strip()
        ]
        ignore_selectors = [
            (r["css_selector"] if isinstance(r, dict) else r.css_selector).strip()
            for r in (rules or [])
            if (
                str(r.get("rule_type", "") if isinstance(r, dict) else getattr(r, "rule_type", "")).lower().endswith("ignore")
            )
            and (r["css_selector"] if isinstance(r, dict) else r.css_selector).strip()
        ]

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage", "--no-first-run", "--no-default-browser-check"],
            )
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            # Load the cached DOM content locally without network activity
            page.set_content(raw_html, wait_until="domcontentloaded")

            # Validate watch selectors
            for ws in watch_selectors:
                try:
                    count = page.locator(ws).count()
                    if count == 0:
                        browser.close()
                        raise BrowserCaptureError(
                            f"Watched element selector '{ws}' not found on target page.",
                            error_code="MISSING_SELECTOR",
                        )
                except BrowserCaptureError:
                    raise
                except Exception as e:
                    browser.close()
                    raise BrowserCaptureError(f"Invalid watch selector '{ws}': {str(e)}", error_code="MISSING_SELECTOR")

            # Extract clean text with watch/ignore rules applied
            extraction_js = """
            ({ watchRules, ignoreRules }) => {
                function extractCleanText(node) {
                    if (!node) return "";
                    const clone = node.cloneNode(true);
                    if (ignoreRules && ignoreRules.length > 0) {
                        for (const ig of ignoreRules) {
                            try {
                                const ignNodes = clone.querySelectorAll(ig);
                                ignNodes.forEach(el => el.remove());
                            } catch (e) {}
                        }
                    }
                    return clone.innerText || "";
                }

                if (watchRules && watchRules.length > 0) {
                    const collected = [];
                    for (const ws of watchRules) {
                        try {
                            const elements = document.querySelectorAll(ws);
                            elements.forEach(el => {
                                const t = extractCleanText(el);
                                if (t) collected.push(t);
                            });
                        } catch (e) {}
                    }
                    return collected.join("\\n");
                } else {
                    return extractCleanText(document.body);
                }
            }
            """
            raw_text = page.evaluate(extraction_js, {"watchRules": watch_selectors, "ignoreRules": ignore_selectors}) or ""
            browser.close()

        normalized = normalize_text(raw_text)
        content_hash = calculate_content_hash(normalized)
        return raw_text, normalized, content_hash


shared_fetch_service = SharedFetchService()
