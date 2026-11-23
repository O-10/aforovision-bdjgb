# -*- coding: utf-8 -*-
"""Toma un fotograma del stream real y muestra las detecciones."""
import io
import urllib.request

import cv2
import numpy as np

from vision import PersonDetector

url = "http://127.0.0.1:8000/api/video/comicteca"
with urllib.request.urlopen(url, timeout=8) as resp:
    buffer = bytearray()
    while len(buffer) < 3_000_000:
        chunk = resp.read(8192)
        if not chunk:
            break
        buffer.extend(chunk)
        ini = buffer.find(b"\xff\xd8")
        fin = buffer.find(b"\xff\xd9", ini + 2)
        if ini >= 0 and fin > ini:
            datos = bytes(buffer[ini:fin + 2])
            frame = cv2.imdecode(np.frombuffer(datos, np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                detector = PersonDetector()
                cajas, w, h = detector.detectar(frame, conf=0.35)
                print(f"frame={w}x{h} detecciones={len(cajas)}")
                for c in cajas:
                    print(f"  conf={c['conf']:.2f} caja=({c['x1']:.0f},{c['y1']:.0f})-({c['x2']:.0f},{c['y2']:.0f})")
            break
