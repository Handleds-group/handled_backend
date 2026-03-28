from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

SUCCESS_HTML = """<!doctype html>
<html lang=\"en\" data-theme=\"light\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Payment Successful</title>
    <link href=\"https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css\" rel=\"stylesheet\" type=\"text/css\" />
    <script src=\"https://cdn.tailwindcss.com\"></script>
    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              lilac: '#EDE7FF',
              violetGlow: '#A78BFA',
              deepPurple: '#5B21B6'
            }
          }
        }
      }
    </script>
    <style>
      .glass-card { backdrop-filter: blur(14px); }
    </style>
  </head>
  <body class=\"min-h-screen bg-gradient-to-br from-white via-lilac to-purple-100\">
    <div class=\"min-h-screen flex items-center justify-center px-4 py-14\">
      <div class=\"max-w-2xl w-full\">
        <div class=\"glass-card card bg-white/80 shadow-2xl border border-purple-100\">
          <div class=\"card-body gap-6\">
            <div class=\"flex items-center gap-4\">
              <div class=\"avatar placeholder\">
                <div class=\"bg-violetGlow text-white rounded-full w-14 shadow-lg\">
                  <span class=\"text-2xl\">?</span>
                </div>
              </div>
              <div>
                <h1 class=\"text-3xl font-bold text-deepPurple\">Payment Successful</h1>
                <p class=\"text-slate-600\">Your subscription is active and ready to use.</p>
              </div>
            </div>

            <div class=\"grid gap-4 sm:grid-cols-3\">
              <div class=\"stat bg-white border border-purple-100 rounded-xl\">
                <div class=\"stat-title\">Status</div>
                <div class=\"stat-value text-lg text-deepPurple\">Activated</div>
                <div class=\"stat-desc\">Instant access</div>
              </div>
              <div class=\"stat bg-white border border-purple-100 rounded-xl\">
                <div class=\"stat-title\">Plan</div>
                <div class=\"stat-value text-lg text-deepPurple\">Handled Pro</div>
                <div class=\"stat-desc\">Monthly billing</div>
              </div>
              <div class=\"stat bg-white border border-purple-100 rounded-xl\">
                <div class=\"stat-title\">Next Step</div>
                <div class=\"stat-value text-lg text-deepPurple\">Open App</div>
                <div class=\"stat-desc\">Start deciding</div>
              </div>
            </div>

            <div class=\"alert bg-purple-50 border border-purple-100\">
              <div>
                <h3 class=\"font-semibold text-deepPurple\">What happens now?</h3>
                <p class=\"text-slate-600\">You can return to the app and enjoy premium features instantly. A receipt was sent to your email.</p>
              </div>
            </div>

            <div class=\"flex flex-col sm:flex-row gap-3\">
              <a class=\"btn btn-primary bg-deepPurple border-deepPurple hover:bg-violetGlow\" href=\"/\">Back to Handled</a>
              <a class=\"btn btn-ghost text-deepPurple\" href=\"/health\">System Status</a>
            </div>
          </div>
        </div>
        <div class=\"text-center text-xs text-slate-500 mt-4\">Need help? Contact support and we will sort it out fast.</div>
      </div>
    </div>
  </body>
</html>
"""

CANCEL_HTML = """<!doctype html>
<html lang=\"en\" data-theme=\"light\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>Payment Canceled</title>
    <link href=\"https://cdn.jsdelivr.net/npm/daisyui@4.12.10/dist/full.min.css\" rel=\"stylesheet\" type=\"text/css\" />
    <script src=\"https://cdn.tailwindcss.com\"></script>
    <script>
      tailwind.config = {
        theme: {
          extend: {
            colors: {
              ember: '#FEE2E2',
              emberDeep: '#DC2626',
              emberDark: '#7F1D1D'
            }
          }
        }
      }
    </script>
    <style>
      .glass-card { backdrop-filter: blur(14px); }
    </style>
  </head>
  <body class=\"min-h-screen bg-gradient-to-br from-white via-ember to-rose-100\">
    <div class=\"min-h-screen flex items-center justify-center px-4 py-14\">
      <div class=\"max-w-2xl w-full\">
        <div class=\"glass-card card bg-white/85 shadow-2xl border border-red-100\">
          <div class=\"card-body gap-6\">
            <div class=\"flex items-center gap-4\">
              <div class=\"avatar placeholder\">
                <div class=\"bg-emberDeep text-white rounded-full w-14 shadow-lg\">
                  <span class=\"text-2xl\">!</span>
                </div>
              </div>
              <div>
                <h1 class=\"text-3xl font-bold text-emberDark\">Payment Canceled</h1>
                <p class=\"text-slate-600\">No worries, you have not been charged.</p>
              </div>
            </div>

            <div class=\"grid gap-4 sm:grid-cols-3\">
              <div class=\"stat bg-white border border-red-100 rounded-xl\">
                <div class=\"stat-title\">Status</div>
                <div class=\"stat-value text-lg text-emberDark\">Canceled</div>
                <div class=\"stat-desc\">Checkout exited</div>
              </div>
              <div class=\"stat bg-white border border-red-100 rounded-xl\">
                <div class=\"stat-title\">Charge</div>
                <div class=\"stat-value text-lg text-emberDark\">$0.00</div>
                <div class=\"stat-desc\">No payment taken</div>
              </div>
              <div class=\"stat bg-white border border-red-100 rounded-xl\">
                <div class=\"stat-title\">Next Step</div>
                <div class=\"stat-value text-lg text-emberDark\">Try Again</div>
                <div class=\"stat-desc\">Ready when you are</div>
              </div>
            </div>

            <div class=\"alert bg-red-50 border border-red-100\">
              <div>
                <h3 class=\"font-semibold text-emberDark\">Need help completing checkout?</h3>
                <p class=\"text-slate-600\">If something went wrong, return to the app or reach out and we will help right away.</p>
              </div>
            </div>

            <div class=\"flex flex-col sm:flex-row gap-3\">
              <a class=\"btn bg-emberDeep border-emberDeep text-white hover:bg-red-500\" href=\"/\">Back to Handled</a>
              <a class=\"btn btn-ghost text-emberDark\" href=\"/\">Try Checkout Again</a>
            </div>
          </div>
        </div>
        <div class=\"text-center text-xs text-slate-500 mt-4\">We are here if you want to continue or need support.</div>
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
