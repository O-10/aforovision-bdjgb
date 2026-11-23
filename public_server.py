# -*- coding: utf-8 -*-
"""Servidor público: expone el aforo en móviles sin administración.

Este servicio se publica en internet. Permite:
  - ver el tablero móvil (/);
  - consultar el estado filtrado (/api/estado);
  - activar la medición del área elegida (/api/consulta);
  - medir con la cámara del propio celular (/api/celular/frame);
  - descargar el reporte CSV (/api/reporte.csv).

Nunca expone cámaras, video, cambio de fuentes, conteo manual ni configuración.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response

ORIGEN = os.getenv("AFORO_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
STATIC = Path(__file__).resolve().parent / "static"
EVENTOS_PUBLICOS = {"excedido", "preventiva", "normalizado", "manual", "celular"}
ZONAS_PERMITIDAS = {"comicteca", "domo_p2", "domo_p3", "plazoleta"}

app = FastAPI(title="AforoVision · Consulta pública", version="1.0.0")


def _get(ruta: str, timeout: int = 5) -> bytes:
    try:
        with urllib.request.urlopen(ORIGEN + ruta, timeout=timeout) as resp:
            return resp.read()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="El motor de aforo no está disponible") from exc


def _post(ruta: str, cuerpo: dict) -> bytes:
    req = urllib.request.Request(
        ORIGEN + ruta,
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="No se pudo activar el área") from exc


def filtrar(estado: dict) -> dict:
    """Mantiene solo datos de aforo; quita rutas, credenciales y configuración."""
    servidor = estado.get("servidor") or {}
    return {
        "servidor": {
            "hora": servidor.get("hora"),
            "institucion": servidor.get("institucion"),
            "evento": servidor.get("evento"),
            "desarrollador": servidor.get("desarrollador"),
            "contacto": servidor.get("contacto"),
            "licencia_sst": servidor.get("licencia_sst"),
        },
        "resumen": estado.get("resumen") or {},
        "zonas": [
            {
                "id": z.get("id"), "nombre": z.get("nombre"),
                "capacidad": z.get("capacidad"), "conteo": z.get("conteo"),
                "estado": z.get("estado"), "color": z.get("color"),
                "tipo_fuente": z.get("tipo_fuente"),
            }
            for z in estado.get("zonas") or []
        ],
        "consulta": estado.get("consulta") or {},
        "eventos": [
            {
                "ts": ev.get("ts"), "tipo": ev.get("tipo"),
                "zona": ev.get("zona"), "mensaje": ev.get("mensaje"),
            }
            for ev in (estado.get("eventos") or [])
            if ev.get("tipo") in EVENTOS_PUBLICOS
        ],
    }


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "ver.html")


@app.get("/api/estado")
def estado() -> dict:
    return filtrar(json.loads(_get("/api/estado")))


@app.post("/api/consulta")
def consulta(datos: dict) -> dict:
    """Enfoca la detección en el área elegida."""
    zona = datos.get("zona")
    activo = bool(datos.get("activo", True))
    if activo and zona not in ZONAS_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Área no válida")
    _post("/api/consulta", {"activo": activo, "zona": zona})
    return filtrar(json.loads(_get("/api/estado")))


_ultimo_frame = 0.0


@app.post("/api/celular/frame")
def frame_celular(datos: dict) -> dict:
    """Recibe un fotograma de la cámara del celular y devuelve el conteo."""
    global _ultimo_frame
    zona = datos.get("zona")
    if zona not in ZONAS_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Área no válida")
    frame = datos.get("frame")
    if not isinstance(frame, str) or len(frame) > 3_500_000:
        raise HTTPException(status_code=413, detail="Fotograma demasiado grande")
    ahora = time.monotonic()
    if ahora - _ultimo_frame < 0.25:  # máximo ~4 fps por el enlace compartido
        raise HTTPException(status_code=429, detail="Enviando fotogramas muy rápido")
    _ultimo_frame = ahora
    respuesta = _post("/api/celular/frame", {"zona": zona, "frame": frame})
    return json.loads(respuesta) if respuesta else {"ok": True}


@app.get("/api/reporte.csv")
def reporte_csv() -> Response:
    return Response(
        content=_get("/api/reporte.csv"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aforo_bdjgb.csv"'},
    )


@app.get("/health")
def health() -> dict:
    return {"ok": True, "servicio": "AforoVision · Consulta pública"}
