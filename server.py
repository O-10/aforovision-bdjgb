# -*- coding: utf-8 -*-
"""Servidor web del sistema de control de aforo por visión computarizada."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
from nucleo import GestorAforo

gestor = GestorAforo()


@asynccontextmanager
async def lifespan(app: FastAPI):
    gestor.iniciar()
    yield
    gestor.detener()


app = FastAPI(
    title="AforoVision · Control de aforo por visión computarizada",
    description="Biblioteca Departamental Jorge Garcés Borrero",
    version="1.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "servidor": "AforoVision BDJGB", "hora": gestor.snapshot()["servidor"]["hora"]}


@app.get("/api/estado")
def estado() -> dict:
    return gestor.snapshot()


@app.get("/api/zonas")
def zonas() -> list[dict]:
    return config.ZONAS


@app.get("/api/fuentes")
def fuentes() -> dict:
    return {
        "institucion": config.INSTITUCION,
        "evento": config.EVENTO_ARTECA,
        "desarrollador": config.DESARROLLADOR,
        "contacto": config.CONTACTO,
        "zonas": [
            {
                "id": z["id"], "nombre": z["nombre"], "capacidad": z["capacidad"],
                "fuente": z["fuente"], "detalle": z["detalle"],
                "nota_tecnica": z.get("nota_tecnica", ""),
            }
            for z in config.ZONAS
        ],
        "documentos": [
            "Mapa_Aforos_y_Fuentes_SGSST.pdf",
            "CONCEPTO DE HABILITACIÓN CONDICIONADA PARA EL ÁREA DE LA COMICTECA.pdf",
            "concepto-habitabilidad-aforo-domo-arteca_Os.pdf",
            "Concepto técnico de Aforo y Ocupación Máxima de la plazoleta de la lectura.pdf",
            "Capacidad en el Domo.pdf",
        ],
    }


@app.post("/api/zonas/{zid}/fuente")
def configurar_fuente(zid: str, datos: dict) -> dict:
    try:
        return gestor.configurar_fuente(zid, datos)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/zonas/{zid}/manual")
def ajustar_manual(zid: str, datos: dict) -> dict:
    try:
        if zid not in gestor.workers:
            raise ValueError("Zona no encontrada")
        return gestor.ajustar_manual(zid, int(datos.get("delta", 0)))
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/zonas/{zid}/restaurar")
def restaurar(zid: str) -> dict:
    if zid not in gestor.workers:
        raise HTTPException(status_code=404, detail="Zona no encontrada")
    return gestor.restaurar_automatico(zid)


@app.post("/api/consulta")
def configurar_consulta(datos: dict) -> dict:
    try:
        return gestor.configurar_consulta(datos)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/celular/frame")
def frame_celular(datos: dict) -> dict:
    """Recibe un fotograma JPEG (base64) enviado desde la cámara del celular."""
    try:
        return gestor.recibir_frame_celular(
            str(datos.get("zona") or ""), str(datos.get("frame") or "")
        )
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/domo")
def configurar_domo(datos: dict) -> dict:
    try:
        return gestor.configurar_domo(datos)
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/video/{zid}")
def video(zid: str) -> StreamingResponse:
    if zid not in gestor.workers:
        raise HTTPException(status_code=404, detail="Zona no encontrada")

    def generador():
        limite = time.time() + 600
        while time.time() < limite:
            frame = gestor.frame(zid)
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n"
                b"Cache-Control: no-store\r\n\r\n" + frame + b"\r\n"
            )
            time.sleep(0.12)

    return StreamingResponse(
        generador(), media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/eventos")
def eventos(limit: int = 50) -> list[dict]:
    with gestor.lock:
        return list(reversed(gestor.eventos))[:max(1, min(limit, 400))]


@app.get("/api/reporte.csv")
def reporte_csv() -> Response:
    contenido = "\ufeff" + gestor.csv_reporte()
    nombre = gestor.ultimo_reporte or "reporte_aforo_bdjgb.csv"
    return Response(
        content=contenido.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )
