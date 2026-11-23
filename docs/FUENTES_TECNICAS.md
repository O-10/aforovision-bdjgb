# Fuentes técnicas consultadas

Ruta base: `C:\Users\Oscar\Documents\59. Biblioteca_Departamental`

## 1. Comicteca — 60 personas

- **Mapa_Aforos_y_Fuentes_SGSST.pdf**: 302,00 m², aforo teórico 66 (NSR-10 Título K, 4,6 m²/persona), aforo operativo autorizado **60 personas** por margen preventivo de 6 (mobiliario y circulación). Condicionantes: rutas y salidas libres, gabinetes e hidrantes presurizados, luces de emergencia, inducción al personal y simulacro previo.
- **CONCEPTO DE HABILITACIÓN CONDICIONADA PARA EL ÁREA DE LA COMICTECA.pdf** (SiGPRO Colombia S.A.S. / Positiva ARL, Michaell Meneses Medina).

## 2. El Domo · Pisos 2 y 3 — 56 y 54 personas (ARTECA)

- **Domo_aforo calculo\concepto-habitabilidad-aforo-domo-arteca_Os.pdf** (Oscar Iván Solarte Cerón, Res. 3702 de 2023): exposición ARTECA del 18 al 22 de noviembre de 2026.
  - Piso 2: 314,16 m² brutos − 56,50 m² núcleo/escalera = 257,66 m² netos / 4,60 = **56 personas en simultáneo**.
  - Piso 3: 314,16 m² brutos − 64,16 m² vacío/mezanine = 250,00 m² netos / 4,60 = **54 personas en simultáneo**.
  - Combinado: 507,66 m² netos = **110 personas en simultáneo**.
  - Clasificación estructural VERDE (EME AL CUBO S.A.S.). Acceso y evacuación exclusivamente por vías exteriores de la plazoleta; prohibido el tránsito por pasillos internos del edificio principal. Muro no estructural del Piso 2 reparado.
- **Domo_aforo calculo\Informe_de_habitabilidad_post_corregido(1) (2).pdf** (EME AL CUBO S.A.S., Ing. Juan Salvador Mantilla).
- **Información Biblioteca\Capacidad en el Domo.pdf** (Angela Berrío, Lic. 0356): primer piso 96,90 m² netos, 12–15 puestos óptimos, 18 máximo en emergencia.

## 3. Plazoleta de Cultura — 80 personas (parámetro de la aplicación)

- **Información Biblioteca\Concepto técnico de Aforo y Ocupación Máxima de la plazoleta de la lectura.pdf** (Angela Berrío, 28/10/2026): área útil aproximada 300 m² (de 360 m²); picnic/cine 70–75 personas, eventos infantiles/exposiciones 60–65; nota SST: limitar el ingreso a **60 personas** por la capacidad de evacuación de las gradas angostas. Exige baranda rígida de 1,20 m, pasamanos seguro, baños portátiles, lavamanos, extintores ABC, camilla y botiquín.
- La aplicación usa **80 personas** por instrucción expresa del usuario y muestra la advertencia técnica en la interfaz para su validación.

## 4. Consideración de diseño

Los aforos se configuran en `config.py` y se muestran en el panel *Fuentes técnicas*. El sistema no modifica los dictámenes: solo parametriza el control y deja trazabilidad de cada límite.
