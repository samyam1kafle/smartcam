# smartcam/security_cam.py
"""
SmartCam: motion-detecting 'security camera' using OpenCV.
- Works with webcam index (e.g., 0) or an IP/RTSP URL (e.g., phone camera apps).
- Shows live preview (unless --headless).
- On confirmed motion: saves a snapshot, optional local alarm, optional webhook/Telegram alert.
"""

import argparse
import os
import time
import platform
import subprocess
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import requests
from dotenv import load_dotenv

# Load env vars from .env if present
load_dotenv()


# -----------------------------
# CLI
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(description="SmartCam")
    p.add_argument(
        "--source",
        type=str,
        default="0",
        help="Camera index (e.g., '0') or URL (e.g., 'http://IP:8080/video')",
    )
    p.add_argument(
        "--show-mask",
        action="store_true",
        help="Show motion mask debug window",
    )
    p.add_argument(
        "--min-area",
        type=float,
        default=0.01,
        help="Min moving area fraction to trigger (e.g., 0.01 = 1%)",
    )
    p.add_argument(
        "--min-motion-frames",
        type=int,
        default=5,
        help="Consecutive frames with motion required to confirm event",
    )
    p.add_argument(
        "--cooldown",
        type=int,
        default=20,
        help="Seconds between alerts",
    )
    p.add_argument(
        "--save-dir",
        type=str,
        default="events",
        help="Where to save snapshots",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run without any windows",
    )
    p.add_argument(
        "--no-alarm",
        action="store_true",
        help="Disable local alarm sound",
    )
    p.add_argument(
        "--webhook-url",
        type=str,
        default=os.getenv("WEBHOOK_URL", ""),
        help="Generic webhook URL (Slack/Discord/etc.)",
    )
    p.add_argument(
        "--telegram-token",
        type=str,
        default=os.getenv("TELEGRAM_TOKEN", ""),
        help="Telegram bot token",
    )
    p.add_argument(
        "--telegram-chat-id",
        type=str,
        default=os.getenv("TELEGRAM_CHAT_ID", ""),
        help="Telegram chat ID",
    )
    p.add_argument(
        "--max-fps",
        type=float,
        default=8.0,
        help="Process at most this many FPS (reduces CPU)",
    )
    p.add_argument(
    "--discord-webhook",
    type=str,
    default=os.getenv("DISCORD_WEBHOOK_URL", ""),
    help="Discord webhook URL (sends snapshot images)"
    )
    return p.parse_args()


# -----------------------------
# Helpers
# -----------------------------
def open_source(source: str):
    """Open webcam by index string ('0', '1', ...) or URL/path."""
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def ensure_dir(path: str):
    if path and not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def save_snapshot(frame, directory: str) -> str:
    ensure_dir(directory)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(directory, f"event_{ts}.jpg")
    cv2.imwrite(path, frame)
    return path


def play_alarm():
    """Cross-platform best-effort beep."""
    try:
        if platform.system() == "Windows":
            import winsound

            winsound.Beep(1000, 500)
        elif platform.system() == "Darwin":
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
        else:
            # Linux fallback: terminal bell
            print("\a", end="", flush=True)
    except Exception as e:
        print(f"[warn] alarm failed: {e}")


def send_webhook(url: str, text: str):
    if not url:
        return
    try:
        requests.post(url, json={"text": text}, timeout=5)
    except Exception as e:
        print(f"[warn] webhook failed: {e}")

def send_discord(webhook_url: str, text: str, image_path: str | None = None):
    """Post a message (and optional image) to Discord via webhook."""
    if not webhook_url:
        return
    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                files = {"file": (os.path.basename(image_path), f, "image/jpeg")}
                data = {"content": text, "username": "SmartCam"}
                resp = requests.post(webhook_url, data=data, files=files, timeout=10)
        else:
            resp = requests.post(
                webhook_url,
                json={"content": text, "username": "SmartCam"},
                timeout=5
            )
        if resp.status_code >= 300:
            print(f"[warn] discord failed: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"[warn] discord exception: {e}")

def send_telegram(token: str, chat_id: str, text: str, image_path: str | None = None):
    if not token or not chat_id:
        return
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            with open(image_path, "rb") as f:
                files = {"photo": f}
                data = {"chat_id": chat_id, "caption": text}
                requests.post(url, data=data, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {"chat_id": chat_id, "text": text}
            requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"[warn] telegram failed: {e}")


# -----------------------------
# Main
# -----------------------------
def main():
    args = parse_args()
    cap = open_source(args.source)

    if not cap.isOpened():
        raise RuntimeError(f"Could not open source: {args.source}")

    # Keep frames modest for speed (no-op for some network streams)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    # Background subtractor for motion
    backSub = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=16, detectShadows=True
    )

    # Stabilization & rate limiting
    motion_window = deque(maxlen=args.min_motion_frames)
    cooldown_s = args.cooldown
    last_alert_time = 0.0

    min_dt = 1.0 / max(0.1, args.max_fps)
    last_time = 0.0

    if args.headless:
        print("[info] Running headless.")
    else:
        print("[info] Press 'q' to quit.")
    try:
        while True:
            # FPS cap
            now = time.time()
            if now - last_time < min_dt:
                time.sleep(0.001)
                continue
            last_time = now

            ok, frame = cap.read()
            if not ok or frame is None:
                print("[warn] frame grab failed; retrying…")
                continue

            # Preprocess: grayscale + slight blur to reduce noise
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (5, 5), 0)

            # Background subtraction → threshold → dilate
            fg = backSub.apply(gray)
            _, th = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
            th = cv2.dilate(th, None, iterations=2)

            # Find moving blobs (contours)
            contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Measure total moving area vs threshold
            frame_area = gray.shape[0] * gray.shape[1]
            min_area_fraction = args.min_area
            min_area_pixels = min_area_fraction * frame_area
            moving_area = 0

            for c in contours:
                area = cv2.contourArea(c)
                if area < 100:  # ignore tiny noise
                    continue
                moving_area += area
                x, y, w, h = cv2.boundingRect(c)
                # Draw boxes on preview (gray)
                if not args.headless:
                    cv2.rectangle(gray, (x, y), (x + w, y + h), (255, 255, 255), 2)

            motion_detected = moving_area >= min_area_pixels

            # Require consecutive frames to confirm motion; then apply cooldown
            motion_window.append(1 if motion_detected else 0)
            strong_motion = sum(motion_window) >= motion_window.maxlen

            if strong_motion and (now - last_alert_time) >= cooldown_s:
                last_alert_time = now

                # 1) Save snapshot at full resolution
                snapshot = save_snapshot(frame, args.save_dir)
                print(f"[event] motion confirmed → saved: {snapshot}")

                # 2) Optional local alarm
                if not args.no_alarm:
                    play_alarm()

                # 3) Optional alerts
                msg = f"Motion detected at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                send_webhook(args.webhook_url, msg)
                send_telegram(args.telegram_token, args.telegram_chat_id, msg, image_path=snapshot)
                send_discord(args.discord_webhook, msg, image_path=snapshot)


                # Reset so we don't immediately retrigger
                motion_window.clear()

            # Overlay status text on preview
            if not args.headless:
                cv2.putText(
                    gray,
                    f"Motion:{'YES' if motion_detected else 'no'} area:{moving_area:.0f}/{min_area_pixels:.0f}",
                    (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    2,
                )
                if args.show_mask:
                    cv2.imshow("MotionMask", th)
                cv2.imshow("SmartCam", gray)

                # Quit with 'q'
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
    except KeyboardInterrupt:
        print("\n[info] Ctrl+C received, stopping…")
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()
    


if __name__ == "__main__":
    main()
