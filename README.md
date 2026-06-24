# UtiliDriver Phasor / CT Info

Render/GitHub-ready Flask web app.

## Render settings

- Root Directory: leave blank
- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`

## Safety note

The app sends only one POST order per button click. If that POST fails, the app stops and does not retry/post again.

## Phasor note

The phasor diagram is approximate. Voltage phase angles are assumed as L1 0°, L2 -120°, L3 +120°. Current angle is calculated from power factor using `acos(PF)` and assumed lagging.
