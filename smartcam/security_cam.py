# smartcam/security_cam.py
import cv2
import numpy as np 
import argparse

def parse_args():
    p = argparse.ArgumentParser(description="SmartCam")
    p.add_argument("--source", type=str, default="0", 
                   help="Camera index (e.g., '0') or URL (e.g., 'http://IP:8080/video'))")
    return p.parse_args()

def open_source(source: str):
    # digits like "0", "1" → webcam index; otherwise treat as URL/path
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)

def main():
    args = parse_args()
    cap = open_source(args.source)
    if not cap.isOpened():
        raise RuntimeError("Could not open source: {args.source}")
    
    # (optional) keep frames modest for speed
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    while True:
        ok, frame = cap.read()
        if not ok:
            print("[warn] frame grab failed; Retrying...")
            continue

        cv2.imshow("SmartCam", frame)

        #press 'q' to quit the program
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # release the Camera after exitted
    cap.release()
    cv2.destroyAllWindows()    
 


if __name__ == "__main__":
    main()