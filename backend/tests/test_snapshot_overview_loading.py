import os
import time
import pytest
from playwright.sync_api import sync_playwright

FRONTEND_URL = os.getenv("TEST_FRONTEND_URL", "http://127.0.0.1:5173")
TARGET_MONITOR_ID = "1d57e537-963a-4f91-8f6f-283594852fde"


def test_snapshot_overview_initial_screenshot_loading():
    """
    Regression test verifying:
    1. Starts from a fresh unauthenticated browser context.
    2. Signs in.
    3. Opens a monitor with an existing screenshot.
    4. Navigates directly to Snapshot Overview.
    5. Verifies the screenshot loads with valid image dimensions, without opening any comparison tab.
    6. Refreshes the page and verifies it again.
    7. Opens Visual Overlay Diff and verifies it still works.
    8. Returns to Snapshot Overview and verifies continued functionality.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1. Fresh unauthenticated browser context
        context = browser.new_context()
        page = context.new_page()

        # 2. Open frontend and sign in
        page.goto(FRONTEND_URL, wait_until="networkidle")
        password_input = page.locator("input[type='password']")
        if password_input.is_visible():
            password_input.fill("admin")
            page.locator("button[type='submit']").click()
            page.wait_for_selector("header", timeout=5000)

        # 3. Open monitor directly with an existing screenshot via hash route
        page.goto(f"{FRONTEND_URL}/#monitors/{TARGET_MONITOR_ID}", wait_until="networkidle")
        page.wait_for_timeout(1000)

        # 4 & 5. Verify the screenshot loads with valid image dimensions directly on Snapshot Overview
        # (WITHOUT visiting any comparison tab)
        page.wait_for_selector("button:has-text('Snapshot Overview')", timeout=10000)
        overview_tab = page.locator("button:has-text('Snapshot Overview')")
        assert overview_tab.is_visible()

        img_locator = page.locator("img[alt^='Screenshot for']")
        page.wait_for_selector("img[alt^='Screenshot for']", timeout=10000)

        # Verify image dimensions
        src = img_locator.get_attribute("src")
        assert src, "Screenshot img element missing src attribute"
        assert "screenshot" in src, f"Expected screenshot URL, got {src}"

        # Wait for natural dimensions to be non-zero
        page.wait_for_function("() => { const img = document.querySelector(\"img[alt^='Screenshot for']\"); return img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0; }", timeout=10000)

        natural_width = img_locator.evaluate("el => el.naturalWidth")
        natural_height = img_locator.evaluate("el => el.naturalHeight")
        assert natural_width > 0, f"naturalWidth should be > 0, got {natural_width}"
        assert natural_height > 0, f"naturalHeight should be > 0, got {natural_height}"

        # 6. Refresh the page and verify screenshot loads again directly
        page.reload(wait_until="networkidle")
        page.wait_for_selector("img[alt^='Screenshot for']", timeout=10000)
        page.wait_for_function("() => { const img = document.querySelector(\"img[alt^='Screenshot for']\"); return img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0; }", timeout=10000)

        refreshed_width = img_locator.evaluate("el => el.naturalWidth")
        refreshed_height = img_locator.evaluate("el => el.naturalHeight")
        assert refreshed_width > 0, f"refreshed naturalWidth should be > 0, got {refreshed_width}"
        assert refreshed_height > 0, f"refreshed naturalHeight should be > 0, got {refreshed_height}"

        # 7. Open Visual Overlay Diff and verify it works
        compare_tab = page.locator("button:has-text('Compare Versions')")
        compare_tab.click()
        page.wait_for_selector("button:has-text('Visual Overlay Diff')", timeout=5000)

        visual_diff_button = page.locator("button:has-text('Visual Overlay Diff')")
        visual_diff_button.click()
        page.wait_for_selector("img[alt='Visual diff overlay']", timeout=10000)
        diff_img = page.locator("img[alt='Visual diff overlay']")
        assert diff_img.is_visible()

        # 8. Return to Snapshot Overview and verify continued functionality
        overview_tab.click()
        page.wait_for_selector("img[alt^='Screenshot for']", timeout=5000)
        page.wait_for_function("() => { const img = document.querySelector(\"img[alt^='Screenshot for']\"); return img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0; }", timeout=5000)

        final_width = img_locator.evaluate("el => el.naturalWidth")
        final_height = img_locator.evaluate("el => el.naturalHeight")
        assert final_width > 0
        assert final_height > 0

        browser.close()
