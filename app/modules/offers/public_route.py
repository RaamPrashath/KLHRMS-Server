from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.offers import service
from app.shared.database import get_db

router = APIRouter(prefix="/public/offers", tags=["public-offers"])


def _response_page(message: str, success: bool = True) -> str:
    """Build a neat self-contained HTML page for offer accept / reject responses."""
    lower = message.lower()

    if "accepted" in lower:
        title = "Offer Accepted"
        heading = "Offer Accepted"
        detail = "Your acceptance has been submitted successfully."
        show_check = True
    elif "rejected" in lower:
        title = "Offer Rejected"
        heading = "Offer Rejected"
        detail = "We wish you all the best for your future endeavors."
        show_check = True
    elif "expired" in lower:
        title = "Offer Expired"
        heading = "Offer Expired"
        detail = "This offer is no longer valid as it has expired."
        show_check = False
    elif "responded" in lower:
        title = "Already Responded"
        heading = "Already Responded"
        detail = "You have already responded to this offer."
        show_check = True
    elif "active" in lower or "withdrawn" in lower:
        title = "Offer No Longer Active"
        heading = "Offer No Longer Active"
        detail = message
        show_check = False
    else:
        title = "Offer Response"
        heading = message
        detail = ""
        show_check = success

    icon_svg = (
        """
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="32" cy="32" r="28" fill="#16a34a"/>
          <path d="M22 34l7 7 14-16" stroke="#fff" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """
        if show_check
        else """
        <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="32" cy="32" r="28" fill="#f59e0b"/>
          <path d="M24 24l16 16M40 24l-16 16" stroke="#fff" stroke-width="4" stroke-linecap="round"/>
        </svg>
        """
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f0 100%);
      padding: 24px;
    }}
    .card {{
      background: #fff;
      border-radius: 20px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08), 0 1px 4px rgba(0,0,0,0.04);
      padding: 48px 40px;
      max-width: 460px;
      width: 100%;
      text-align: center;
    }}
    .icon {{ margin-bottom: 24px; }}
    h1 {{
      font-size: 28px;
      font-weight: 700;
      color: #1a1a2e;
      margin-bottom: 12px;
      letter-spacing: -0.02em;
    }}
    p {{
      font-size: 16px;
      color: #5b5b6b;
      line-height: 1.6;
    }}
    .footer {{
      margin-top: 32px;
      padding-top: 24px;
      border-top: 1px solid #f0f0f5;
      font-size: 13px;
      color: #9a9aad;
    }}
    @media (max-width: 480px) {{
      .card {{ padding: 32px 24px; }}
      h1 {{ font-size: 24px; }}
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{icon_svg}</div>
    <h1>{heading}</h1>
    <p>{detail}</p>
    <div class="footer">Kovan Labs</div>
  </div>
</body>
</html>"""


@router.get("/{token}/accept", response_class=HTMLResponse)
async def accept_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> str:
    # Product explicitly requested direct GET actions. Email security scanners may prefetch
    # these links; if false responses appear in production, move this to a confirmation page or POST.
    message = await service.accept_offer_by_token(db, token)
    return _response_page(message, success=True)


@router.get("/{token}/reject", response_class=HTMLResponse)
async def reject_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> str:
    # Product explicitly requested direct GET actions. Email security scanners may prefetch
    # these links; if false responses appear in production, move this to a confirmation page or POST.
    message = await service.reject_offer_by_token(db, token)
    return _response_page(message, success=True)


@router.get("/{token}/download")
async def download_offer(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    url = await service.get_offer_download_url_by_token(db, token)
    return RedirectResponse(url=url, status_code=302)
