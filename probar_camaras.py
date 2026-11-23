# -*- coding: utf-8 -*-
"""Detecta cámaras locales disponibles sin iniciar la interfaz."""
import cv2

for idx in range(4):
    cap = None
    try:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(idx)
        ok, frame = cap.read()
        print(f"indice {idx}: abierta={cap.isOpened()} frame={ok} shape={None if frame is None else frame.shape}")
    except Exception as exc:
        print(f"indice {idx}: error {exc}")
    finally:
        if cap is not None:
            cap.release()
