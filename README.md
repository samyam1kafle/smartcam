# SmartCam

Turn a webcam or unused phone into a motion-detecting security camera (OpenCV).

- Saves snapshots on motion (to `events/`)
- Optional local alarm sound
- Optional alerts via Webhook or Telegram (can include photo)
- Headless mode for running in the background
- Adjustable sensitivity & cooldown

## Requirements

- Python 3.10+
- macOS, Linux, or Windows
- On Ubuntu/Debian you may also need:

  ```bash
  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0
  ```

## Quickstart (development)

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
# .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install opencv-python numpy python-dotenv requests
```

## Run

Webcam (index 0):

```bash
python smartcam/security_cam.py --source 0 --min-area 0.01 --min-motion-frames 5
```

Headless + faster alerts:

```bash
python smartcam/security_cam.py --headless --cooldown 10 --save-dir events
```

## Use a phone as the camera

**Android (e.g., “IP Webcam” app)**

1. Connect phone & computer to the same Wi-Fi
2. Start the server in the app and note the IP (e.g., `http://192.168.1.45:8080`)
3. Use the MJPEG endpoint:

```bash
python smartcam/security_cam.py --headless --source "http://192.168.1.45:8080/video"
```

**iOS**
Many IP/RTSP camera apps expose URLs like:

```
http://<PHONE_IP>:<PORT>/video.mjpg
rtsp://<PHONE_IP>:<PORT>/live
```

Pass that URL to `--source`.

## Alerts (optional)

Create a `.env` file in the project root (or set environment variables):

```
WEBHOOK_URL=
TELEGRAM_TOKEN=
TELEGRAM_CHAT_ID=
```

Then run headless:

```bash
python smartcam/security_cam.py --headless
```

## How it works (short)

The script builds a background model (OpenCV MOG2).
When the changed pixel area exceeds a threshold for N consecutive frames, it saves a snapshot, optionally plays a sound, and sends an alert (respecting a cooldown).

## Project structure

```
smartcam/
├─ smartcam/
│  ├─ __init__.py
│  └─ security_cam.py
├─ events/              # created at runtime
├─ .env                 # (optional) secrets, not committed
├─ .gitignore
└─ README.md
```

## License

MIT — see `LICENSE`.
