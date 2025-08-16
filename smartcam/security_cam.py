# smartcam/security_cam.py
import cv2
import numpy as np 

def main():
    print("OpenCv V:", cv2.__version__)
    print("Np op, shape: ", np.zeros((2,2)).shape)

if __name__ == "__main__":
    main()