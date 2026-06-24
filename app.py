from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests
from flask import Flask, request, render_template_string

API_URL = os.getenv("UTILIDRIVER_API_URL", "http://197.189.218.35/utilidriver/api/orders/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
POLL_TIMEOUT_SECONDS = float(os.getenv("POLL_TIMEOUT_SECONDS", "120"))

app = Flask(__name__)

REGISTER_LABELS = {
    "1.1.21.7.0.255": "L1 Active Power", "1.1.22.7.0.255": "L1 Reactive Power",
    "1.1.31.7.0.255": "L1 Current", "1.1.32.7.0.255": "L1 Voltage", "1.1.33.7.0.255": "L1 Power Factor / Angle",
    "1.1.41.7.0.255": "L2 Active Power", "1.1.42.7.0.255": "L2 Reactive Power",
    "1.1.51.7.0.255": "L2 Current", "1.1.52.7.0.255": "L2 Voltage", "1.1.53.7.0.255": "L2 Power Factor / Angle",
    "1.1.61.7.0.255": "L3 Active Power", "1.1.62.7.0.255": "L3 Reactive Power",
    "1.1.71.7.0.255": "L3 Current", "1.1.72.7.0.255": "L3 Voltage", "1.1.73.7.0.255": "L3 Power Factor / Angle",
}

PAGE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>UtiliDriver Phasor / CT Info</title>
  <style>
    body{font-family:Arial,sans-serif;background:#f4f6f8;margin:0;padding:30px;color:#1f2937}.card{max-width:1100px;margin:auto;background:white;padding:24px;border-radius:14px;box-shadow:0 8px 30px #0001}input,button{font-size:16px;padding:12px;border-radius:8px;border:1px solid #cbd5e1}button{background:#111827;color:white;cursor:pointer}.ok{background:#ecfdf5;border-left:5px solid #10b981;padding:12px}.bad{background:#fef2f2;border-left:5px solid #ef4444;padding:12px}table{border-collapse:collapse;width:100%;margin-top:18px}th,td{border-bottom:1px solid #e5e7eb;padding:10px;text-align:left}th{background:#f9fafb}.small{color:#64748b;font-size:13px}.urls{word-break:break-all;background:#f8fafc;padding:10px;border-radius:8px}
  </style>
</head>
<body>
<div class="card">
  <h1>UtiliDriver Phasor / CT Info</h1>
  <p class="small">Enter the 8-digit meter serial number. The system will send only one POST order. If it fails, it will stop and not post again.</p>
  <form method="post">
    <input name="meter_number" placeholder="e.g. 12345678" maxlength="8" pattern="[0-9]{8}" required>
    <button type="submit">Run Once</button>
  </form>

  {% if result %}
    <h2>Result</h2>
    <div class="{{ 'ok' if result.ok else 'bad' }}">{{ result.message }}</div>
    {% if result.meter_dec %}<p><b>Meter:</b> {{ result.meter_dec }} {% if result.meter_hex %} | <b>Hex:</b> {{ result.meter_hex }}{% endif %}</p>{% endif %}
    {% if result.order_url %}
      <div class="urls"><b>Order URL:</b> {{ result.order_url }}<br><b>Status URL:</b> {{ result.status_url }}<br><b>Completed URL:</b> {{ result.completed_url }}</div>
    {% endif %}
    {% if result.ct_ratio %}<p><b>CT Ratio:</b> {{ result.ct_ratio }} {% if result.ct_fraction %} | <b>Fraction:</b> {{ result.ct_fraction }}{% endif %}</p>{% endif %}
    {% if result.rows %}
      <table><tr><th>Register</th><th>Description</th><th>Unit</th><th>Scale</th><th>Value</th></tr>
      {% for row in result.rows %}<tr><td>{{ row.id }}</td><td>{{ row.description }}</td><td>{{ row.unit }}</td><td>{{ row.scale }}</td><td>{{ row.value }}</td></tr>{% endfor %}
      </table>
    {% endif %}
  {% endif %}
</div>
</body>
</html>
"""

@dataclass
class OrderResult:
    ok: bool
    message: str
    meter_dec: str | None = None
    meter_hex: str | None = None
    order_url: str | None = None
    status_url: str | None = None
    completed_url: str | None = None
    ct_ratio: str | None = None
    ct_fraction: str | None = None
    rows: list[dict[str, str]] | None = None

def validate_meter_number(meter_dec: str) -> str:
    meter_dec = meter_dec.strip()
    if len(meter_dec) != 8 or not meter_dec.isdigit():
        raise ValueError("Meter number must be exactly 8 digits.")
    return meter_dec

def decimal_to_hex_8(meter_dec: str) -> str:
    return format(int(meter_dec), "08X")

def build_xml_body(meter_hex: str) -> str:
    registers = "\n".join(f"    <RegisterCommand action='read'><Register id='{reg_id}' /></RegisterCommand>" for reg_id in REGISTER_LABELS)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Order priority='High'>
  <Subjects><Meters><Meter ref="http://197.189.218.35/utilidriver/api/meters/4B414D000000{meter_hex}/" /></Meters></Subjects>
  <Commands>
    <TransformerRatioConfigurationCommand action='read' />
{registers}
  </Commands>
</Order>""".strip()

def send_order_once(xml_body: str) -> str:
    headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
    response = requests.post(API_URL, data=xml_body.encode("utf-8"), headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    order_url = response.headers.get("Location")
    if not order_url:
        raise RuntimeError("Order posted, but no Location header was returned.")
    return order_url

def wait_for_order(status_url: str) -> bool:
    end_time = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < end_time:
        response = requests.get(status_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        root = ET.fromstring(response.text.strip())
        waiting_text = root.findtext("WaitingCommandCount")
        if waiting_text is None:
            raise RuntimeError("WaitingCommandCount was not found in status XML.")
        if int(waiting_text.strip()) == 0:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return False

def parse_completed_results(completed_url: str):
    response = requests.get(completed_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    root = ET.fromstring(response.text)
    rows = []
    for reg in root.findall(".//Register"):
        reg_id = (reg.get("id") or "").strip()
        if reg_id:
            rows.append({"id": reg_id, "description": REGISTER_LABELS.get(reg_id, ""), "unit": (reg.findtext("Unit") or "").strip(), "scale": (reg.findtext("Scale") or "").strip(), "value": (reg.findtext("Value") or "").strip()})
    rows.sort(key=lambda row: row["id"])
    ct_ratio = (root.findtext(".//CurrentTransformerRatio") or "").strip() or None
    ct_fraction = None
    if ct_ratio:
        try: ct_fraction = f"{int(ct_ratio) * 5}/5"
        except ValueError: pass
    return rows, ct_ratio, ct_fraction

def run_meter_order(meter_dec: str) -> OrderResult:
    try:
        meter_dec = validate_meter_number(meter_dec)
        meter_hex = decimal_to_hex_8(meter_dec)
        order_url = send_order_once(build_xml_body(meter_hex))  # exactly one POST only
        status_url = f"{order_url.rstrip('/')}/status/"
        completed_url = f"{order_url.rstrip('/')}/completed/"
        if not wait_for_order(status_url):
            return OrderResult(False, "Timed out. No second POST was sent.", meter_dec, meter_hex, order_url, status_url, completed_url)
        rows, ct_ratio, ct_fraction = parse_completed_results(completed_url)
        return OrderResult(True, "Order completed successfully.", meter_dec, meter_hex, order_url, status_url, completed_url, ct_ratio, ct_fraction, rows)
    except Exception as exc:
        return OrderResult(False, f"Stopped after one attempt: {exc}", meter_dec if meter_dec else None)

@app.route("/", methods=["GET", "POST"])
def index() -> Any:
    result = run_meter_order(request.form.get("meter_number", "")) if request.method == "POST" else None
    return render_template_string(PAGE, result=result)

@app.route("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
