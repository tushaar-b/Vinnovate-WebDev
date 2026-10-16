#!/usr/bin/env python3
"""Read-only public deployment checks for Website Change Detector."""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse


def request(url, timeout, method="GET", headers=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read(2_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read(2_000_000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--backend-url", required=True)
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args()
    front = args.frontend_url.rstrip("/")
    back = args.backend_url.rstrip("/")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))

    try:
        status, headers, body = request(front, args.timeout)
        html = body.decode("utf-8", "replace")
        check("HTTPS frontend response", urlparse(front).scheme == "https" and status == 200,
              f"HTTP {status}; content-type={headers.get('Content-Type', 'unknown')}")
        check("Frontend application shell", status == 200 and "<html" in html.lower() and "<div" in html.lower(),
              "response contains HTML shell")
    except Exception as exc:
        check("HTTPS frontend response", False, type(exc).__name__)
        check("Frontend application shell", False, "frontend could not be read")

    health_data = {}
    try:
        status, _, body = request(back + "/api/health", args.timeout)
        try:
            health_data = json.loads(body)
        except Exception:
            pass
        healthy = status == 200 and health_data.get("status") == "ok"
        check("Backend health", healthy, f"HTTP {status}; database={health_data.get('database', 'unknown')}; redis={health_data.get('redis', 'unknown')}")
        check("PostgreSQL and Redis health", healthy and health_data.get("database") == "ok" and health_data.get("redis") == "ok",
              f"database={health_data.get('database', 'unknown')}; redis={health_data.get('redis', 'unknown')}")
        leaked = bool(re.search(r"(?i)(password|webhook_url|bot_token|secret|api_key)\s*[:=]\s*[^\s\"']+", body.decode("utf-8", "replace")))
        check("No obvious credentials in public health response", not leaked)
    except Exception as exc:
        check("Backend health", False, type(exc).__name__)
        check("PostgreSQL and Redis health", False, "health endpoint unavailable")
        check("No obvious credentials in public health response", False, "health endpoint unavailable")

    try:
        status, _, body = request(back + "/api/monitors", args.timeout)
        protected = status in (401, 403)
        check("Administrative API access protection", protected,
              f"GET /api/monitors returned HTTP {status}; expected 401 or 403")
        sensitive = ("webhook_url", "bot_token", "smtp_password", "ENCRYPTION_KEY")
        text = body.decode("utf-8", "replace")
        check("No obvious credentials in monitor response", not any(x.lower() in text.lower() for x in sensitive))
    except Exception as exc:
        check("Administrative API access protection", False, type(exc).__name__)
        check("No obvious credentials in monitor response", False, "API unavailable")

    # Public Judge Session Creation & Isolation Verification
    judge_token = None
    try:
        status, _, body = request(back + "/api/judge/session", args.timeout, method="POST", headers={"Content-Type": "application/json"})
        judge_data = {}
        try:
            judge_data = json.loads(body)
        except Exception:
            pass
        judge_token = judge_data.get("token")
        check("Public judge session creation", status == 200 and bool(judge_token),
              f"HTTP {status}; session_id={judge_data.get('session_id') or judge_data.get('judge_session_id', 'none')}")
    except Exception as exc:
        check("Public judge session creation", False, type(exc).__name__)

    if judge_token:
        try:
            status, _, body = request(
                back + "/api/judge/session/status",
                args.timeout,
                headers={"Authorization": f"Bearer {judge_token}"},
            )
            status_data = {}
            try:
                status_data = json.loads(body)
            except Exception:
                pass
            check("Judge session status verification", status == 200 and (status_data.get("active") or status_data.get("authenticated")),
                  f"HTTP {status}; active={status_data.get('active')}")
        except Exception as exc:
            check("Judge session status verification", False, type(exc).__name__)

        try:
            # Judge session must be blocked from admin settings with 403 Forbidden
            status, _, _ = request(
                back + "/api/settings/notifications",
                args.timeout,
                headers={"Authorization": f"Bearer {judge_token}"},
            )
            check("Judge administrative isolation (403 Forbidden on admin settings)", status == 403,
                  f"GET /api/settings/notifications returned HTTP {status}; expected 403")
        except Exception as exc:
            check("Judge administrative isolation (403 Forbidden on admin settings)", False, type(exc).__name__)

    # A CORS preflight from the actual frontend origin should be explicitly allowed.
    origin = f"{urlparse(front).scheme}://{urlparse(front).netloc}"
    try:
        status, headers, _ = request(back + "/api/health", args.timeout, "OPTIONS", {
            "Origin": origin, "Access-Control-Request-Method": "GET",
        })
        allowed = headers.get("Access-Control-Allow-Origin") in (origin, "*")
        check("Frontend origin CORS", status in (200, 204) and allowed,
              f"HTTP {status}; allow-origin={headers.get('Access-Control-Allow-Origin', 'absent')}")
    except Exception as exc:
        check("Frontend origin CORS", False, type(exc).__name__)

    # Real browser check when Playwright is installed; no page mutation is performed.
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            console_errors = []
            page.on("pageerror", lambda error: console_errors.append(str(error)))
            response = page.goto(front, wait_until="domcontentloaded", timeout=int(args.timeout * 1000))
            page.wait_for_timeout(1000)
            browser.close()
        check("Browser access", response is not None and response.status == 200,
              f"HTTP {response.status if response else 'none'}")
        check("Critical browser page errors", not console_errors,
              f"{len(console_errors)} page error(s)")
    except ImportError:
        check("Browser access", False, "Playwright Python package is unavailable")
        check("Critical browser page errors", False, "Playwright Python package is unavailable")
    except Exception as exc:
        check("Browser access", False, type(exc).__name__)
        check("Critical browser page errors", False, type(exc).__name__)

    failed = len([x for x in results if not x])
    print(f"\nSummary: {len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
