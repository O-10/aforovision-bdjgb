# -*- coding: utf-8 -*-
"""Configuración técnica y parametrización de aforos.

Biblioteca Departamental Jorge Garcés Borrero — Santiago de Cali.
Desarrollado por Oscar Iván Solarte Cerón — 3154013707.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
_data_env = os.getenv("AFORO_DATA_DIR", "").strip()
DATA_DIR = Path(_data_env).expanduser().resolve() if _data_env else BASE_DIR / "data"
REPORTES_DIR = DATA_DIR / "reportes"
MODELOS_DIR = BASE_DIR / "modelos"
MODELO_PERSONAS = MODELOS_DIR / "yolov8n.pt"
CONFIG_PATH = DATA_DIR / "config.json"
EVENTOS_PATH = DATA_DIR / "eventos.jsonl"

DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTES_DIR.mkdir(parents=True, exist_ok=True)
MODELOS_DIR.mkdir(parents=True, exist_ok=True)

INSTITUCION = "Biblioteca Departamental Jorge Garcés Borrero"
EVENTO_ARTECA = "Exposición Artística y Cultural ARTECA · 18 al 22 de noviembre de 2026"
DESARROLLADOR = "Oscar Iván Solarte Cerón"
CONTACTO = "3154013707"
LICENCIA_SST = "Resolución 3702 de 2023"

# ---------------------------------------------------------------------------
# Zonas. Los aforos son los autorizados por el usuario / dictámenes SG-SST.
# ---------------------------------------------------------------------------
ZONAS: list[dict] = [
    {
        "id": "comicteca",
        "nombre": "Comicteca",
        "ubicacion": "Edificio Sur · Segundo piso",
        "capacidad": 60,
        "area_m2": 302.0,
        "indice_ns": 4.6,
        "aforo_teorico": 66,
        "color": "#38bdf8",
        "icono": "CM",
        "fuente": (
            "CONCEPTO DE HABILITACIÓN CONDICIONADA PARA EL ÁREA DE LA COMICTECA "
            "(SiGPRO Colombia S.A.S. / Positiva ARL, Michaell Meneses Medina); "
            "Mapa Maestro de Aforos y Fuentes SG-SST."
        ),
        "detalle": (
            "302,00 m² / 4,6 m² por persona = 66 personas teóricas (NSR-10 Título K). "
            "Margen preventivo de 6 personas por mobiliario y circulación → aforo operativo 60. "
            "Requiere rutas libres, hidrantes y luces de emergencia revisadas y simulacro previo."
        ),
        "acciones": (
            "Suspender el ingreso, reforzar control en el acceso y mantener despejadas las rutas de evacuación."
        ),
    },
    {
        "id": "domo_p2",
        "nombre": "El Domo · Piso 2",
        "ubicacion": "Edificio Norte · Exposición ARTECA",
        "capacidad": 56,
        "area_m2": 257.66,
        "indice_ns": 4.6,
        "aforo_teorico": 56,
        "color": "#a78bfa",
        "icono": "D2",
        "es_domo": True,
        "piso": 2,
        "fuente": (
            "CONCEPTO TÉCNICO DE HABITABILIDAD ESTRUCTURAL Y CÁLCULO DE AFORO OPERATIVO: EL DOMO "
            "(Oscar Iván Solarte Cerón, Res. 3702 de 2023)."
        ),
        "detalle": (
            "Área neta 257,66 m² (314,16 m² brutos − 56,50 m² de núcleo/escalera) / 4,60 m² por persona "
            "= 56 personas en simultáneo. Escenario de exhibición cultural / galería NSR-10 Título K. "
            "Acceso y evacuación exclusivamente por las vías exteriores de la plazoleta."
        ),
        "acciones": (
            "Cerrar el acceso al Piso 2, desviar el flujo al Piso 3 (si está habilitado) y verificar las rutas exteriores."
        ),
    },
    {
        "id": "domo_p3",
        "nombre": "El Domo · Piso 3",
        "ubicacion": "Edificio Norte · Mezanine ARTECA",
        "capacidad": 54,
        "area_m2": 250.0,
        "indice_ns": 4.6,
        "aforo_teorico": 54,
        "color": "#f472b6",
        "icono": "D3",
        "es_domo": True,
        "piso": 3,
        "fuente": (
            "CONCEPTO TÉCNICO DE HABITABILIDAD ESTRUCTURAL Y CÁLCULO DE AFORO OPERATIVO: EL DOMO "
            "(Oscar Iván Solarte Cerón, Res. 3702 de 2023)."
        ),
        "detalle": (
            "Área neta 250,00 m² (314,16 m² brutos − 64,16 m² de vacío/mezanine) / 4,60 m² por persona "
            "= 54 personas en simultáneo. Escenario de exhibición cultural / galería NSR-10 Título K. "
            "El inventario total combinado de los pisos 2 y 3 es de 110 personas."
        ),
        "acciones": (
            "Cerrar el acceso al Piso 3, desviar el flujo al Piso 2 (si está habilitado) y verificando las rutas exteriores."
        ),
    },
    {
        "id": "plazoleta",
        "nombre": "Plazoleta de Cultura",
        "ubicacion": "Zona verde y cubierta · Picnic literario / proyecciones",
        "capacidad": 80,
        "area_m2": 300.0,
        "indice_ns": None,
        "aforo_teorico": None,
        "color": "#34d399",
        "icono": "PC",
        "fuente": (
            "Parametrización operativa solicitada por la Biblioteca (aforo 80 personas). "
            "Contraste: CONCEPTO TÉCNICO DE AFORO Y OCUPACIÓN MÁXIMA DE LA PLAZOLETA DE LA LECTURA "
            "(Angela Berrío, Lic. 0356, 28/10/2026)."
        ),
        "detalle": (
            "El módulo aplica 80 personas como límite operativo parametrizado. El concepto técnico de referencia "
            "sugiere 70–75 personas sentadas (cine/picnic), 60–65 en movimiento y limita el ingreso a 60 por el "
            "cuello de botella de las gradas angostas. Verificar este parámetro antes de la operación."
        ),
        "nota_tecnica": (
            "⚠ El dictamen de SST recomienda 60–75 personas y exige baranda rígida de 1,20 m, pasamanos seguro, "
            "baños portátiles y Extintores ABC. El valor 80 se usa por instrucción del usuario."
        ),
        "acciones": (
            "Detener el ingreso a la plazoleta, abrir una segunda ruta de salida y reforzar la vigilancia en gradas y borde."
        ),
    },
]

ZONAS_POR_ID = {z["id"]: z for z in ZONAS}


def configuracion_por_defecto() -> dict:
    """Configuración inicial: modo demo para visualizar sin cámaras físicas."""
    zonas = {}
    for z in ZONAS:
        zonas[z["id"]] = {
            "tipo": "demo",
            "valor": "",
            "roi": [0.0, 0.0, 1.0, 1.0],
            "conf": 0.35,
            "fps": 3.0,
        }
    return {
        "zonas": zonas,
        "domo": {"modo": "alterno", "piso_activo": "domo_p2", "minutos": 15},
        "consulta": {"activo": False, "zona": "comicteca"},
        "sonido": True,
    }


def cargar_config() -> dict:
    base = configuracion_por_defecto()
    try:
        if CONFIG_PATH.is_file():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for zid, cfg in (data.get("zonas") or {}).items():
                if zid in base["zonas"]:
                    base["zonas"][zid].update(cfg)
            base["domo"].update(data.get("domo") or {})
            base["consulta"].update(data.get("consulta") or {})
            base["sonido"] = bool(data.get("sonido", True))
    except Exception:
        pass
    return base


def guardar_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# Umbrales de estado (porcentaje de ocupación)
UMBRAL_PREVENTIVA = 0.80
INTERVALO_ALERTA_SEG = 20  # reiterar aviso mientras persista el exceso
HISTORIAL = 7
