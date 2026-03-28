import os
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

EMAIL_THEME_COLOR = os.getenv("EMAIL_THEME_COLOR", "5B2AA8")
SUCCESS_BG = "#E3D7F8"
SUCCESS_CARD = "#F6F3F3"
SUCCESS_BORDER = "#E4D7FF"
SUCCESS_MUTED = "#665487"
SUCCESS_TEXT = "#40315F"
SUCCESS_BADGE_BG = "#EFE3FF"
LOGO_URL = "/images/handed-app-ui.png"

SUCCESS_HTML = f"""<!doctype html>
<html lang=\"en\" data-theme=\"light\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Payment Successful</title>
    <link href=\"https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css\" rel=\"stylesheet\" type=\"text/css\" />
    <script src=\"https://cdn.tailwindcss.com\"></script>
  </head>
  <body style=\"background:{SUCCESS_BG};\" class=\"min-h-screen\">
    <div class=\"min-h-screen flex items-center justify-center px-4 py-14\">
      <div class=\"max-w-2xl w-full\">
        <div class=\"card shadow-xl\" style=\"background:{SUCCESS_CARD}; border:1px solid {SUCCESS_BORDER};\">
          <div class=\"card-body gap-6\">
            <div class=\"text-center\">
              <div class=\"inline-flex items-center justify-center rounded-full\" style=\"background:{SUCCESS_BADGE_BG}; padding:6px; border:2px solid {SUCCESS_BORDER};\">
                <img src=\"{LOGO_URL}\" alt=\"Handled\" width=\"96\" height=\"96\" style=\"display:block; width:96px; height:96px; border-radius:50%; background:{SUCCESS_CARD};\" />
              </div>
              <h1 class=\"text-3xl font-bold mt-4\" style=\"color:#{EMAIL_THEME_COLOR};\">Payment Successful</h1>
              <p class=\"mt-1\" style=\"color:{SUCCESS_MUTED};\">Your subscription is active and ready to use.</p>
            </div>

            <div class=\"grid gap-4 sm:grid-cols-3\">
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {SUCCESS_BORDER};\">
                <div class=\"stat-title\">Status</div>
                <div class=\"stat-value text-lg\" style=\"color:{SUCCESS_TEXT};\">Activated</div>
                <div class=\"stat-desc\" style=\"color:{SUCCESS_MUTED};\">Instant access</div>
              </div>
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {SUCCESS_BORDER};\">
                <div class=\"stat-title\">Plan</div>
                <div class=\"stat-value text-lg\" style=\"color:{SUCCESS_TEXT};\">Handled Pro</div>
                <div class=\"stat-desc\" style=\"color:{SUCCESS_MUTED};\">Monthly billing</div>
              </div>
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {SUCCESS_BORDER};\">
                <div class=\"stat-title\">Next Step</div>
                <div class=\"stat-value text-lg\" style=\"color:{SUCCESS_TEXT};\">Open App</div>
                <div class=\"stat-desc\" style=\"color:{SUCCESS_MUTED};\">Start deciding</div>
              </div>
            </div>

            <div class=\"rounded-xl p-4\" style=\"background:#F7F3FF; border:1px dashed #D8C6F7;\">
              <h3 class=\"font-semibold\" style=\"color:#{EMAIL_THEME_COLOR};\">What happens now?</h3>
              <p class=\"mt-1\" style=\"color:{SUCCESS_MUTED};\">A receipt was sent to your email. You can return to the app and enjoy premium features instantly.</p>
            </div>
          </div>
        </div>
        <div class=\"text-center text-xs mt-4\" style=\"color:{SUCCESS_MUTED};\">Need help? Contact support and we will sort it out fast.</div>
      </div>
    </div>
  </body>
</html>
"""

CANCEL_BG = "#FDECEC"
CANCEL_CARD = "#FFF7F7"
CANCEL_BORDER = "#F6D1D1"
CANCEL_MUTED = "#7A4A4A"
CANCEL_TEXT = "#5A1E1E"
CANCEL_BADGE_BG = "#FEE2E2"

CANCEL_HTML = f"""<!doctype html>
<html lang=\"en\" data-theme=\"light\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Payment Canceled</title>
    <link href=\"https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css\" rel=\"stylesheet\" type=\"text/css\" />
    <script src=\"https://cdn.tailwindcss.com\"></script>
  </head>
  <body style=\"background:{CANCEL_BG};\" class=\"min-h-screen\">
    <div class=\"min-h-screen flex items-center justify-center px-4 py-14\">
      <div class=\"max-w-2xl w-full\">
        <div class=\"card shadow-xl\" style=\"background:{CANCEL_CARD}; border:1px solid {CANCEL_BORDER};\">
          <div class=\"card-body gap-6\">
            <div class=\"text-center\">
              <div class=\"inline-flex items-center justify-center rounded-full\" style=\"background:{CANCEL_BADGE_BG}; padding:8px; border:2px solid {CANCEL_BORDER};\">
                <div style=\"width:88px; height:88px; border-radius:50%; background:#FFFFFF; display:flex; align-items:center; justify-content:center; color:{CANCEL_TEXT}; font-size:36px; font-weight:700;\">!</div>
              </div>
              <h1 class=\"text-3xl font-bold mt-4\" style=\"color:{CANCEL_TEXT};\">Payment Canceled</h1>
              <p class=\"mt-1\" style=\"color:{CANCEL_MUTED};\">No worries, you have not been charged.</p>
            </div>

            <div class=\"grid gap-4 sm:grid-cols-3\">
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {CANCEL_BORDER};\">
                <div class=\"stat-title\">Status</div>
                <div class=\"stat-value text-lg\" style=\"color:{CANCEL_TEXT};\">Canceled</div>
                <div class=\"stat-desc\" style=\"color:{CANCEL_MUTED};\">Checkout exited</div>
              </div>
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {CANCEL_BORDER};\">
                <div class=\"stat-title\">Charge</div>
                <div class=\"stat-value text-lg\" style=\"color:{CANCEL_TEXT};\">$0.00</div>
                <div class=\"stat-desc\" style=\"color:{CANCEL_MUTED};\">No payment taken</div>
              </div>
              <div class=\"stat rounded-xl\" style=\"background:#FFFFFF; border:1px solid {CANCEL_BORDER};\">
                <div class=\"stat-title\">Next Step</div>
                <div class=\"stat-value text-lg\" style=\"color:{CANCEL_TEXT};\">Try Again</div>
                <div class=\"stat-desc\" style=\"color:{CANCEL_MUTED};\">Ready when you are</div>
              </div>
            </div>

            <div class=\"rounded-xl p-4\" style=\"background:#FFF1F1; border:1px dashed #E7BDBD;\">
              <h3 class=\"font-semibold\" style=\"color:{CANCEL_TEXT};\">Need help completing checkout?</h3>
              <p class=\"mt-1\" style=\"color:{CANCEL_MUTED};\">If something went wrong, return to the app or reach out and we will help right away.</p>
            </div>

            <div class=\"flex flex-col sm:flex-row gap-3\">
              <a class=\"btn\" style=\"background:#DC2626; border-color:#DC2626; color:#FFFFFF;\" href=\"/\">Back to Handled</a>
              <a class=\"btn btn-ghost\" style=\"color:{CANCEL_TEXT};\" href=\"/\">Try Checkout Again</a>
            </div>
          </div>
        </div>
        <div class=\"text-center text-xs mt-4\" style=\"color:{CANCEL_MUTED};\">We are here if you want to continue or need support.</div>
      </div>
    </div>
  </body>
</html>
"""


@router.get("/success", response_class=HTMLResponse)
async def payment_success_page():
    return HTMLResponse(content=SUCCESS_HTML)


@router.get("/cancel", response_class=HTMLResponse)
async def payment_cancel_page():
    return HTMLResponse(content=CANCEL_HTML)
