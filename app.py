from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import requests
from flask import Flask, render_template, request

API_URL = os.getenv("UTILIDRIVER_API_URL", "http://197.189.218.35/utilidriver/api/orders/")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "2"))
POLL_TIMEOUT_SECONDS = float(os.getenv("POLL_TIMEOUT_SECONDS", "120"))

app = Flask(__name__)


REGISTER_LABELS = {
    "1.1.21.7.0.255": "L1 Active Power",
    "1.1.22.7.0.255": "L1 Reactive Power",
    "1.1.31.7.0.255": "L1 Current",
    "1.1.32.7.0.255": "L1 Voltage",
    "1.1.33.7.0.255": "L1 Power Factor / Angle",
    "1.1.41.7.0.255": "L2 Active Power",
    "1.1.42.7.0.255": "L2 Reactive Power",
    "1.1.51.7.0.255": "L2 Current",
    "1.1.52.7.0.255": "L2 Voltage",
    "1.1.53.7.0.255": "L2 Power Factor / Angle",
    "1.1.61.7.0.255": "L3 Active Power",
    "1.1.62.7.0.255": "L3 Reactive Power",
    "1.1.71.7.0.255": "L3 Current",
    "1.1.72.7.0.255": "L3 Voltage",
    "1.1.73.7.0.255": "L3 Power Factor / Angle",
}


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
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Order priority='High'>
  <Subjects>
    <Meters>
      <Meter ref="http://197.189.218.35/utilidriver/api/meters/4B414D000000{meter_hex}/" />
    </Meters>
  </Subjects>
  <Commands>
    <TransformerRatioConfigurationCommand action='read' />
    <RegisterCommand action='read'><Register id='1.1.21.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.22.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.31.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.32.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.33.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.41.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.42.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.51.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.52.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.53.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.61.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.62.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.71.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.72.7.0.255' /></RegisterCommand>
    <RegisterCommand action='read'><Register id='1.1.73.7.0.255' /></RegisterCommand>
  </Commands>
</Order>""".strip()


def build_order_status_url(order_url: str) -> str:
    return f"{order_url.rstrip('/')}/status/"


def build_order_completed_url(order_url: str) -> str:
    return f"{order_url.rstrip('/')}/completed/"


def send_order_once(xml_body: str) -> str:
    """POST exactly once. No retries. If it fails, raise and stop."""
    headers = {"Content-Type": "application/xml", "Accept": "application/xml"}
    response = requests.post(API_URL, data=xml_body.encode("utf-8"), headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    order_url = response.headers.get("Location")
    if not order_url:
        raise RuntimeError("Order was created, but no Location header was returned by UtiliDriver.")
    return order_url


def wait_for_order(status_url: str) -> bool:
    end_time = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < end_time:
        response = requests.get(status_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        root = ET.fromstring(response.text.strip())
        waiting_elem = root.find("WaitingCommandCount")
        if waiting_elem is None or waiting_elem.text is None:
            raise RuntimeError("WaitingCommandCount was not found in the order status XML.")
        if int(waiting_elem.text.strip()) == 0:
            return True
        time.sleep(POLL_INTERVAL_SECONDS)
    return False


def parse_completed_results(completed_url: str) -> tuple[list[dict[str, str]], str | None, str | None]:
    response = requests.get(completed_url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    root = ET.fromstring(response.text)

    rows: list[dict[str, str]] = []
    for reg in root.findall(".//Register"):
        reg_id = (reg.get("id") or "").strip()
        if not reg_id:
            continue
        rows.append({
            "id": reg_id,
            "description": REGISTER_LABELS.get(reg_id, ""),
            "unit": (reg.findtext("Unit") or "").strip(),
            "scale": (reg.findtext("Scale") or "").strip(),
            "value": (reg.findtext("Value") or "").strip(),
        })
    rows.sort(key=lambda row: row["id"])

    ct_ratio = None
    ct_fraction = None
    ct_text = root.findtext(".//CurrentTransformerRatio")
    if ct_text:
        ct_ratio = ct_text.strip()
        try:
            ct_fraction = f"{int(ct_ratio) * 5}/5"
        except ValueError:
            ct_fraction = None

    return rows, ct_ratio, ct_fraction


def run_meter_order(meter_dec: str) -> OrderResult:
    try:
        meter_dec = validate_meter_number(meter_dec)
        meter_hex = decimal_to_hex_8(meter_dec)
        xml_body = build_xml_body(meter_hex)

        # Important safety rule: this function performs exactly ONE POST.
        # There are no retry loops around send_order_once().
        order_url = send_order_once(xml_body)

        status_url = build_order_status_url(order_url)
        completed_url = build_order_completed_url(order_url)

        if not wait_for_order(status_url):
            return OrderResult(False, "Order timed out before all commands completed. No second POST was sent.", meter_dec, meter_hex, order_url, status_url, completed_url)

        rows, ct_ratio, ct_fraction = parse_completed_results(completed_url)
        return OrderResult(True, "Order completed successfully.", meter_dec, meter_hex, order_url, status_url, completed_url, ct_ratio, ct_fraction, rows)

    except Exception as exc:
        return OrderResult(False, f"Stopped after one attempt: {exc}", meter_dec if meter_dec else None)


@app.route("/", methods=["GET", "POST"])
def index() -> Any:
    result = None
    if request.method == "POST":
        result = run_meter_order(request.form.get("meter_number", ""))
    return render_template("index.html", result=result)


@app.route("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
