# UtiliDriver Phasor / CT Info

Render settings:

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn --workers 1 --timeout 180 app:app`
- Root Directory: leave blank

Flow:
1. Enter meter serial and click **Get Readings Once**.
2. The app sends only one POST order.
3. Once readings show, use **Draw Phasor Diagram**, **Download Excel**, or **Download PDF**.
