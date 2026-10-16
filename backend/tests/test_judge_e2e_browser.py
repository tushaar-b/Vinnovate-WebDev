import os
import time
import pytest
from playwright.sync_api import sync_playwright

FRONTEND_URL = os.getenv("TEST_FRONTEND_URL", "http://127.0.0.1:5173")


def test_judge_workspace_e2e_workflow():
    """
    Requirement 9: Real Browser End-to-End Test:
    1. Open website in clean browser context (no credentials).
    2. Enter Judge Workspace via "Explore Judge Workspace".
    3. Add a public website (e.g. https://example.com).
    4. Trigger Check Now.
    5. Wait for genuine check result (BASELINE).
    6. Verify screenshot naturalWidth and naturalHeight > 0.
    7. Refresh the browser and verify session retains access to own monitor.
    8. Open a second independent browser context; verify it CANNOT access the first judge's monitor.
    9. Verify Admin Login is still available and working.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # Context 1: Judge Session A
        # -------------------------------------------------------------
        ctx_a = browser.new_context()
        page_a = ctx_a.new_page()

        # Step 1: Open website landing page
        page_a.goto(FRONTEND_URL, wait_until="networkidle")

        # Step 2: Verify Entry Screen & Click "Explore Judge Workspace"
        judge_btn = page_a.locator("button:has-text('Explore Judge Workspace')")
        assert judge_btn.is_visible(), "Entry screen must display 'Explore Judge Workspace'"
        judge_btn.click()

        # Verify Judge Workspace loaded
        page_a.wait_for_selector("h1:has-text('Interactive Evaluation Workspace')", timeout=10000)
        assert page_a.locator("text=Temporary evaluation session").is_visible()

        # Step 3: Add Website (https://example.com)
        add_btn = page_a.locator("button:has-text('Add Website')")
        if not add_btn.is_visible():
            add_btn = page_a.locator("button:has-text('Add First Website')")
        add_btn.click()

        page_a.wait_for_selector("#modal-title", timeout=5000)
        page_a.locator("input[placeholder*='e.g.']").fill("Example Test")
        page_a.locator("input[type='url']").fill("https://example.com")
        page_a.locator("button[type='submit']").click()

        # Wait for Monitor Details view to open
        page_a.wait_for_selector("button:has-text('Snapshot Overview')", timeout=10000)
        current_hash = page_a.evaluate("() => window.location.hash")
        assert "/judge/monitors/" in current_hash
        monitor_id = current_hash.split("/monitors/")[1]
        assert monitor_id, "Monitor ID should be present in URL hash"

        # Step 4: Trigger Check Now
        check_now_btn = page_a.locator("button:has-text('Check Now')")
        assert check_now_btn.is_visible()
        check_now_btn.click()

        # Step 5: Wait for genuine Playwright check run to finish with BASELINE
        # Polling check status until baseline or completed
        page_a.wait_for_function(
            "() => document.body.innerText.includes('BASELINE') || document.body.innerText.includes('OK')",
            timeout=30000,
        )

        # Step 6: Verify screenshot renders with naturalWidth & naturalHeight > 0
        img_locator = page_a.locator("img[alt^='Screenshot for']")
        page_a.wait_for_selector("img[alt^='Screenshot for']", timeout=15000)
        page_a.wait_for_function(
            "() => { const img = document.querySelector(\"img[alt^='Screenshot for']\"); return img && img.complete && img.naturalWidth > 0 && img.naturalHeight > 0; }",
            timeout=15000,
        )
        w = img_locator.evaluate("el => el.naturalWidth")
        h = img_locator.evaluate("el => el.naturalHeight")
        assert w > 0, f"naturalWidth must be > 0, got {w}"
        assert h > 0, f"naturalHeight must be > 0, got {h}"

        # Step 7: Refresh browser in Context A and verify session retains access
        page_a.reload(wait_until="networkidle")
        page_a.wait_for_selector("button:has-text('Snapshot Overview')", timeout=20000)
        assert page_a.locator("button:has-text('Snapshot Overview')").is_visible(), "Session should retain access after refresh"

        # -------------------------------------------------------------
        # Context 2: Independent Browser Context B (Judge B)
        # -------------------------------------------------------------
        ctx_b = browser.new_context()
        page_b = ctx_b.new_page()

        # Judge B tries to access Judge A's monitor directly
        page_b.goto(f"{FRONTEND_URL}/#/judge/monitors/{monitor_id}", wait_until="networkidle")
        # Wait for 404 / error state to render
        page_b.wait_for_function(
            "() => document.body.innerText.toLowerCase().includes('not found') || document.body.innerText.includes('Return to Dashboard') || document.body.innerText.includes('Failed')",
            timeout=15000,
        )
        assert "not found" in page_b.inner_text("body").lower() or "return to dashboard" in page_b.inner_text("body").lower(), "Judge B must not be able to access Judge A's monitor"

        # -------------------------------------------------------------
        # Admin Login Verification
        # -------------------------------------------------------------
        ctx_admin = browser.new_context()
        page_admin = ctx_admin.new_page()
        page_admin.goto(f"{FRONTEND_URL}/#admin", wait_until="networkidle")
        assert page_admin.locator("input[type='password']").is_visible(), "Admin Login password field must be visible"

        browser.close()
