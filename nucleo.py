# -*- coding: utf-8 -*-
"""Núcleo de monitoreo: hilos por zona, alertas y estado compartido."""
from __future__ import annotations

import base64
import csv
import io
import json
import statistics
import threading
import time
from collections import deque
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import cv2
import numpy as np

import config
from vision import DemoEscena, PersonDetector, anotar, frame_placeholder, jpeg

LOCAL_TZ = timezone(timedelta(hours=-5))  # America/Bogota


def ahora_iso() -> str:
    return datetime.now(LOCAL_TZ).isoformat(timespec="seconds")


def estado_de(conteo: int, capacidad: int) -> str:
    if conteo > capacidad:
        return "excedido"
    if conteo >= capacidad * config.UMBRAL_PREVENTIVA:
        return "preventiva"
    return "normal"


class TrabajadorZona:
    """Un hilo por zona: captura, detección, suavizado y fotograma anotado."""

    def __init__(self, zona: dict, cfg: dict, detector: PersonDetector) -> None:
        self.zona = zona
        self.zid = zona["id"]
        self.cfg = dict(cfg)
        self.detector = detector
        self.cap: cv2.VideoCapture | None = None
        self.imagen_fija: np.ndarray | None = None
        self.demo = DemoEscena(self.zid, int(zona["capacidad"]))
        self.manual: int | None = None
        self.cfg_antes_manual: dict | None = None
        self.conteo = 0
        self.crudo = 0
        self.historial: deque[int] = deque(maxlen=config.HISTORIAL)
        self.estado = "normal"
        self.actualizado = ahora_iso()
        self.error: str | None = None
        self.frame_jpg = jpeg(
            frame_placeholder(zona["nombre"], "INICIANDO MONITOREO")
        )
        self._stop = threading.Event()
        self._proxima = 0.0

    # ------------------------------------------------------------------
    def aplicar_config(self, cfg: dict) -> None:
        self._liberar_captura()
        self.cfg = dict(cfg)
        self.demo = DemoEscena(self.zid, int(self.zona["capacidad"]))
        self.historial.clear()
        self.error = None
        self._proxima = 0.0

    def activar_manual(self, conteo: int) -> None:
        if self.manual is None:
            self.cfg_antes_manual = dict(self.cfg)
        self.manual = max(0, min(500, int(conteo)))
        self._liberar_captura()
        self.historial.clear()
        self._proxima = 0.0

    def ajustar_manual(self, delta: int) -> int:
        base = self.manual if self.manual is not None else self.conteo
        self.activar_manual(base + delta)
        return self.manual or 0

    def restaurar_automatico(self) -> None:
        self.manual = None
        if self.cfg_antes_manual:
            self.aplicar_config(self.cfg_antes_manual)
        self.cfg_antes_manual = None
        self._proxima = 0.0

    def _liberar_captura(self) -> None:
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None
        self.imagen_fija = None

    def detener(self) -> None:
        self._stop.set()
        self._liberar_captura()

    # ------------------------------------------------------------------
    def _abrir_captura(self) -> None:
        tipo = str(self.cfg.get("tipo", "sin_fuente")).lower()
        valor = str(self.cfg.get("valor", "")).strip()
        if not valor:
            self.error = "La fuente no tiene valor configurado"
            return
        try:
            if tipo == "camara":
                if valor.isdigit():
                    self.cap = cv2.VideoCapture(int(valor), cv2.CAP_DSHOW)
                    if not self.cap.isOpened():
                        self.cap.release()
                        self.cap = cv2.VideoCapture(int(valor))
                else:
                    self.cap = cv2.VideoCapture(valor, cv2.CAP_FFMPEG)
                for prop in ("CAP_PROP_OPEN_TIMEOUT_MSEC", "CAP_PROP_READ_TIMEOUT_MSEC"):
                    code = getattr(cv2, prop, None)
                    if code is not None and self.cap.isOpened():
                        self.cap.set(code, 5000)
            elif tipo == "video":
                self.cap = cv2.VideoCapture(valor)
            elif tipo == "imagen":
                img = cv2.imread(valor)
                if img is None:
                    self.error = f"No se pudo leer la imagen: {valor}"
                else:
                    self.imagen_fija = img
            else:
                self.error = f"Tipo de fuente no soportado: {tipo}"
                return
            if self.cap is not None and not self.cap.isOpened():
                self.error = f"No se pudo abrir la fuente: {valor}"
                self.cap = None
            if not self.error:
                self.error = None
        except Exception as exc:
            self.error = f"Error al abrir fuente: {exc}"
            self.cap = None

    def _leer_frame(self) -> np.ndarray | None:
        tipo = str(self.cfg.get("tipo", "sin_fuente")).lower()
        if tipo == "demo":
            frame, _ = self.demo.generar()
            return frame
        if self.imagen_fija is not None:
            return self.imagen_fija.copy()
        if self.cap is None:
            self._abrir_captura()
        if self.cap is None:
            return None
        ok, frame = self.cap.read()
        if not ok or frame is None:
            if str(self.cfg.get("tipo", "")).lower() == "video":
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self.cap.read()
            if not ok or frame is None:
                return None
        return frame

    def tick(self) -> None:
        if self._stop.is_set():
            return
        if time.time() < self._proxima:
            return
        fps = max(0.5, min(10.0, float(self.cfg.get("fps", 3.0))))
        self._proxima = time.time() + 1.0 / fps

        capacidad = int(self.zona["capacidad"])
        if self.manual is not None:
            self._tick_manual(capacidad)
            return

        tipo = str(self.cfg.get("tipo", "sin_fuente")).lower()
        if tipo == "sin_fuente" or not str(self.cfg.get("valor", "")).strip() and tipo != "demo":
            self.conteo = 0
            self.estado = "sin_fuente"
            self.actualizado = ahora_iso()
            self.frame_jpg = jpeg(
                anotar(
                    frame_placeholder(self.zona["nombre"], "CONFIGURE UNA CAMARA EN AJUSTES"),
                    [], zona=self.zona["nombre"], conteo=0, capacidad=capacidad,
                    estado="sin_fuente", origen="SIN FUENTE",
                )
            )
            return

        frame = self._leer_frame()
        if frame is None:
            self.error = self.error or "Sin fotograma disponible"
            self.frame_jpg = jpeg(
                anotar(
                    frame_placeholder(self.zona["nombre"], self.error[:58]),
                    [], zona=self.zona["nombre"], conteo=self.conteo,
                    capacidad=capacidad, estado=self.estado, origen="ERROR",
                )
            )
            self.actualizado = ahora_iso()
            return

        if tipo == "demo":
            self.conteo = len(self.demo.objetivos)
            self.crudo = self.conteo
            self.historial.append(self.conteo)
            self.estado = estado_de(self.conteo, capacidad)
            self.actualizado = ahora_iso()
            self.frame_jpg = jpeg(
                anotar(
                    frame, [
                        {
                            "x1": x - 17, "y1": y - 32, "x2": x + 17, "y2": y + 56,
                            "conf": 0.98,
                        }
                        for x, y in self._posiciones_demo(frame.shape[1], frame.shape[0])
                    ],
                    zona=self.zona["nombre"], conteo=self.conteo,
                    capacidad=capacidad, estado=self.estado, origen="SIMULACIÓN",
                    roi=self.cfg.get("roi"),
                )
            )
            return

        cajas, w, h = self.detector.detectar(
            frame, conf=float(self.cfg.get("conf", 0.35)),
            roi=self.cfg.get("roi"), clave=self.zid,
        )
        self.crudo = len(cajas)
        self.historial.append(self.crudo)
        self.conteo = int(round(statistics.median(self.historial))) if self.historial else self.crudo
        self.estado = estado_de(self.conteo, capacidad)
        self.actualizado = ahora_iso()

        origen = {
            "camara": "CAMARA", "video": "VIDEO", "imagen": "IMAGEN"
        }.get(tipo, tipo.upper())
        self.frame_jpg = jpeg(
            anotar(
                frame, cajas, zona=self.zona["nombre"], conteo=self.conteo,
                capacidad=capacidad, estado=self.estado, origen=origen,
                roi=self.cfg.get("roi"),
            )
        )

    def ingestar_frame(self, frame: np.ndarray) -> dict:
        """Procesa un fotograma enviado desde la cámara de un celular."""
        capacidad = int(self.zona["capacidad"])
        cajas, _, _ = self.detector.detectar(
            frame, conf=float(self.cfg.get("conf", 0.35)),
            roi=self.cfg.get("roi"), clave=f"{self.zid}-celular",
        )
        self.crudo = len(cajas)
        self.historial.append(self.crudo)
        self.conteo = int(round(statistics.median(self.historial))) if self.historial else self.crudo
        self.estado = estado_de(self.conteo, capacidad)
        self.actualizado = ahora_iso()
        self.error = None
        self.frame_jpg = jpeg(
            anotar(
                frame, cajas, zona=self.zona["nombre"], conteo=self.conteo,
                capacidad=capacidad, estado=self.estado, origen="CELULAR",
                roi=self.cfg.get("roi"),
            )
        )
        return {
            "conteo": self.conteo, "crudo": self.crudo, "estado": self.estado,
            "capacidad": capacidad, "actualizado": self.actualizado,
        }

    def _posiciones_demo(self, ancho: int, alto: int) -> list[tuple[int, int]]:
        """Posiciones de las figuras sintéticas para superponer las cajas."""
        return [
            (int(p["x"] * ancho), int(p["y"] * alto))
            for p in self.demo.objetivos
        ]

    def _tick_manual(self, capacidad: int) -> None:
        self.conteo = int(self.manual or 0)
        self.crudo = self.conteo
        self.estado = estado_de(self.conteo, capacidad)
        self.actualizado = ahora_iso()
        self.frame_jpg = jpeg(
            anotar(
                frame_placeholder(self.zona["nombre"], "CONTEO MANUAL - VERIFICADO POR OPERARIO"),
                [], zona=self.zona["nombre"], conteo=self.conteo,
                capacidad=capacidad, estado=self.estado, origen="MANUAL",
            )
        )


class GestorAforo:
    """Coordina zonas, modo alterno del Domo, alertas y persistencia."""

    def __init__(self) -> None:
        self.cfg = config.cargar_config()
        self.detector = PersonDetector()
        self.workers: dict[str, TrabajadorZona] = {}
        for z in config.ZONAS:
            self.workers[z["id"]] = TrabajadorZona(
                z, self.cfg["zonas"][z["id"]], self.detector
            )
        self.lock = threading.RLock()
        self.hilo: threading.Thread | None = None
        self._stop = threading.Event()
        self.inicio = ahora_iso()
        self.eventos: deque[dict] = deque(maxlen=400)
        self.ultimo_reporte: str = ""
        self._cargar_eventos()
        self._ultima_alerta: dict[str, float] = {}
        self._ultimo_estado: dict[str, str] = {}
        self.domo = dict(self.cfg["domo"])
        self.consulta = dict(self.cfg.get("consulta") or {"activo": False, "zona": "comicteca"})
        if self.consulta.get("zona") not in config.ZONAS_POR_ID:
            self.consulta["zona"] = "comicteca"
        self.fuente_celular: str | None = None
        self._ultimo_cambio_domo = time.time()
        self._registrar("sistema", "Sistema iniciado", zona="Sistema")

    # ------------------------------------------------------------------
    def _cargar_eventos(self) -> None:
        try:
            if config.EVENTOS_PATH.is_file():
                for linea in config.EVENTOS_PATH.read_text(encoding="utf-8").splitlines():
                    if linea.strip():
                        self.eventos.append(json.loads(linea))
        except Exception:
            pass

    def _registrar(
        self,
        tipo: str,
        mensaje: str,
        *,
        zona: str = "Sistema",
        zona_id: str = "sistema",
        conteo: int | None = None,
        capacidad: int | None = None,
        acciones: str = "",
    ) -> dict:
        ev = {
            "id": f"{int(time.time() * 1000)}-{len(self.eventos)}",
            "ts": ahora_iso(),
            "tipo": tipo,
            "zona": zona,
            "zona_id": zona_id,
            "conteo": conteo,
            "capacidad": capacidad,
            "exceso": (conteo - capacidad) if (conteo is not None and capacidad is not None) else 0,
            "mensaje": mensaje,
            "acciones": acciones,
        }
        with self.lock:
            self.eventos.append(ev)
            try:
                with config.EVENTOS_PATH.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return ev

    # ------------------------------------------------------------------
    def iniciar(self) -> None:
        if self.hilo and self.hilo.is_alive():
            return
        self._stop.clear()
        self.hilo = threading.Thread(target=self._bucle, name="aforo-monitor", daemon=True)
        self.hilo.start()

    def detener(self) -> None:
        self._stop.set()
        for w in self.workers.values():
            w.detener()

    def _poner_en_espera(self, z: dict, mensaje: str) -> None:
        w = self.workers[z["id"]]
        w.conteo = 0
        w.crudo = 0
        w.estado = "inactivo"
        w.actualizado = ahora_iso()
        w.frame_jpg = jpeg(
            anotar(
                frame_placeholder(z["nombre"], mensaje),
                [], zona=z["nombre"], conteo=0,
                capacidad=int(z["capacidad"]), estado="inactivo",
                origen="EN ESPERA",
            )
        )

    def _bucle(self) -> None:
        while not self._stop.is_set():
            try:
                if self.consulta.get("activo"):
                    # Modo consulta: solo se mide el área elegida.
                    zona_id = self.consulta.get("zona")
                    for z in config.ZONAS:
                        if z["id"] != zona_id:
                            self._poner_en_espera(z, "CONSULTA EN OTRA ZONA")
                    z = config.ZONAS_POR_ID[zona_id]
                    if z.get("es_domo") and self.domo.get("piso_activo") != z["id"]:
                        self.domo["piso_activo"] = z["id"]
                        self._ultimo_cambio_domo = time.time()
                        self._guardar()
                    w = self.workers[zona_id]
                    # Si un celular está enviando video, no lo sobrescribe la cámara local.
                    if zona_id != self.fuente_celular:
                        w.tick()
                    self._evaluar_alerta(z, w)
                else:
                    self._verificar_cambio_domo()
                    for z in config.ZONAS:
                        w = self.workers[z["id"]]
                        en_espera_domo = (
                            z.get("es_domo")
                            and self.domo.get("modo") == "alterno"
                            and z["id"] != self.domo.get("piso_activo")
                        )
                        if en_espera_domo:
                            self._poner_en_espera(z, "PISO EN ESPERA - MODO ALTERNO ARTECA")
                            continue
                        w.tick()
                        self._evaluar_alerta(z, w)
                    self._evaluar_domo_combinado()
            except Exception:
                pass
            self._stop.wait(0.25)

    def _verificar_cambio_domo(self) -> None:
        if self.consulta.get("activo"):
            return
        if self.domo.get("modo") != "alterno":
            return
        try:
            minutos = max(1, int(self.domo.get("minutos", 15)))
        except Exception:
            minutos = 15
        if time.time() - self._ultimo_cambio_domo < minutos * 60:
            return
        self._ultimo_cambio_domo = time.time()
        self.domo["piso_activo"] = (
            "domo_p3" if self.domo.get("piso_activo") == "domo_p2" else "domo_p2"
        )
        self._guardar()
        z = config.ZONAS_POR_ID[self.domo["piso_activo"]]
        self._registrar(
            "domo", f"Cambio automático del recorrido ARTECA → {z['nombre']}",
            zona="El Domo · ARTECA", zona_id="domo",
        )

    def _evaluar_alerta(self, z: dict, w: TrabajadorZona) -> None:
        if w.estado in ("inactivo", "sin_fuente"):
            self._ultimo_estado.pop(z["id"], None)
            return
        anterior = self._ultimo_estado.get(z["id"])
        actual = w.estado
        if anterior == actual and actual != "excedido":
            return
        ahora = time.time()
        if actual == "excedido":
            if anterior != "excedido":
                self._ultima_alerta[z["id"]] = ahora
            elif ahora - self._ultima_alerta.get(z["id"], 0) < config.INTERVALO_ALERTA_SEG:
                return
            else:
                self._ultima_alerta[z["id"]] = ahora
            exceso = w.conteo - int(z["capacidad"])
            mensaje = (
                f"AFORO EXCEDIDO en {z['nombre']}: {w.conteo} personas "
                f"({exceso} por encima del límite de {z['capacidad']})."
            )
            self._registrar(
                "excedido", mensaje, zona=z["nombre"], zona_id=z["id"],
                conteo=w.conteo, capacidad=int(z["capacidad"]), acciones=z["acciones"],
            )
        elif anterior == "excedido" and actual != "excedido":
            self._registrar(
                "normalizado",
                f"Aforo normalizado en {z['nombre']}: {w.conteo}/{z['capacidad']} personas.",
                zona=z["nombre"], zona_id=z["id"], conteo=w.conteo,
                capacidad=int(z["capacidad"]),
            )
        elif actual == "preventiva" and anterior != "preventiva":
            self._registrar(
                "preventiva",
                f"Zona preventiva en {z['nombre']}: {w.conteo}/{z['capacidad']} personas "
                f"(≥ {int(config.UMBRAL_PREVENTIVA * 100)}% del aforo).",
                zona=z["nombre"], zona_id=z["id"], conteo=w.conteo,
                capacidad=int(z["capacidad"]),
            )
        self._ultimo_estado[z["id"]] = actual

    def _evaluar_domo_combinado(self) -> None:
        if self.domo.get("modo") != "ambos":
            self._ultimo_estado.pop("domo_total", None)
            return
        total = sum(self.workers[f"domo_p{p}"].conteo for p in (2, 3))
        cap = 110
        actual = "excedido" if total > cap else (
            "preventiva" if total >= cap * config.UMBRAL_PREVENTIVA else "normal"
        )
        anterior = self._ultimo_estado.get("domo_total")
        if actual == "excedido" and (
            anterior != "excedido"
            or time.time() - self._ultima_alerta.get("domo_total", 0) >= config.INTERVALO_ALERTA_SEG
        ):
            self._ultima_alerta["domo_total"] = time.time()
            self._registrar(
                "excedido",
                f"AFORO COMBINADO EXCEDIDO en El Domo (P2+P3): {total}/{cap} personas.",
                zona="El Domo · P2+P3", zona_id="domo_total", conteo=total,
                capacidad=cap,
                acciones="Suspender el ingreso a ambos pisos y reforzar las rutas exteriores.",
            )
        elif anterior == "excedido" and actual != "excedido":
            self._registrar(
                "normalizado",
                f"Aforo combinado del Domo normalizado: {total}/{cap} personas.",
                zona="El Domo · P2+P3", zona_id="domo_total", conteo=total, capacidad=cap,
            )
        self._ultimo_estado["domo_total"] = actual

    # ------------------------------------------------------------------
    def _guardar(self) -> None:
        self.cfg["domo"] = dict(self.domo)
        self.cfg["consulta"] = dict(self.consulta)
        config.guardar_config(self.cfg)

    def configurar_consulta(self, datos: dict) -> dict:
        """Activa el modo consulta enfocado en un área, o vuelve a todas las zonas."""
        activo = bool(datos.get("activo", True))
        zona = str(datos.get("zona") or self.consulta.get("zona") or "comicteca")
        if zona not in config.ZONAS_POR_ID:
            raise ValueError("Zona no encontrada")
        self.consulta = {"activo": activo, "zona": zona}
        # Un cambio manual de área desactiva la cámara del celular que estuviera activa.
        self.fuente_celular = None
        if activo:
            z = config.ZONAS_POR_ID[zona]
            if z.get("es_domo"):
                self.domo["piso_activo"] = zona
                self._ultimo_cambio_domo = time.time()
            self._registrar(
                "consulta", f"Consulta de aforo enfocada en {z['nombre']}",
                zona=z["nombre"], zona_id=zona,
            )
        else:
            self._registrar(
                "consulta", "Monitoreo de todas las zonas reanudado", zona="Sistema"
            )
        self._guardar()
        return self.snapshot()

    def configurar_fuente(self, zid: str, datos: dict) -> dict:
        if zid not in self.workers:
            raise ValueError("Zona no encontrada")
        tipo = str(datos.get("tipo", "sin_fuente")).lower()
        if tipo not in ("demo", "camara", "video", "imagen", "sin_fuente", "manual"):
            raise ValueError("Tipo de fuente no válido")
        w = self.workers[zid]
        if tipo == "manual":
            w.activar_manual(int(datos.get("conteo", w.conteo)))
        else:
            w.manual = None
            w.cfg_antes_manual = None
            cfg = {
                "tipo": tipo,
                "valor": str(datos.get("valor", "")).strip(),
                "roi": datos.get("roi", w.cfg.get("roi", [0, 0, 1, 1])),
                "conf": float(datos.get("conf", w.cfg.get("conf", 0.35))),
                "fps": float(datos.get("fps", w.cfg.get("fps", 3.0))),
            }
            w.aplicar_config(cfg)
            self.cfg["zonas"][zid] = cfg
            self._guardar()
        z = config.ZONAS_POR_ID[zid]
        self._registrar(
            "config", f"Fuente de {z['nombre']} configurada: {tipo}",
            zona=z["nombre"], zona_id=zid,
        )
        return self.snapshot()

    def ajustar_manual(self, zid: str, delta: int) -> dict:
        w = self.workers[zid]
        conteo = w.ajustar_manual(int(delta))
        z = config.ZONAS_POR_ID[zid]
        self._registrar(
            "manual", f"Conteo manual en {z['nombre']}: {conteo} personas",
            zona=z["nombre"], zona_id=zid, conteo=conteo, capacidad=int(z["capacidad"]),
        )
        return self.snapshot()

    def restaurar_automatico(self, zid: str) -> dict:
        self.workers[zid].restaurar_automatico()
        z = config.ZONAS_POR_ID[zid]
        self._registrar(
            "config", f"Conteo automático restaurado en {z['nombre']}",
            zona=z["nombre"], zona_id=zid,
        )
        return self.snapshot()

    def configurar_domo(self, datos: dict) -> dict:
        modo = str(datos.get("modo", "alterno")).lower()
        if modo not in ("alterno", "ambos"):
            raise ValueError("Modo no válido")
        self.domo["modo"] = modo
        if datos.get("piso_activo") in ("domo_p2", "domo_p3"):
            self.domo["piso_activo"] = datos["piso_activo"]
        if datos.get("minutos") is not None:
            self.domo["minutos"] = max(1, min(120, int(datos["minutos"])))
        self._ultimo_cambio_domo = time.time()
        self._guardar()
        self._registrar(
            "domo",
            f"Modo del Domo actualizado: {modo}"
            + (f" · piso activo {self.domo['piso_activo']}" if modo == "alterno" else " · 110 combinados"),
            zona="El Domo · ARTECA", zona_id="domo",
        )
        return self.snapshot()

    def recibir_frame_celular(self, zona_id: str, datos_frame: str) -> dict:
        """Recibe un JPEG en base64 desde el celular y actualiza el conteo del área."""
        if zona_id not in self.workers:
            raise ValueError("Zona no encontrada")
        raw = str(datos_frame or "").strip()
        if raw.startswith("data:image"):
            raw = raw.split(",", 1)[-1]
        if not raw or len(raw) > 3_500_000:
            raise ValueError("Fotograma vacío o demasiado grande")
        try:
            buffer = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError("Fotograma no válido") from exc
        if len(buffer) > 2_500_000:
            raise ValueError("Fotograma demasiado grande")
        frame = cv2.imdecode(np.frombuffer(buffer, np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("No se pudo leer la imagen")
        if frame.shape[0] < 120 or frame.shape[1] < 160:
            raise ValueError("Imagen demasiado pequeña")

        z = config.ZONAS_POR_ID[zona_id]
        if self.fuente_celular != zona_id:
            self.fuente_celular = zona_id
            self.consulta = {"activo": True, "zona": zona_id}
            w = self.workers[zona_id]
            w.historial.clear()
            self._ultimo_estado.pop(zona_id, None)
            self._registrar(
                "celular",
                f"Medición activada con la cámara del celular en {z['nombre']}",
                zona=z["nombre"], zona_id=zona_id,
            )
            self._guardar()

        w = self.workers[zona_id]
        resultado = w.ingestar_frame(frame)
        self._evaluar_alerta(z, w)
        anotado = base64.b64encode(w.frame_jpg).decode("ascii")
        return {
            "ok": True, "zona": z["nombre"], "origen": "celular",
            "frame": anotado, **resultado,
        }

    def frame(self, zid: str) -> bytes:
        return self.workers[zid].frame_jpg

    def snapshot(self) -> dict:
        zonas = []
        total = 0
        activas = 0
        alertas = 0
        for z in config.ZONAS:
            w = self.workers[z["id"]]
            info = {
                "id": z["id"], "nombre": z["nombre"], "ubicacion": z["ubicacion"],
                "capacidad": int(z["capacidad"]), "area_m2": z["area_m2"],
                "indice_ns": z["indice_ns"], "aforo_teorico": z["aforo_teorico"],
                "color": z["color"], "icono": z["icono"], "fuente": z["fuente"],
                "detalle": z["detalle"], "acciones": z["acciones"],
                "nota_tecnica": z.get("nota_tecnica", ""),
                "conteo": w.conteo, "crudo": w.crudo, "estado": w.estado,
                "actualizado": w.actualizado, "error": w.error,
                "manual": w.manual is not None,
                "tipo_fuente": (
                    "celular" if self.fuente_celular == z["id"]
                    else str(w.cfg.get("tipo", "sin_fuente"))
                ),
                "valor_fuente": str(w.cfg.get("valor", "")),
                "roi": w.cfg.get("roi", [0, 0, 1, 1]),
                "conf": w.cfg.get("conf", 0.35), "fps": w.cfg.get("fps", 3.0),
                "motor": self.detector.motor,
            }
            zonas.append(info)
            if w.estado not in ("inactivo", "sin_fuente"):
                total += w.conteo
                activas += 1
            if w.estado == "excedido":
                alertas += 1

        domo_total = sum(self.workers[f"domo_p{p}"].conteo for p in (2, 3))
        domo_estado = "inactivo"
        if self.domo["modo"] == "ambos":
            domo_estado = "excedido" if domo_total > 110 else (
                "preventiva" if domo_total >= 88 else "normal"
            )
        with self.lock:
            eventos = list(reversed(self.eventos))[:30]
        return {
            "servidor": {
                "inicio": self.inicio, "hora": ahora_iso(),
                "motor": self.detector.motor,
                "modelo": str(config.MODELO_PERSONAS.name),
                "institucion": config.INSTITUCION,
                "evento": config.EVENTO_ARTECA,
                "desarrollador": config.DESARROLLADOR,
                "contacto": config.CONTACTO,
                "licencia_sst": config.LICENCIA_SST,
            },
            "resumen": {
                "total_personas": total, "zonas_activas": activas,
                "alertas_activas": alertas + (1 if domo_estado == "excedido" else 0),
            },
            "zonas": zonas,
            "domo": {
                "modo": self.domo["modo"], "piso_activo": self.domo["piso_activo"],
                "minutos": self.domo["minutos"], "total": domo_total,
                "capacidad_combinada": 110, "estado": domo_estado,
            },
            "consulta": dict(self.consulta),
            "eventos": eventos,
        }

    def csv_reporte(self) -> str:
        """Entrega el conteo por área + el historial, y deja copia registrada.

        Cada descarga:
          1. registra un evento ``reporte`` en el historial SG-SST;
          2. incluye una fila por área con su conteo, cupo y estado;
          3. incluye una fila de TOTAL GENERAL;
          4. guarda una copia con fecha en ``data/reportes/``.
        """
        stamp = datetime.now(LOCAL_TZ).strftime("%Y%m%d_%H%M%S")
        nombre = f"reporte_aforo_{stamp}.csv"
        self.ultimo_reporte = nombre
        self._registrar(
            "reporte",
            f"Reporte CSV generado: {nombre} · conteo por área registrado",
            zona="Sistema",
        )

        snap = self.snapshot()
        campos = [
            "ts", "tipo", "zona", "conteo", "capacidad", "exceso",
            "mensaje", "acciones", "zona_id", "porcentaje", "estado", "seccion",
        ]
        filas: list[dict] = []
        hora = snap["servidor"]["hora"]

        # 1) Conteo total por área.
        for info in snap["zonas"]:
            conteo = int(info["conteo"])
            cap = int(info["capacidad"])
            pct = (conteo / cap * 100.0) if cap else 0.0
            exceso = max(0, conteo - cap)
            filas.append({
                "ts": hora,
                "tipo": "conteo_area",
                "zona": info["nombre"],
                "conteo": conteo,
                "capacidad": cap,
                "exceso": exceso,
                "mensaje": (
                    f"{info['nombre']}: {conteo}/{cap} personas ({pct:.1f}%). "
                    f"Estado: {info['estado']}."
                ),
                "acciones": info["acciones"] if info["estado"] == "excedido" else "",
                "zona_id": info["id"],
                "porcentaje": f"{pct:.1f}%",
                "estado": info["estado"],
                "seccion": "RESUMEN_POR_AREA",
            })

        # 2) Total general del momento del corte.
        resumen = snap["resumen"]
        caps_activas = sum(
            int(z["capacidad"]) for z in snap["zonas"]
            if z["estado"] not in ("inactivo", "sin_fuente")
        )
        filas.append({
            "ts": hora,
            "tipo": "conteo_total",
            "zona": "TOTAL GENERAL",
            "conteo": int(resumen["total_personas"]),
            "capacidad": caps_activas,
            "exceso": "",
            "mensaje": (
                f"Total general: {resumen['total_personas']} personas en "
                f"{resumen['zonas_activas']} área(s) activa(s)."
            ),
            "acciones": "",
            "zona_id": "total",
            "porcentaje": "",
            "estado": "",
            "seccion": "TOTAL_GENERAL",
        })

        # 3) Historial de eventos (trazabilidad).
        with self.lock:
            eventos = list(reversed(self.eventos))
        for ev in eventos:
            conteo = ev.get("conteo")
            cap = ev.get("capacidad")
            pct = (
                f"{(int(conteo) / int(cap) * 100.0):.1f}%"
                if conteo is not None and cap else ""
            )
            filas.append({
                "ts": ev.get("ts", ""),
                "tipo": ev.get("tipo", ""),
                "zona": ev.get("zona", ""),
                "conteo": conteo if conteo is not None else "",
                "capacidad": cap if cap is not None else "",
                "exceso": ev.get("exceso", 0),
                "mensaje": ev.get("mensaje", ""),
                "acciones": ev.get("acciones", ""),
                "zona_id": ev.get("zona_id", ""),
                "porcentaje": pct,
                "estado": "",
                "seccion": "REGISTRO_EVENTOS",
            })

        buf = io.StringIO(newline="")
        escritor = csv.DictWriter(buf, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(filas)
        contenido = buf.getvalue()

        # Copia persistente con fecha, además del historial en eventos.jsonl.
        try:
            config.REPORTES_DIR.mkdir(parents=True, exist_ok=True)
            (config.REPORTES_DIR / nombre).write_text(
                "\ufeff" + contenido, encoding="utf-8"
            )
        except Exception:
            pass
        return contenido
