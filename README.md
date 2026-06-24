# UtiliDriver Phasor Info

Render settings:
- Root Directory: leave blank
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

Safety rule: the app sends only one POST per meter lookup. If that POST fails, it stops.
