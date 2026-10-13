from datetime import datetime, timezone
from fastapi import APIRouter, Response, status, Query
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/fixture", tags=["Test Fixtures"])


@router.get("/product", response_class=HTMLResponse)
def fixture_product(
    price: str = Query("4999", description="Product price"),
    title: str = Query("AcuTime Precision Chronometer 400", description="Product title"),
    availability: str = Query("In Stock (Ships in 24 hours)", description="Product availability"),
    banner: str = Query("Special Edition Launch - Limited Availability", description="Banner text"),
    timestamp: str = Query("2026-10-14 00:00:00 UTC", description="Rendered noise timestamp"),
    visitors: str = Query("142", description="Visitor counter noise"),
):
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #fafafa; color: #111; margin: 0; padding: 40px; }}
        .container {{ max-width: 800px; margin: 0 auto; background: #fff; padding: 32px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .banner {{ background: #eff6ff; color: #1d4ed8; padding: 12px 16px; border-radius: 8px; font-size: 14px; margin-bottom: 24px; }}
        .timestamp {{ color: #6b7280; font-size: 12px; margin-top: 4px; }}
        .visitor-counter {{ color: #9333ea; font-size: 12px; margin-top: 4px; font-weight: 500; }}
        h1 {{ font-size: 28px; margin: 0 0 16px 0; color: #0f172a; }}
        .price {{ font-size: 32px; font-weight: 700; color: #16a34a; margin-bottom: 16px; }}
        .description {{ font-size: 16px; line-height: 1.6; color: #334155; margin-bottom: 24px; }}
        .stock {{ display: inline-block; padding: 6px 12px; border-radius: 9999px; background: #dcfce7; color: #15803d; font-size: 14px; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="banner" id="banner">
            <div>{banner}</div>
            <div class="timestamp" id="timestamp">System Clock: {timestamp}</div>
            <div class="visitor-counter" id="visitor-counter">Live Viewers: {visitors}</div>
        </div>
        <h1 id="product-title">{title}</h1>
        <div class="price" id="price">${price}</div>
        <div class="stock" id="stock-status">{availability}</div>
        <div class="description" id="product-desc">
            Engineered with aerospace-grade titanium and precision Swiss movement. 
            Calibrated for extreme environments and high durability.
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)



@router.get("/error500")
def fixture_error500():
    return Response(content="Internal Server Error Simulated", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.get("/blocked")
def fixture_blocked():
    return Response(content="Simulated Access Forbidden / Anti-Bot Shield", status_code=status.HTTP_403_FORBIDDEN)


@router.get("/redirect-safe")
def fixture_redirect_safe():
    return RedirectResponse(url="/fixture/product", status_code=status.HTTP_302_FOUND)


@router.get("/redirect-unsafe")
def fixture_redirect_unsafe():
    # Malicious redirect targeting AWS metadata
    return RedirectResponse(url="http://169.254.169.254/latest/meta-data/", status_code=status.HTTP_302_FOUND)
