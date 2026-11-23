/* AforoVision BDJGB — panel de control en tiempo real */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let zonaActual = "comicteca";
  let estadoActual = null;
  let sonidoActivo = false;
  let audioCtx = null;
  let ultimoEventoAlerta = null;
  let alertaCerradaPara = "";
  let zonaFormCargada = null;
  let eventosSignature = "";

  const ETIQUETAS = {
    normal: "Normal",
    preventiva: "Preventiva",
    excedido: "Excedido",
    inactivo: "En espera",
    sin_fuente: "Sin fuente",
  };

  async function api(url, opciones = {}) {
    const resp = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...opciones,
    });
    if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).detail || resp.statusText);
    return resp.json();
  }

  function fmtHora(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("es-CO", {
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  }

  function beep() {
    if (!sonidoActivo) return;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const t = audioCtx.currentTime;
      [0, 0.22].forEach((offset) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "square";
        osc.frequency.value = offset ? 740 : 880;
        gain.gain.setValueAtTime(0.0001, t + offset);
        gain.gain.exponentialRampToValueAtTime(0.12, t + offset + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + offset + 0.17);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(t + offset);
        osc.stop(t + offset + 0.18);
      });
    } catch (_) { /* audio no disponible */ }
  }

  function inicializarSelect(zonas) {
    const sel = $("selectZona");
    if (sel.options.length) return;
    zonas.forEach((z) => {
      const op = document.createElement("option");
      op.value = z.id;
      op.textContent = z.nombre;
      sel.appendChild(op);
    });
    sel.value = zonaActual;
    sel.addEventListener("change", () => seleccionarZona(sel.value));
    $("video").src = `/api/video/${zonaActual}`;
  }

  function pintarResumen(e) {
    $("statPersonas").textContent = e.resumen.total_personas;
    $("statZonas").textContent = `${e.resumen.zonas_activas} / ${e.zonas.length}`;
    $("statAlertas").textContent = e.resumen.alertas_activas;
    $("statMotor").textContent = e.servidor.motor;
    $("statModelo").textContent = e.servidor.modelo;
    $("hora").textContent = `${fmtHora(e.servidor.hora)} · Bogotá`;
  }

  function pintarDomo(e) {
    const d = e.domo;
    $("domoTotal").innerHTML = `${d.total} <small style="color:var(--muted);font-size:.7rem">/ ${d.capacidad_combinada}</small>`;
    const pct = Math.min(100, (d.total / d.capacidad_combinada) * 100);
    const barra = $("barraDomo");
    barra.className = `barra ${d.estado === "normal" ? "" : d.estado}`;
    barra.firstElementChild.style.width = `${pct}%`;
    $("domoEstado").textContent = d.modo === "alterno"
      ? `Modo alterno · piso activo: ${d.piso_activo === "domo_p2" ? "Piso 2 (56)" : "Piso 3 (54)"} · rotación cada ${d.minutos} min`
      : `Ambos pisos habilitados · límite combinado 110 personas · estado ${ETIQUETAS[d.estado] || d.estado}`;
    $("pisoActivo").value = d.piso_activo;
    $("minutosDomo").value = d.minutos;
    document.querySelectorAll("#segmentoDomo button").forEach((b) => {
      b.classList.toggle("activo", b.dataset.modo === d.modo);
    });
    $("pisoActivo").disabled = d.modo !== "alterno";
    $("minutosDomo").disabled = d.modo !== "alterno";
  }

  function pintarCards(e) {
    const grid = $("zonasGrid");
    grid.innerHTML = "";
    e.zonas.forEach((z) => {
      const pct = Math.min(100, Math.round((z.conteo / z.capacidad) * 100));
      const card = document.createElement("article");
      card.className = `zcard ${z.estado} ${z.id === zonaActual ? "seleccionada" : ""}`;
      card.style.setProperty("--zcolor", z.color);
      card.innerHTML = `
        <div class="cab">
          <div class="icono">${z.icono}</div>
          <div style="display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end">
            <span class="badge ${z.estado}">${ETIQUETAS[z.estado] || z.estado}</span>
            ${z.tipo_fuente === "demo" ? '<span class="badge demo">Demo</span>' : ""}
            ${z.manual ? '<span class="badge">Manual</span>' : ""}
          </div>
        </div>
        <h3>${z.nombre}</h3>
        <div class="ubic">${z.ubicacion}</div>
        <div class="conteo">${z.conteo} <small>/ ${z.capacidad}</small></div>
        <div class="pct">${pct}% del aforo autorizado</div>
        <div class="barra ${z.estado === "normal" ? "" : z.estado}"><i style="width:${pct}%"></i></div>
        ${z.nota_tecnica ? `<div class="nota" style="margin-top:10px">${z.nota_tecnica}</div>` : ""}
      `;
      card.addEventListener("click", () => seleccionarZona(z.id));
      grid.appendChild(card);
    });
  }

  function pintarZonaSeleccionada(e) {
    const z = e.zonas.find((x) => x.id === zonaActual) || e.zonas[0];
    if (!z) return;
    $("estadoVideo").className = `badge ${z.estado}`;
    $("estadoVideo").textContent = ETIQUETAS[z.estado] || z.estado;
    $("chipFuente").textContent = `Fuente: ${z.tipo_fuente.toUpperCase()}${z.valor_fuente ? " · " + z.valor_fuente : ""}`;
    $("chipConteo").textContent = `${z.conteo} / ${z.capacidad}`;
    $("manualCount").textContent = z.conteo;
    $("infoTitulo").textContent = `${z.nombre} · ${z.capacidad} personas`;
    $("infoDetalle").textContent = z.detalle;
    const nota = $("infoNota");
    if (z.nota_tecnica) {
      nota.hidden = false;
      nota.textContent = z.nota_tecnica;
    } else {
      nota.hidden = true;
    }
    $("infoFuente").textContent = `Soporte: ${z.fuente}`;
    if (z.error) $("infoFuente").textContent += ` · Error: ${z.error}`;

    if (zonaFormCargada !== z.id) {
      zonaFormCargada = z.id;
      $("fuenteTipo").value = z.manual ? "manual" : z.tipo_fuente;
      $("fuenteValor").value = z.valor_fuente || "";
      $("fuenteFps").value = z.fps;
      $("fuenteConf").value = z.conf;
      const r = z.roi || [0, 0, 1, 1];
      ["roiX1", "roiY1", "roiX2", "roiY2"].forEach((id, i) => { $(id).value = r[i]; });
    }
  }

  function pintarEventos(e) {
    const cont = $("eventos");
    const sig = e.eventos.map((x) => x.id).join("|");
    $("eventosCount").textContent = `${e.eventos.length} eventos recientes`;
    if (sig === eventosSignature) return;
    eventosSignature = sig;
    if (!e.eventos.length) {
      cont.innerHTML = '<div class="vacio">Sin eventos registrados.</div>';
      return;
    }
    cont.innerHTML = e.eventos.slice(0, 18).map((ev) => `
      <div class="evento ${ev.tipo}">
        <span class="hora">${fmtHora(ev.ts)}</span>
        <span class="tipo">${ev.tipo}</span>
        <div>
          <strong>${ev.zona}</strong> · ${ev.mensaje}
          ${ev.acciones ? `<div class="acciones">→ ${ev.acciones}</div>` : ""}
        </div>
      </div>`).join("");
  }

  function pintarTabla(e) {
    const tb = $("tablaParametros");
    tb.innerHTML = e.zonas.map((z) => `
      <tr>
        <td><strong>${z.nombre}</strong></td>
        <td>${z.area_m2 ? z.area_m2.toLocaleString("es-CO", { maximumFractionDigits: 2 }) + " m²" : "—"}</td>
        <td>${z.indice_ns ? z.indice_ns.toFixed(2) + " m²/pers." : "—"}</td>
        <td><strong style="color:${z.color}">${z.capacidad}</strong> pers.</td>
      </tr>`).join("");
  }

  function pintarAlerta(e) {
    const excedidas = e.zonas.filter((z) => z.estado === "excedido");
    const domoExcedido = e.domo.modo === "ambos" && e.domo.estado === "excedido";
    const banner = $("alertaGlobal");
    if (!excedidas.length && !domoExcedido) {
      banner.classList.remove("visible");
      alertaCerradaPara = "";
      return;
    }
    const detalle = excedidas
      .map((z) => `${z.nombre}: ${z.conteo}/${z.capacidad} (exceso ${z.conteo - z.capacidad})`)
      .join(" · ");
    const texto = domoExcedido
      ? `${detalle}${detalle ? " · " : ""}Domo combinado: ${e.domo.total}/110`
      : detalle;
    const firma = texto;
    if (firma === alertaCerradaPara) {
      banner.classList.remove("visible");
      return;
    }
    banner.classList.add("visible");
    $("alertaTitulo").textContent = "AFORO EXCEDIDO — SUSPENDER INGRESO";
    $("alertaTexto").textContent = `${texto}. Aplique las acciones del plan de emergencias y registre el evento.`;

    const nuevos = e.eventos.filter((x) => x.tipo === "excedido");
    const id = nuevos.length ? nuevos[0].id : null;
    if (id && id !== ultimoEventoAlerta) {
      ultimoEventoAlerta = id;
      beep();
    }
  }

  function pintarSelector(e) {
    const cont = $("selectorAreas");
    cont.innerHTML = e.zonas.map((z) => {
      const activo = e.consulta?.activo && e.consulta.zona === z.id;
      return `
        <button class="area-btn ${activo ? "activo" : ""}" data-zona="${z.id}" style="--zcolor:${z.color}">
          <span class="nombre">${z.nombre}</span>
          <span class="cupo">Cupo: ${z.capacidad} personas</span>
          <span class="mini">${z.estado === "inactivo" ? "—" : z.conteo} <small style="color:var(--muted);font-size:.65rem">en vivo</small></span>
        </button>`;
    }).join("");
  }

  function pintarConsulta(e) {
    const c = e.consulta || { activo: false, zona: zonaActual };
    const activo = !!c.activo;
    $("btnVerTodas").hidden = !activo;
    const destacado = $("consultaDestacado");
    destacado.hidden = !activo;
    if (!activo) return;

    const z = e.zonas.find((x) => x.id === c.zona);
    if (!z) return;
    destacado.className = `consulta-destacado ${z.estado === "excedido" ? "excedido" : ""}`;
    $("consultaCount").textContent = z.conteo;
    $("consultaCap").textContent = `/ ${z.capacidad} personas`;
    $("consultaZona").textContent = z.nombre;
    $("consultaEstado").className = `badge ${z.estado}`;
    $("consultaEstado").textContent = ETIQUETAS[z.estado] || z.estado;

    const aviso = $("consultaAviso");
    if (z.tipo_fuente === "demo") {
      aviso.textContent = "Modo DEMO: cifra simulada. Configure una cámara en ‘Configuración de la fuente’ para medir en tiempo real.";
    } else if (z.tipo_fuente === "sin_fuente") {
      aviso.textContent = "Sin cámara asignada. Configure la fuente para comenzar a medir.";
    } else if (z.manual) {
      aviso.textContent = "Conteo manual verificado. Restaure el automático para volver a la cámara.";
    } else if (z.error) {
      aviso.textContent = `Error de captura: ${z.error}`;
    } else {
      const mismaCamara = z.tipo_fuente === "camara"
        ? e.zonas.filter((x) => x.tipo_fuente === "camara" && x.valor_fuente === z.valor_fuente).length
        : 0;
      const avisoCamara = mismaCamara > 1
        ? ` ⚠ Cámara compartida con ${mismaCamara - 1} área(s): diríjala al área seleccionada; el conteo es lo que ve la cámara.`
        : "";
      aviso.textContent = `Midiendo en tiempo real · ${z.tipo_fuente.toUpperCase()} · ${z.fps} FPS · ${z.detalle.slice(0, 95)}…${avisoCamara}`;
    }
  }

  async function seleccionarZona(id) {
    zonaActual = id;
    $("selectZona").value = id;
    $("video").src = `/api/video/${id}`;
    zonaFormCargada = null;
    try {
      await api("/api/consulta", {
        method: "POST", body: JSON.stringify({ activo: true, zona: id }),
      });
    } catch (_) { /* se reflejará en el siguiente refresco */ }
    refrescar();
  }

  function pintar(e) {
    if (!e) return;
    estadoActual = e;
    if (e.consulta?.activo && e.consulta.zona !== zonaActual) {
      zonaActual = e.consulta.zona;
      $("video").src = `/api/video/${zonaActual}`;
      zonaFormCargada = null;
    }
    inicializarSelect(e.zonas);
    pintarResumen(e);
    pintarDomo(e);
    pintarCards(e);
    pintarSelector(e);
    pintarConsulta(e);
    pintarZonaSeleccionada(e);
    pintarEventos(e);
    pintarTabla(e);
    pintarAlerta(e);
  }

  async function refrescar() {
    try {
      pintar(await api("/api/estado"));
    } catch (_) { /* servidor temporalmente no disponible */ }
  }

  async function abrirFuentes() {
    try {
      const f = await api("/api/fuentes");
      $("modalSubtitulo").textContent = `${f.institucion} · ${f.evento} · Desarrollado por ${f.desarrollador} (${f.contacto})`;
      $("modalFuentesContenido").innerHTML = f.zonas.map((z) => `
        <div class="fuente-item">
          <h3>${z.nombre} · ${z.capacidad} personas</h3>
          <p><strong>Soporte:</strong> ${z.fuente}</p>
          <p>${z.detalle}</p>
          ${z.nota_tecnica ? `<p class="nota">${z.nota_tecnica}</p>` : ""}
        </div>`).join("") + `
        <div class="fuente-item">
          <h3>Documentos de referencia</h3>
          <p>${f.documentos.join(" · ")}</p>
        </div>`;
      $("modalFuentes").classList.add("visible");
    } catch (err) {
      alert("No se pudo cargar la información de fuentes: " + err.message);
    }
  }

  function enlazar() {
    $("selectorAreas").addEventListener("click", (ev) => {
      const btn = ev.target.closest(".area-btn");
      if (btn) seleccionarZona(btn.dataset.zona);
    });
    $("btnVerTodas").addEventListener("click", async () => {
      await api("/api/consulta", {
        method: "POST", body: JSON.stringify({ activo: false }),
      });
      refrescar();
    });

    $("btnSonido").addEventListener("click", () => {
      sonidoActivo = !sonidoActivo;
      $("btnSonido").textContent = sonidoActivo ? "🔊 Sonido activo" : "🔇 Activar sonido";
      $("btnSonido").classList.toggle("on", sonidoActivo);
      if (sonidoActivo) beep();
    });
    $("btnFuentes").addEventListener("click", abrirFuentes);
    $("btnCerrarFuentes").addEventListener("click", () => $("modalFuentes").classList.remove("visible"));
    $("modalFuentes").addEventListener("click", (ev) => {
      if (ev.target === $("modalFuentes")) $("modalFuentes").classList.remove("visible");
    });
    $("btnCerrarAlerta").addEventListener("click", () => {
      const z = (estadoActual?.zonas || []).filter((x) => x.estado === "excedido")
        .map((x) => `${x.nombre}: ${x.conteo}/${x.capacidad}`).join(" · ");
      alertaCerradaPara = z || "domo";
      $("alertaGlobal").classList.remove("visible");
    });

    $("btnMenos").addEventListener("click", async () => {
      await api(`/api/zonas/${zonaActual}/manual`, { method: "POST", body: JSON.stringify({ delta: -1 }) });
      refrescar();
    });
    $("btnMas").addEventListener("click", async () => {
      await api(`/api/zonas/${zonaActual}/manual`, { method: "POST", body: JSON.stringify({ delta: 1 }) });
      refrescar();
    });
    $("btnFijarManual").addEventListener("click", async () => {
      const valor = parseInt($("manualCount").textContent, 10) || 0;
      await api(`/api/zonas/${zonaActual}/fuente`, {
        method: "POST", body: JSON.stringify({ tipo: "manual", conteo: valor }),
      });
      refrescar();
    });
    $("btnRestaurar").addEventListener("click", async () => {
      await api(`/api/zonas/${zonaActual}/restaurar`, { method: "POST", body: "{}" });
      zonaFormCargada = null;
      refrescar();
    });

    $("formFuente").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const datos = {
        tipo: $("fuenteTipo").value,
        valor: $("fuenteValor").value.trim(),
        fps: parseFloat($("fuenteFps").value) || 3,
        conf: parseFloat($("fuenteConf").value) || 0.35,
        roi: [0, 1, 2, 3].map((i) => parseFloat($(["roiX1", "roiY1", "roiX2", "roiY2"][i]).value) || 0),
      };
      if (datos.tipo === "manual") datos.conteo = parseInt($("manualCount").textContent, 10) || 0;
      try {
        await api(`/api/zonas/${zonaActual}/fuente`, {
          method: "POST", body: JSON.stringify(datos),
        });
        zonaFormCargada = null;
        refrescar();
      } catch (err) {
        alert("No se pudo aplicar la configuración: " + err.message);
      }
    });

    document.querySelectorAll("#segmentoDomo button").forEach((b) => {
      b.addEventListener("click", () => {
        document.querySelectorAll("#segmentoDomo button").forEach((x) => x.classList.remove("activo"));
        b.classList.add("activo");
      });
    });
    $("btnAplicarDomo").addEventListener("click", async () => {
      const modo = document.querySelector("#segmentoDomo button.activo").dataset.modo;
      await api("/api/domo", {
        method: "POST",
        body: JSON.stringify({
          modo,
          piso_activo: $("pisoActivo").value,
          minutos: parseInt($("minutosDomo").value, 10) || 15,
        }),
      });
      refrescar();
    });
  }

  enlazar();
  refrescar();
  setInterval(refrescar, 1200);
})();
