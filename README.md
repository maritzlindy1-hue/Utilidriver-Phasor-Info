# UtiliDriver Phasor / CT Info

Render start command:

```bash
gunicorn --workers 1 --timeout 180 app:app
```

Flow:
1. Enter 8-digit meter serial.
2. Click **Get Readings Once**. The app sends only one POST order.
3. After readings load, use **Draw Phasor Diagram**, **Download Excel**, **Download PDF**, or **Download Phasor PDF**.

The full PDF now includes the phasor diagram plus the phase summary and register readings. The separate phasor PDF includes the phasor diagram with the phase summary only.
