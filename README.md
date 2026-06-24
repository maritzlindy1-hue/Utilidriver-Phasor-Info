# UtiliDriver Phasor / CT Info

Render settings:

- Root Directory: leave blank
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --workers 1 --timeout 180 app:app`

Important: this app sends only one POST order per request. If the POST fails, it stops and does not post again.

The longer Gunicorn timeout is required because the app waits for the UtiliDriver order to complete before showing the result.
