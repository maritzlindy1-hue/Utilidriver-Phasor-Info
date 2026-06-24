# Phasor CT Meter Read

Small Flask web app for UtiliDriver Phasor / CT meter reads.

## What it does

- User types an 8-digit meter serial number.
- The app converts the meter number to 8-digit HEX.
- The app sends one XML order to UtiliDriver.
- The app polls the order status using GET requests.
- When complete, it shows register values and CT ratio.

## Important server safety rule

The app only performs **one POST** per button click.

If the POST fails, times out, or does not return a `Location` header, the app stops and shows an error. It does **not** retry the POST.

The status and completed endpoints are fetched using GET requests only after a successful first POST.

## Local install

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://localhost:5000
```

## Deploy on Render

1. Upload these files to GitHub.
2. Create a new Render Web Service from the GitHub repo.
3. Render can use the included `render.yaml`.

## Environment variables

| Variable | Default |
| --- | --- |
| `UTILIDRIVER_API_URL` | `http://197.189.218.35/utilidriver/api/orders/` |
| `REQUEST_TIMEOUT_SECONDS` | `20` |
| `POLL_INTERVAL_SECONDS` | `2` |
| `POLL_TIMEOUT_SECONDS` | `120` |
