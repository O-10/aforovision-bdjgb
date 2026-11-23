# -*- coding: utf-8 -*-
"""Detección de personas, generación de fotogramas y anotaciones.

Motor principal: YOLOv8n (clase 'person') con pesos locales, sin conexión.
Respaldo: HOG + SVM de OpenCV cuando el modelo no está disponible.
Modo DEMO: escena sintética etiquetada como SIMULACIÓN para probar la interfaz.
"""
from __future__ import annotations

import random
import threading
import time
from datetime import datetime

import cv2
import numpy as np

import config

try:
    from ultralytics import YOLO  # type: ignore
except Exception:  # pragma: no cover
    YOLO = None


class PersonDetector:
    """Detecta personas dentro de una región de interés (ROI)."""

    def __init__(self) -> None:
        self.yolo = None
        self.yolo_error = None
        if YOLO is not None and config.MODELO_PERSONAS.is_file():
            try:
                self.yolo = YOLO(str(config.MODELO_PERSONAS))
            except Exception as exc:  # pragma: no cover
                self.yolo_error = str(exc)
        self.hog = None
        if hasattr(cv2, "HOGDescriptor") and hasattr(cv2, "HOGDescriptor_getDefaultPeopleDetector"):
            try:
                self.hog = cv2.HOGDescriptor()
                self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            except Exception:
                self.hog = None
        self._lock = threading.Lock()
        self._prev: dict[str, np.ndarray] = {}

    @property
    def motor(self) -> str:
        if self.yolo is not None:
            return "YOLOv8n · personas"
        if self.hog is not None:
            return "OpenCV HOG · personas"
        return "OpenCV movimiento (aprox.)"

    def detectar(
        self, frame: np.ndarray, conf: float = 0.35, roi: list[float] | None = None,
        clave: str = "default",
    ) -> tuple[list[dict], int, int]:
        """Devuelve (detecciones, ancho, alto). Coordenadas en el frame completo."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = _roi_pixeles(roi, w, h)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return [], w, h

        if self.yolo is not None:
            cajas = self._detectar_yolo(crop, conf)
        elif self.hog is not None:
            cajas = self._detectar_hog(crop)
        else:
            cajas = self._detectar_movimiento(crop, clave)

        for c in cajas:
            c["x1"] += x1
            c["x2"] += x1
            c["y1"] += y1
            c["y2"] += y1
        return cajas, w, h

    def _detectar_yolo(self, crop: np.ndarray, conf: float) -> list[dict]:
        try:
            with self._lock:
                resultados = self.yolo.predict(
                    crop, conf=conf, classes=[0], imgsz=640, verbose=False
                )
        except Exception:
            return []
        salida = []
        for r in resultados:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for b in boxes:
                xa, ya, xb, yb = [float(v) for v in b.xyxy[0].tolist()]
                salida.append(
                    {
                        "x1": xa, "y1": ya, "x2": xb, "y2": yb,
                        "conf": float(b.conf[0]), "motor": "yolo",
                    }
                )
        return salida

    def _detectar_hog(self, crop: np.ndarray) -> list[dict]:
        try:
            rects, pesos = self.hog.detectMultiScale(
                crop, winStride=(6, 6), padding=(8, 8), scale=1.05
            )
        except Exception:
            return []
        salida = []
        for (x, y, cw, ch), peso in zip(rects, pesos):
            if float(peso) < 0.45:
                continue
            salida.append(
                {
                    "x1": float(x), "y1": float(y),
                    "x2": float(x + cw), "y2": float(y + ch),
                    "conf": float(peso), "motor": "hog",
                }
            )
        return salida

    def _detectar_movimiento(self, crop: np.ndarray, clave: str) -> list[dict]:
        """Respaldos sin modelo: agrupa blobs en movimiento (estimación burda)."""
        gris = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gris = cv2.GaussianBlur(gris, (7, 7), 0)
        anterior = self._prev.get(clave)
        self._prev[clave] = gris
        if anterior is None or anterior.shape != gris.shape:
            return []
        dif = cv2.absdiff(anterior, gris)
        _, mask = cv2.threshold(dif, 22, 255, cv2.THRESH_BINARY)
        mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
        contornos, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area_min = max(350, crop.shape[0] * crop.shape[1] // 900)
        salida = []
        for c in contornos:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            if area < area_min or ch < crop.shape[0] * 0.12:
                continue
            salida.append(
                {
                    "x1": float(x), "y1": float(y),
                    "x2": float(x + cw), "y2": float(y + ch),
                    "conf": 0.5, "motor": "movimiento",
                }
            )
        return salida


def _roi_pixeles(roi: list[float] | None, w: int, h: int) -> tuple[int, int, int, int]:
    if not roi or len(roi) != 4:
        return 0, 0, w, h
    try:
        xa, ya, xb, yb = [float(v) for v in roi]
    except Exception:
        return 0, 0, w, h
    xa = max(0.0, min(1.0, xa))
    xb = max(0.0, min(1.0, xb))
    ya = max(0.0, min(1.0, ya))
    yb = max(0.0, min(1.0, yb))
    if xb <= xa or yb <= ya:
        return 0, 0, w, h
    return int(xa * w), int(ya * h), int(xb * w), int(yb * h)


class DemoEscena:
    """Personas sintéticas en movimiento para demostración sin cámara."""

    def __init__(self, zona_id: str, capacidad: int) -> None:
        self.capacidad = capacidad
        self.rng = random.Random(sum(ord(c) for c in zona_id) + capacidad)
        self.objetivos = [
            {
                "x": self.rng.uniform(0.06, 0.94),
                "y": self.rng.uniform(0.35, 0.88),
                "vx": self.rng.uniform(-0.0009, 0.0009),
                "vy": self.rng.uniform(-0.0005, 0.0005),
            }
            for _ in range(max(4, int(capacidad * 0.35)))
        ]
        self._ultimo_cambio = time.time()

    def generar(self, ancho: int = 768, alto: int = 432) -> tuple[np.ndarray, list[dict]]:
        ahora = time.time()
        if ahora - self._ultimo_cambio > 2.6:
            self._ultimo_cambio = ahora
            delta = self.rng.choice([-2, -1, -1, 0, 1, 1, 2])
            objetivo = max(2, min(self.capacidad + 10, len(self.objetivos) + delta))
            while len(self.objetivos) < objetivo:
                self.objetivos.append(
                    {
                        "x": self.rng.uniform(0.06, 0.94),
                        "y": self.rng.uniform(0.35, 0.88),
                        "vx": self.rng.uniform(-0.0009, 0.0009),
                        "vy": self.rng.uniform(-0.0005, 0.0005),
                    }
                )
            self.objetivos = self.objetivos[:objetivo]

        frame = np.zeros((alto, ancho, 3), dtype=np.uint8)
        for y in range(alto):
            t = y / max(1, alto - 1)
            frame[y, :] = (
                int(12 + 18 * t), int(23 + 30 * t), int(38 + 42 * t)
            )
        cv2.line(frame, (0, int(alto * 0.72)), (ancho, int(alto * 0.72)), (45, 70, 92), 2)
        cv2.putText(
            frame, "MODO DEMO - SIMULACION", (16, 26),
            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 200, 255), 2, cv2.LINE_AA,
        )

        cajas = []
        colores = [(90, 190, 120), (110, 170, 230), (220, 170, 90), (190, 130, 210)]
        for i, p in enumerate(self.objetivos):
            p["x"] += p["vx"] * 16
            p["y"] += p["vy"] * 16
            if p["x"] < 0.04 or p["x"] > 0.96:
                p["vx"] *= -1
            if p["y"] < 0.32 or p["y"] > 0.9:
                p["vy"] *= -1
            cx, cy = int(p["x"] * ancho), int(p["y"] * alto)
            color = colores[i % len(colores)]
            cv2.circle(frame, (cx, cy - 20), 7, color, -1, cv2.LINE_AA)
            cv2.rectangle(frame, (cx - 12, cy - 12), (cx + 12, cy + 30), color, -1, cv2.LINE_AA)
            cv2.line(frame, (cx - 9, cy + 30), (cx - 11, cy + 52), color, 5, cv2.LINE_AA)
            cv2.line(frame, (cx + 9, cy + 30), (cx + 11, cy + 52), color, 5, cv2.LINE_AA)
            cajas.append(
                {
                    "x1": float(cx - 17), "y1": float(cy - 32),
                    "x2": float(cx + 17), "y2": float(cy + 56),
                    "conf": 0.98, "motor": "demo",
                }
            )
        return frame, cajas


def frame_placeholder(titulo: str, mensaje: str) -> np.ndarray:
    frame = np.zeros((432, 768, 3), dtype=np.uint8)
    frame[:] = (28, 22, 18)
    cv2.putText(
        frame, titulo[:44], (24, 190),
        cv2.FONT_HERSHEY_SIMPLEX, 0.75, (180, 210, 235), 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, mensaje[:60], (24, 235),
        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (150, 160, 170), 1, cv2.LINE_AA,
    )
    return frame


def anotar(
    frame: np.ndarray,
    cajas: list[dict],
    *,
    zona: str,
    conteo: int,
    capacidad: int,
    estado: str,
    origen: str,
    roi: list[float] | None = None,
) -> np.ndarray:
    """Dibuja cajas, ROI y cabecera informativa sobre el fotograma."""
    out = frame.copy()
    h, w = out.shape[:2]
    colores = {
        "normal": (60, 200, 130),
        "preventiva": (60, 190, 235),
        "excedido": (70, 70, 235),
        "inactivo": (140, 140, 140),
        "sin_fuente": (140, 140, 140),
    }
    color = colores.get(estado, (200, 200, 200))

    xa, ya, xb, yb = _roi_pixeles(roi, w, h)
    if roi and not (xa == 0 and ya == 0 and xb == w and yb == h):
        for x in range(xa, xb, 18):
            cv2.line(out, (x, ya), (min(x + 9, xb), ya), (255, 255, 255), 1)
            cv2.line(out, (x, yb), (min(x + 9, xb), yb), (255, 255, 255), 1)
        for y in range(ya, yb, 18):
            cv2.line(out, (xa, y), (xa, min(y + 9, yb)), (255, 255, 255), 1)
            cv2.line(out, (xb, y), (xb, min(y + 9, yb)), (255, 255, 255), 1)

    for c in cajas:
        x1, y1 = int(c["x1"]), int(c["y1"])
        x2, y2 = int(c["x2"]), int(c["y2"])
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.rectangle(out, (x1, y1 - 17), (x1 + 78, y1), color, -1)
        cv2.putText(
            out, f"PERSONA {c.get('conf', 0):.2f}", (x1 + 2, y1 - 4),
            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (15, 20, 25), 1, cv2.LINE_AA,
        )

    overlay = out.copy()
    cv2.rectangle(overlay, (0, 0), (w, 62), (8, 13, 22), -1)
    cv2.addWeighted(overlay, 0.82, out, 0.18, 0, out)
    cv2.rectangle(out, (0, 60), (w, 63), color, -1)
    cv2.putText(
        out, zona[:30], (14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.68, (235, 245, 255), 2, cv2.LINE_AA
    )
    texto = f"{conteo}/{capacidad}  {estado.upper()}"
    (tw, _), _ = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX, 0.62, 2)
    cv2.putText(
        out, texto, (w - tw - 14, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.62, color, 2, cv2.LINE_AA
    )
    cv2.putText(
        out, f"ORIGEN: {origen[:46]}", (14, 49),
        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (150, 170, 190), 1, cv2.LINE_AA,
    )
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (sw, _), _ = cv2.getTextSize(sello, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
    cv2.putText(
        out, sello, (w - sw - 12, h - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (170, 185, 200), 1, cv2.LINE_AA,
    )
    return out


def jpeg(frame: np.ndarray, calidad: int = 78) -> bytes:
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), calidad])
    if not ok:
        return b""
    return buffer.tobytes()
