/* Atlachia · tablero del operador. Todo sale de la API de la aplicación (/api/...). */
'use strict';
{
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const DAY = 864e5;
const MES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
const fmtD = f => `${Number(f.slice(8, 10))} ${MES[Number(f.slice(5, 7)) - 1]} ${f.slice(0, 4)}`;
const hora = t => new Date(t).toLocaleTimeString('es-MX', {hour: '2-digit', minute: '2-digit', hour12: false});
const fechaLocal = t => { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
const lluvias = f => { const m = Number(f.slice(5, 7)); return m >= 6 && m <= 10; };
const iso = t => new Date(t).toISOString().slice(0, 10);
const IDX = {
  ndti: {nombre: 'Turbidez', corto: 'NDTI', f: v => v.toFixed(3)},
  ndci: {nombre: 'Clorofila', corto: 'NDCI', f: v => v.toFixed(3)},
  lirio: {nombre: 'Lirio', corto: 'IA, % del espejo de agua', f: v => (v * 100).toFixed(1) + '%'}
};
const CROP = {lon0: -98.2634, lon1: -98.0984, lat0: 18.959, lat1: 18.871, w: 300, h: 160};
const PAR = [['turbidez', 'Turbidez'], ['pH', 'pH'], ['conductividad', 'Conductividad'], ['temperatura', 'Temperatura'], ['oxigeno_disuelto', 'Oxígeno disuelto']];
const NODO = {id: 'NODO-01', lat: 18.948, lon: -98.25};

const api = async (ruta, op) => {
  const r = await fetch('/api' + ruta, op);
  if (!r.ok) { let t = ''; try { t = (await r.json()).detail; } catch (e) {} throw new Error(t || 'error ' + r.status); }
  return r.status === 204 ? null : r.json();
};
const S = {serie: [], sel: 0, vista: 'sat', zonas: [], sitios: [], tipos: [], alertas: [], reportes: [], ultimas: [], turb: [],
           descarga: {activa: false}, bot: {}, ia: {}, salud: {}, filtroAl: 'activas', filtroRep: 'revisar', listo: false};

/* ---------- Umbrales (promedio + 2 desviaciones por temporada, igual que el servidor) ---------- */
const stats = a => { const n = a.length; if (n < 3) return null; const mu = a.reduce((s, v) => s + v, 0) / n; const sd = Math.sqrt(a.reduce((s, v) => s + (v - mu) ** 2, 0) / (n - 1)); return {mu, sd, thr: mu + 2 * sd}; };
const cacheU = {};
const umbral = (idx, ll) => { const k = idx + ll; if (!(k in cacheU)) cacheU[k] = stats(S.serie.filter(r => lluvias(r.fecha) === ll && isFinite(r[idx])).map(r => r[idx])); return cacheU[k]; };

/* ---------- Mapa ---------- */
const mapa = $('#mapa');
const zonaDe = nombre => S.zonas.find(z => z.nombre === nombre) || S.zonas[2] || {lat: 18.915, lon: -98.178};
const repEnMapa = () => S.reportes.filter(r => r.estado === 'revisar' || (r.estado === 'valido' && Date.now() - Date.parse(r.fecha) < DAY));
const drawMapa = () => {
  const W = mapa.clientWidth, H = mapa.clientHeight, img = S.serie[S.sel]; if (!img || !W) return;
  const k = Math.min(W / CROP.w, H / CROP.h), iw = CROP.w * k, ih = CROP.h * k, ox = (W - iw) / 2, oy = (H - ih) / 2;
  const P = (lon, lat) => [ox + (lon - CROP.lon0) / (CROP.lon1 - CROP.lon0) * iw, oy + (CROP.lat0 - lat) / (CROP.lat0 - CROP.lat1) * ih];
  const src = S.vista === 'ia' ? img.mapa_ia : img.mapa_satelite;
  let h = src ? `<image href="/mapas/${esc(src)}" x="${ox}" y="${oy}" width="${iw}" height="${ih}" preserveAspectRatio="none"/>` : `<rect x="${ox}" y="${oy}" width="${iw}" height="${ih}" fill="var(--line)"/><text x="${W / 2}" y="${H / 2}" text-anchor="middle" font-size="14" fill="var(--mute)">Sin mapa para esta fecha</text>`;
  for (const s of S.sitios) { const [x, y] = P(s.lon, s.lat); h += `<rect x="${x - 5}" y="${y - 5}" width="10" height="10" fill="#fff" stroke="#10202a" stroke-width="1.5"><title>${esc(`${s.clave} · ${s.nombre} · SST 2025: ${s.sst_2025} mg/L · semáforo ${s.semaforo_2025}`)}</title></rect>`; }
  repEnMapa().forEach((r, i) => { const z = zonaDe(r.zona), [x, y] = P(z.lon, z.lat); h += `<circle class="pulso" cx="${x + 12 + (i % 4) * 5}" cy="${y - 10}" r="7" fill="#ff5a2a" stroke="#fff" stroke-width="2"><title>${esc(`${hora(r.fecha)} · ${r.tipo} · ${r.zona}`)}</title></circle>`; });
  { const [x, y] = P(NODO.lon, NODO.lat), alto = S.descarga.activa; h += `<path ${alto ? 'class="pulso" ' : ''}d="M${x} ${y + 6}l8 8l-8 8l-8 -8z" fill="${alto ? '#ff5a2a' : '#ffd23f'}" stroke="#10202a" stroke-width="1.5"><title>NODO-01 · sensores (simulados)</title></path>`; }
  const lab = (lon, lat, t, a, dy) => { const [x, y] = P(lon, lat); return `<text x="${x}" y="${y + dy}" text-anchor="${a}" font-size="12" font-weight="600" fill="#10202a" style="stroke:#fff">${esc(t)}</text>`; };
  if (W >= 520) { h += lab(-98.255, 18.948, 'Entrada del Atoyac', 'start', -12); h += lab(-98.112, 18.912, 'Obra de toma', 'end', -12); }
  mapa.innerHTML = `<svg>${h}</svg>`;
};
new ResizeObserver(drawMapa).observe(mapa);

/* ---------- Gráficas de control ---------- */
const serieEl = $('#serie');
const pasoBonito = r => { const raw = r / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / p; return (n < 1.5 ? 1 : n < 3 ? 2 : n < 7 ? 5 : 10) * p; };
const drawCtrl = (el, idx) => {
  const W = el.clientWidth, H = el.clientHeight; if (!W || !S.serie.length) return;
  const pts = S.serie.map((r, i) => ({r, i})).filter(o => isFinite(o.r[idx]));
  if (!pts.length) { el.innerHTML = ''; return; }
  const L = 46, R = 12, T = 28, B = 28;
  const t0 = Date.parse(S.serie[0].fecha), t1 = Math.max(Date.parse(S.serie.at(-1).fecha), t0 + DAY);
  const uS = umbral(idx, false), uL = umbral(idx, true);
  const vals = pts.map(o => o.r[idx]).concat(uS ? [uS.thr, uS.mu - 2 * uS.sd] : [], uL ? [uL.thr, uL.mu - 2 * uL.sd] : []);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * .08 || .01; lo -= pad; hi += pad;
  if (idx === 'lirio') lo = Math.max(0, lo);
  const paso = pasoBonito(hi - lo);
  const X = f => L + (Date.parse(f) - t0) / (t1 - t0) * (W - L - R), Y = v => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const fmtT = v => idx === 'lirio' ? Math.round(v * 100) + '%' : (Math.abs(v) < 1e-9 ? '0' : v.toFixed(paso < .1 ? 2 : 1));
  const angosto = W < 520;
  let h = '';
  for (let v = Math.ceil(lo / paso) * paso; v <= hi + 1e-9; v += paso) h += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" font-size="12" fill="var(--mute)">${fmtT(v)}</text>`;
  const d0 = new Date(t0); let mi = 0;
  for (let d = new Date(Date.UTC(d0.getUTCFullYear(), d0.getUTCMonth() + 1, 1)); d.getTime() <= t1; d = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1))) {
    if (!angosto || mi % 2 === 0) h += `<text x="${X(iso(d.getTime()))}" y="${H - 8}" text-anchor="middle" font-size="12" fill="var(--mute)">${MES[d.getUTCMonth()]}</text>`;
    mi++;
  }
  for (let a = t0; a < t1;) {   // banda normal por temporada: secas nov–may, lluvias jun–oct
    const d = new Date(a), y = d.getUTCFullYear(), m = d.getUTCMonth() + 1, ll = m >= 6 && m <= 10;
    const fin = Math.min(ll ? Date.UTC(y, 10, 1) : m >= 11 ? Date.UTC(y + 1, 5, 1) : Date.UTC(y, 5, 1), t1);
    const u = umbral(idx, ll);
    if (u) { const xa = X(iso(a)), xb = fin >= t1 ? W - R : X(iso(fin)), yt = Y(Math.min(hi, u.thr)), yb = Y(Math.max(lo, u.mu - 2 * u.sd)); h += `<rect x="${xa}" y="${yt}" width="${Math.max(xb - xa, 2)}" height="${Math.max(yb - yt, 0)}" fill="var(--blue)" fill-opacity=".13"/><line x1="${xa}" x2="${xb}" y1="${Y(u.mu)}" y2="${Y(u.mu)}" stroke="var(--blue)" stroke-opacity=".55" stroke-dasharray="4 4"/>`; }
    a = fin;
  }
  const sel = S.serie[S.sel];
  h += `<line x1="${X(sel.fecha)}" x2="${X(sel.fecha)}" y1="${T}" y2="${H - B}" stroke="var(--ink)" stroke-opacity=".3"/>`;
  h += `<path d="M${pts.map(o => `${X(o.r.fecha).toFixed(1)} ${Y(o.r[idx]).toFixed(1)}`).join('L')}" fill="none" stroke="var(--blue)" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>`;
  h += pts.map(o => `<circle data-i="${o.i}" cx="${X(o.r.fecha)}" cy="${Y(o.r[idx])}" r="9" fill="transparent" style="cursor:pointer"><title>${esc(fmtD(o.r.fecha) + ' · ' + IDX[idx].f(o.r[idx]))}</title></circle>`).join('');
  const anom = pts.filter(o => { const u = umbral(idx, lluvias(o.r.fecha)); return u && o.r[idx] > u.thr; });
  const max = pts.reduce((a, b) => b.r[idx] > a.r[idx] ? b : a);
  const sp = pts.find(o => o.i === S.sel);
  if (sp && !anom.includes(sp)) h += `<circle data-i="${sp.i}" cx="${X(sp.r.fecha)}" cy="${Y(sp.r[idx])}" r="4" fill="var(--ink)" style="cursor:pointer"/>`;
  h += anom.map(o => `<circle data-i="${o.i}" cx="${X(o.r.fecha)}" cy="${Y(o.r[idx])}" r="${o === max ? 7 : 5.5}" fill="var(--alert)" stroke="var(--panel)" stroke-width="2" style="cursor:pointer"><title>${esc(fmtD(o.r.fecha) + ' · ' + IDX[idx].f(o.r[idx]) + ' · sobre el umbral')}</title></circle>`).join('');
  if (!anom.includes(max)) h += `<circle data-i="${max.i}" cx="${X(max.r.fecha)}" cy="${Y(max.r[idx])}" r="5.5" fill="var(--ink)" stroke="var(--panel)" stroke-width="2" style="cursor:pointer"/>`;
  const marcas = anom.includes(max) ? anom : anom.concat([max]);
  h += marcas.map(o => { const x = X(o.r.fecha), y = Y(o.r[idx]), c = anom.includes(o) ? 'var(--alert)' : 'var(--ink)', der = x < W - R - 70; return `<line x1="${x - 16}" x2="${x + 16}" y1="${y}" y2="${y}" stroke="${c}" stroke-width="1.4" stroke-dasharray="3 3"/>` + (o === max ? '' : `<text x="${der ? x + 20 : x - 20}" y="${y + 4}" text-anchor="${der ? 'start' : 'end'}" font-size="11" font-weight="600" fill="${c}">${IDX[idx].f(o.r[idx])}</text>`); }).join('');
  const mx = X(max.r.fecha), ma = mx > W - 140 ? 'end' : mx < L + 80 ? 'start' : 'middle';
  h += `<text x="${mx}" y="${Y(max.r[idx]) - 12}" text-anchor="${ma}" font-size="12" font-weight="600" fill="var(--ink)">máx ${IDX[idx].f(max.r[idx])} · ${esc(fmtD(max.r.fecha))}</text>`;
  el.innerHTML = `<svg>${h}</svg>`;
};
const drawSerie = () => { for (const k of ['ndci', 'lirio', 'ndti']) drawCtrl(document.getElementById('serie_' + k), k); };
new ResizeObserver(drawSerie).observe(serieEl);
serieEl.addEventListener('click', e => { const i = e.target.getAttribute && e.target.getAttribute('data-i'); if (i !== null && i !== undefined) { S.sel = Number(i); renderSat(); } });

/* ---------- Conagua ---------- */
const renderConagua = () => {
  if (!S.sitios.length) return;
  const mx = Math.max(...S.sitios.map(x => x.sst_2025));
  const oeste = S.sitios.filter(x => x.sst_2025 > 3 * x.sst_historica);
  const veces = oeste.map(x => Math.round(x.sst_2025 / x.sst_historica));
  $('#vTxt').textContent = `En 2025, ${oeste.length === 2 ? 'los dos sitios del oeste' : 'los sitios marcados'} tuvieron los sólidos suspendidos más altos (${Math.min(...veces)} a ${Math.max(...veces)} veces su mediana histórica) y el modelo de IA los vio con lirio en ${oeste.map(x => x.lirio_ia_pct + '%').join(' y ')} de las imágenes del año; los del este, con sólidos normales, casi no tuvieron lirio. Son 4 sitios con medianas anuales: es una coincidencia espacial, no una calibración.`;
  $('#conTabla').innerHTML = `<table class="ctab"><thead><tr><th>Sitio</th><th>Conagua (sólidos suspendidos 2025) <span style="color:var(--mute)">vs</span> satélite + IA (lirio 2025)</th><th>Semáforo Conagua</th></tr></thead><tbody>${S.sitios.map(x => `<tr><td>${esc(x.clave)}<div class="lbl">${esc(x.nombre)}</div></td><td><div class="cmp"><span class="cl">Conagua</span><div class="trk"><div class="barra" style="width:${(x.sst_2025 / mx * 100).toFixed(0)}%"></div></div><span class="cv mono">${x.sst_2025} mg/L</span><span class="cl">Satélite + IA</span><div class="trk"><div class="barra sat" style="width:${Math.max(1, x.lirio_ia_pct)}%"></div></div><span class="cv mono">${x.lirio_ia_pct}% lirio</span></div></td><td><span class="chip ${x.semaforo_2025 === 'Rojo' ? 'alerta' : 'pend'}">${esc(x.semaforo_2025)}</span></td></tr>`).join('')}</tbody></table><p class="leyenda" style="margin-top:8px"><span><span class="sw" style="background:var(--alert)"></span>Conagua: sólidos suspendidos totales 2025 (laboratorio)</span><span><span class="sw" style="background:var(--blue)"></span>Satélite + IA: % de imágenes de 2025 con lirio en el sitio</span></p>`;
};

/* ---------- Resumen: estado de la presa ---------- */
const renderKPI = () => {
  const img = S.serie[S.sel]; if (!img) return;
  $('#kFecha').textContent = fmtD(img.fecha);
  const fila = idx => { if (!isFinite(img[idx])) return ''; const u = umbral(idx, lluvias(img.fecha)), alto = u && img[idx] > u.thr; return `<div class="fila"><div><div>${IDX[idx].nombre} (${IDX[idx].corto})</div><div class="lbl">${idx === 'lirio' && img.ha ? '≈ ' + Math.round(img.ha).toLocaleString('es-MX') + ' ha · ' : ''}Umbral ${lluvias(img.fecha) ? 'lluvias' : 'secas'}: ${u ? IDX[idx].f(u.thr) : '—'}</div></div><div style="text-align:right"><div class="num">${IDX[idx].f(img[idx])}</div><span class="chip ${alto ? 'alerta' : 'ok'}">${alto ? 'Sobre el umbral' : 'Normal'}</span></div></div>`; };
  $('#kLecturas').innerHTML = fila('ndci') + fila('lirio') + fila('ndti') +
    `<div class="fila"><span>Presa sin nubes</span><span class="num">${isFinite(img.desp) ? Math.round(img.desp * 100) + '%' : '—'}</span></div>` +
    `<div class="fila"><span>Imágenes útiles</span><span class="num">${S.serie.length}</span></div>`;
  $('#slider').max = S.serie.length - 1; $('#slider').value = S.sel;
  $('#tMapa').textContent = `Imagen Sentinel-2 · ${fmtD(img.fecha)}`;
};
const renderSat = () => { if (!S.serie.length) return; S.sel = Math.max(0, Math.min(S.sel, S.serie.length - 1)); renderKPI(); drawMapa(); drawSerie(); };
$('#slider').addEventListener('input', e => { S.sel = Number(e.target.value); renderSat(); });
$('#prev').addEventListener('click', () => { S.sel--; renderSat(); });
$('#next').addEventListener('click', () => { S.sel++; renderSat(); });
const vista = v => { S.vista = v; $('#vSat').setAttribute('aria-pressed', v === 'sat'); $('#vIa').setAttribute('aria-pressed', v === 'ia'); $('#legSat').hidden = v !== 'sat'; $('#legIa').hidden = v !== 'ia'; drawMapa(); };
$('#vSat').addEventListener('click', () => vista('sat'));
$('#vIa').addEventListener('click', () => vista('ia'));

/* ---------- Alertas ---------- */
const INDIC = {ndci: 'ndci', lirio_pct: 'lirio'};
const titAl = a => a.indicador === 'iot' ? 'Cambio brusco en el sensor' : `${IDX[INDIC[a.indicador]].nombre} sobre el umbral`;
const estAl = a => a.atendida ? ['at', 'Atendida'] : a.estado === 'confirmada' ? ['alerta', 'Confirmada'] : ['pend', 'Pendiente'];
const cuandoAl = a => a.indicador === 'iot' ? `${fmtD(a.clave.slice(0, 10))} · ${a.clave.slice(11, 16)}` : fmtD(a.fecha);
const detAl = a => {
  if (a.indicador === 'iot') return `${esc(a.zona)} · NODO-01 · <span class="mono">${esc(a.detalle || a.valor.toFixed(1) + ' NTU')}</span>`;
  const f = a.indicador === 'lirio_pct' ? v => v.toFixed(1) + '%' : v => v.toFixed(3);
  return `${esc(a.zona)} · <span class="mono">${f(a.valor)}</span> / umbral <span class="mono">${f(a.umbral)}</span>`;
};
const renderAlertas = () => {
  const vis = S.alertas.filter(a => S.filtroAl === 'todas' || (S.filtroAl === 'atendidas') === a.atendida);
  $('#alertas').innerHTML = vis.length ? vis.map(a => {
    const e = estAl(a);
    const ver = a.indicador === 'iot' ? `<button data-ir="sensores">Ver sensor</button>` : `<button data-mapa="${esc(a.fecha)}">Ver en mapa</button>`;
    return `<li class="${e[0]}"><div class="cab"><strong>${titAl(a)}</strong><span class="chip ${e[0]}">${e[1]}</span></div><div class="det mono">${esc(cuandoAl(a))}</div><div class="det">${detAl(a)}</div><div class="det">Fuentes: ${a.fuentes.map(esc).join(' + ')}</div><div class="acc">${ver}<button ${a.atendida ? '' : 'class="ok" '}data-at="${esc(a.clave)}" data-v="${a.atendida ? 0 : 1}">${a.atendida ? 'Reabrir' : 'Marcar atendida'}</button></div></li>`;
  }).join('') : `<li class="vacio">${S.filtroAl === 'atendidas' ? 'Ninguna alerta atendida.' : 'Sin alertas activas.'}</li>`;
};
$('#alertas').addEventListener('click', async e => {
  const at = e.target.closest('[data-at]');
  if (at) { at.disabled = true; try { await api(`/alertas/${encodeURIComponent(at.dataset.at)}/atender?atendida=${at.dataset.v === '1'}`, {method: 'POST'}); await cargarAlertas(); if (at.dataset.v === '1') toast('Alerta marcada como atendida.', 'ok'); } catch (err) { toast('No se pudo guardar: ' + err.message, 'alerta'); } return; }
  const m = e.target.closest('[data-mapa]');
  if (m) { const i = S.serie.findIndex(r => r.fecha === m.dataset.mapa); if (i >= 0) { S.sel = i; renderSat(); irA('resumen'); } }
});

/* ---------- Reportes ---------- */
const EST_REP = {revisar: ['pend', 'Por revisar'], valido: ['ok', 'Válido'], descartado: ['at', 'Descartado']};
const iaRep = r => r.ia_texto ? `<div class="ia ${esc(r.ia_nivel || '')}">${esc(r.ia_texto)}</div>` : (r.foto ? `<div class="ia">${S.ia.estado === 'lista' ? 'IA: analizando…' : 'IA: en espera (modelo no listo)'}</div>` : '');
const cuandoRep = r => `${fmtD(fechaLocal(r.fecha))} · ${hora(r.fecha)} · ${r.via === 'telegram' ? 'Telegram' : 'Captura'}`;
const renderReportes = () => {
  const vis = S.reportes.filter(r => S.filtroRep === 'todos' || r.estado === S.filtroRep);
  $('#reportes').innerHTML = vis.length ? vis.map(r => {
    const acc = r.estado === 'revisar' ? `<button class="ok" data-est="valido" data-id="${r.id}">Válido</button><button data-est="descartado" data-id="${r.id}">Descartar</button>` : `<button data-est="revisar" data-id="${r.id}">Deshacer</button>`;
    const re = r.foto && S.ia.estado === 'lista' ? `<button data-rean="${r.id}">Reanalizar IA</button>` : '';
    return `<li class="rep ${r.estado}">${r.foto ? `<a href="/fotos/${esc(r.foto)}" target="_blank"><img src="/fotos/${esc(r.foto)}" alt="Foto del reporte" loading="lazy"></a>` : '<div class="sinfoto">Sin foto</div>'}<div class="rep-c"><div class="cab"><strong>${esc(r.tipo)}</strong><span class="chip ${EST_REP[r.estado][0]}">${EST_REP[r.estado][1]}</span></div><div class="det">${esc(r.zona)}</div><div class="det mono">${esc(cuandoRep(r))}</div>${r.descripcion ? `<div class="det">“${esc(r.descripcion)}”</div>` : ''}${iaRep(r)}<div class="acc">${acc}${re}</div></div></li>`;
  }).join('') : `<li class="vacio">${S.filtroRep === 'revisar' ? 'No hay reportes por revisar.' : 'Sin reportes en esta vista.'}</li>`;
};
$('#reportes').addEventListener('click', async e => {
  const b = e.target.closest('[data-est],[data-rean]'); if (!b) return;
  b.disabled = true;
  try {
    if (b.dataset.rean) { await api(`/reportes/${b.dataset.rean}/reanalizar`, {method: 'POST'}); }
    else {
      await api(`/reportes/${b.dataset.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({estado: b.dataset.est})});
      const r = S.reportes.find(x => String(x.id) === b.dataset.id);
      if (r && b.dataset.est !== 'revisar') toast(b.dataset.est === 'valido' ? `Reporte marcado como válido: ${r.tipo} · ${r.zona}` : `Reporte descartado: ${r.tipo} · ${r.zona}`, b.dataset.est === 'valido' ? 'ok' : '');
    }
    await Promise.all([cargarReportes(), cargarAlertas()]);
  } catch (err) { toast('No se pudo guardar: ' + err.message, 'alerta'); b.disabled = false; }
});
$('#fRep').addEventListener('submit', async e => {
  e.preventDefault();
  const m = $('#rMsg'); m.className = 'msg'; m.textContent = 'Enviando…';
  try {
    await api('/reportes', {method: 'POST', body: new FormData($('#fRep'))});
    $('#rDesc').value = ''; $('#rFoto').value = '';
    m.textContent = 'Reporte capturado.';
    await Promise.all([cargarReportes(), cargarAlertas()]);
  } catch (err) { m.className = 'msg err'; m.textContent = 'No se pudo enviar: ' + err.message; }
});

/* ---------- Sensores ---------- */
const spark = $('#spark');
const drawSpark = () => {
  const W = spark.clientWidth, H = spark.clientHeight, a = S.turb;
  if (!W || a.length < 2) { spark.innerHTML = `<svg><text x="8" y="24" font-size="13" fill="var(--mute)">${a.length ? '' : 'Sin lecturas recientes: ¿está corriendo Docker?'}</text></svg>`; return; }
  const vals = a.map(l => l.valor), mx = Math.max(...vals, 100) * 1.1, t0 = Date.parse(a[0].fecha), t1 = Math.max(Date.parse(a.at(-1).fecha), t0 + 1);
  const X = t => 46 + (Date.parse(t) - t0) / (t1 - t0) * (W - 120), Y = v => 8 + (1 - v / mx) * (H - 26);
  let h = '';
  for (const v of [0, 50, 100, 150, 200].filter(v => v <= mx)) h += `<line x1="46" x2="${W - 70}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)"/><text x="40" y="${Y(v) + 4}" text-anchor="end" font-size="11" fill="var(--mute)">${v}</text>`;
  h += `<line x1="46" x2="${W - 70}" y1="${Y(80)}" y2="${Y(80)}" stroke="var(--alert)" stroke-opacity=".6" stroke-dasharray="4 4"/><text x="${W - 66}" y="${Y(80) + 4}" font-size="11" fill="var(--alert)">80 NTU</text>`;
  h += `<path d="M${a.map(l => `${X(l.fecha).toFixed(1)} ${Y(l.valor).toFixed(1)}`).join('L')}" fill="none" stroke="var(--blue)" stroke-width="2" stroke-linejoin="round"/>`;
  h += a.filter(l => l.valor > 80).map(l => `<circle cx="${X(l.fecha)}" cy="${Y(l.valor)}" r="3" fill="var(--alert)"/>`).join('');
  const u = a.at(-1);
  h += `<circle cx="${X(u.fecha)}" cy="${Y(u.valor)}" r="4" fill="var(--blue)"/><text x="${X(u.fecha) + 8}" y="${Y(u.valor) + 4}" font-size="12" fill="var(--ink)">${u.valor.toFixed(1)} NTU</text>`;
  h += `<text x="46" y="${H - 4}" font-size="11" fill="var(--mute)">${hora(a[0].fecha)}</text><text x="${W - 70}" y="${H - 4}" text-anchor="end" font-size="11" fill="var(--mute)">${hora(u.fecha)}</text>`;
  spark.innerHTML = `<svg>${h}</svg>`;
};
new ResizeObserver(drawSpark).observe(spark);
const sensoresVivos = () => S.ultimas.length && Date.now() - Math.max(...S.ultimas.map(l => Date.parse(l.fecha))) < 30e3;
const renderSensores = () => {
  const por = Object.fromEntries(S.ultimas.map(l => [l.parametro, l]));
  $('#lect').innerHTML = PAR.map(([p, nombre]) => { const l = por[p]; const alto = l && p === 'turbidez' && l.valor > 80; return `<div class="${alto ? 'alto' : ''}"><div class="lbl">${nombre}</div><div class="v">${l ? l.valor.toFixed(p === 'pH' ? 2 : 1) + (l.unidad && l.unidad !== 'pH' ? ' ' + esc(l.unidad) : '') : '—'}</div><div class="q">${l ? esc(l.calidad) + ' · ' + hora(l.fecha) : ''}</div></div>`; }).join('');
  const d = S.descarga, b = $('#bDesc');
  if (d.activa) { const s = Math.max(0, Math.round((Date.parse(d.hasta) - Date.now()) / 1000)); b.disabled = true; $('#descTxt').innerHTML = `<span class="desc-on">Descarga simulada activa</span> · termina en <span class="contador">${s} s</span>`; }
  else { b.disabled = false; $('#descTxt').textContent = sensoresVivos() ? 'Lecturas cada 3 s (en campo serían cada 5 min).' : 'Sin lecturas recientes: revisa que Docker Desktop esté abierto.'; }
  const t = por.turbidez;
  $('#json').textContent = t ? JSON.stringify({fuente: 'iot', sitio: NODO.id, fecha: t.fecha, parametro: 'turbidez', valor: t.valor, unidad: t.unidad, lat: NODO.lat, lon: NODO.lon, calidad: t.calidad}, null, 2) : '';
  drawSpark();
};
$('#bDesc').addEventListener('click', async () => {
  $('#bDesc').disabled = true;
  try { S.descarga = await api('/sensores/descarga?segundos=60', {method: 'POST'}); toast('Descarga simulada activada por 60 s: los 5 sensores van a reaccionar.', ''); renderSensores(); drawMapa(); }
  catch (err) { toast('No se pudo activar: ' + err.message, 'alerta'); $('#bDesc').disabled = false; }
});

/* ---------- Configuración: IA de fotos ---------- */
const iaMsg = (t, err) => { const m = $('#iaMsg'); m.className = err ? 'msg err' : 'msg'; m.textContent = t; };
const renderEjemplos = async () => {
  let ej; try { ej = await api('/ia/ejemplos'); } catch (e) { return; }
  const nombres = Object.fromEntries((S.ia.ejemplos || []).map(c => [c.clase, c.nombre]));
  $('#iaClases').innerHTML = Object.entries(ej).map(([c, lista]) => {
    const conMini = lista.filter(x => /^(https:|data:image)/.test(x.miniatura || ''));
    return `<div class="ej"><div class="cab"><div><strong>${esc(nombres[c] || c)}</strong> <span class="lbl">· ${lista.length} ejemplos</span></div><label class="btnf" style="min-height:34px;font-size:13px">Agregar fotos propias<input type="file" accept="image/*" multiple data-clase="${esc(c)}" class="oculto"></label></div><div class="mini">${conMini.slice(-24).map(x => `<img src="${esc(x.miniatura)}" alt="" loading="lazy" referrerpolicy="no-referrer">`).join('')}${lista.length - Math.min(24, conMini.length) > 0 ? `<span class="sinmini">+${lista.length - Math.min(24, conMini.length)}</span>` : ''}</div></div>`;
  }).join('');
};
$('#iaClases').addEventListener('change', async e => {
  const inp = e.target; if (!inp.dataset || !inp.dataset.clase) return;
  const fs = [...inp.files]; let ok = 0;
  for (const [i, f] of fs.entries()) {
    iaMsg(`Calculando huellas: ${i + 1} de ${fs.length}…`);
    const fd = new FormData(); fd.append('foto', f);
    try { await api('/ia/ejemplos/' + encodeURIComponent(inp.dataset.clase), {method: 'POST', body: fd}); ok++; } catch (err) { iaMsg(err.message, true); }
  }
  inp.value = '';
  if (ok) iaMsg(`${ok} foto(s) agregada(s) como ejemplo.`);
  await cargarEstado(); renderEjemplos();
});
$('#iaImportar').addEventListener('change', async e => {
  const f = e.target.files[0]; if (!f) return;
  const fd = new FormData(); fd.append('archivo', f);
  try { const r = await api('/ia/ejemplos/importar', {method: 'POST', body: fd}); iaMsg(`Ejemplos importados: ${r.agregados} nuevos · ${r.repetidos} ya estaban o repetidos.`); }
  catch (err) { iaMsg(err.message, true); }
  e.target.value = ''; await cargarEstado(); renderEjemplos();
});
$('#iaEval').addEventListener('click', async () => {
  $('#iaEvalRes').textContent = 'Evaluando…';
  try {
    const r = await api('/ia/evaluar', {method: 'POST'}), t = r.total;
    $('#iaEvalRes').innerHTML = `<table class="ctab res-tab"><thead><tr><th>Clase</th><th style="text-align:right">Fotos de prueba</th><th style="text-align:right">CLIP solo</th><th style="text-align:right">CLIP ajustado</th></tr></thead><tbody>${r.clases.map(c => `<tr><td>${esc(c.clase)}</td><td class="n">${c.fotos}</td><td class="n">${c.clip_solo}%</td><td class="n">${c.clip_ajustado}%</td></tr>`).join('')}<tr><td><strong>Total</strong></td><td class="n"><strong>${t.fotos}</strong></td><td class="n"><strong>${t.clip_solo}%</strong></td><td class="n"><strong>${t.clip_ajustado}%</strong></td></tr></tbody></table>`;
  } catch (err) { $('#iaEvalRes').innerHTML = `<p class="msg err">${esc(err.message)}</p>`; }
});
$('#iaProbar').addEventListener('change', async e => {
  const f = e.target.files[0]; if (!f) return;
  $('#iaProbarRes').textContent = 'Analizando…';
  const fd = new FormData(); fd.append('foto', f);
  try {
    const r = await api('/ia/probar', {method: 'POST', body: fd});
    const top = l => l.map(x => `${esc(x.clase)} ${Math.round(x.probabilidad * 100)}%`).join(' · ');
    $('#iaProbarRes').innerHTML = `<img src="${URL.createObjectURL(f)}" alt="Foto de prueba" style="max-width:100%;max-height:200px;border-radius:6px"><p><strong>CLIP ajustado:</strong> ${top(r.ajustado)}</p><p class="lbl">CLIP solo: ${top(r.solo)}</p>`;
  } catch (err) { $('#iaProbarRes').innerHTML = `<p class="msg err">${esc(err.message)}</p>`; }
  e.target.value = '';
});

/* ---------- Preparar demo (dos clics para evitar accidentes) ---------- */
let demoArmado = null;
$('#bDemo').addEventListener('click', async () => {
  const b = $('#bDemo');
  if (!demoArmado) {
    b.textContent = '¿Seguro? Clic otra vez para borrar'; b.classList.add('main');
    demoArmado = setTimeout(() => { demoArmado = null; b.textContent = 'Preparar demo'; b.classList.remove('main'); }, 5000);
    return;
  }
  clearTimeout(demoArmado); demoArmado = null; b.disabled = true;
  try {
    const r = await api('/demo/preparar', {method: 'POST'});
    toast(`Listo para presentar: ${r.reportes_borrados} reporte(s) y ${r.alertas_del_sensor_borradas} alerta(s) del sensor borrados.`, 'ok');
    await Promise.all([cargarAlertas(), cargarReportes(), cargarSensores()]);
    conocidas = new Set(S.alertas.map(a => a.clave)); repConocidos = new Set(S.reportes.map(r => r.id));
  } catch (err) { toast('No se pudo preparar: ' + err.message, 'alerta'); }
  b.disabled = false; b.textContent = 'Preparar demo'; b.classList.remove('main');
});

/* ---------- Estado general (cabecera, configuración, canal) ---------- */
const renderEstado = () => {
  const set = (id, on, txt) => { const el = $(id); el.classList.toggle('on', !!on); if (txt) el.title = txt; };
  const b = S.bot, ia = S.ia, db = (S.salud.base_de_datos || {});
  const vivos = sensoresVivos();
  set('#stSen', vivos, vivos ? 'Sensores enviando lecturas' : 'Sin lecturas recientes');
  set('#stBot', b.estado === 'conectado', b.estado === 'conectado' ? 'Bot conectado: @' + b.usuario : 'Bot: ' + (b.estado || '—'));
  set('#stIa', ia.estado === 'lista', 'IA de fotos: ' + (ia.estado || '—'));
  set('#arDb', db.estado === 'ok'); set('#arSen', vivos); set('#arBot', b.estado === 'conectado'); set('#arIa', ia.estado === 'lista');
  $('#arDbTxt').textContent = db.estado === 'ok' ? `PostgreSQL ${db.postgresql} · PostGIS ${db.postgis}` : 'Sin conexión: revisa que Docker Desktop esté abierto.';
  $('#arSenTxt').textContent = vivos ? 'Enviando lecturas cada 3 s (contenedor atlachia_sensores).' : 'Sin lecturas recientes: revisa Docker Desktop.';
  $('#arBotTxt').textContent = b.estado === 'conectado' ? `@${b.usuario} escuchando · ${b.reportes_recibidos} reporte(s) desde que arrancó.` : `${b.estado || '—'}. ${b.detalle || ''}`;
  const n = (ia.ejemplos || []).reduce((t, c) => t + c.n, 0), comp = ia.compatibilidad;
  $('#arIaTxt').textContent = ia.estado === 'lista' ? `Lista · ${n} ejemplos${comp && comp.fotos ? ` · compatibilidad con el tablero anterior ${comp.promedio.toFixed(3)}` : ''}.` : `${ia.estado || '—'}. ${ia.detalle || ''}`;
  const qr = $('#qrGrande');
  const clave = b.estado === 'conectado' ? 'on:' + b.usuario : 'off:' + b.estado;
  if (qr.dataset.k !== clave) {
    qr.dataset.k = clave;
    qr.innerHTML = b.estado === 'conectado'
      ? `<img class="qrimg" src="/api/bot/qr.png" alt="Código QR del bot"><div class="qrbot">@${esc(b.usuario)}</div><p class="lbl">Escanea para reportar desde Telegram. Se guarda dónde y cuándo, nunca quién.</p>`
      : `<p class="lbl qrvacio">Bot ${esc(b.estado || 'sin conectar')}. ${esc(b.detalle || '')}</p>`;
  }
};

/* ---------- Resumen: listas cortas, insignias y avisos ---------- */
let conocidas = null, confirmadas = null, repConocidos = null;
const renderListas = () => {
  const act = S.alertas.filter(a => !a.atendida), porRev = S.reportes.filter(r => r.estado === 'revisar');
  $('#badgeAl').textContent = act.length; $('#badgeAl').hidden = !act.length;
  $('#badgeRep').textContent = porRev.length; $('#badgeRep').hidden = !porRev.length;
  $('#miniAl').innerHTML = act.length ? act.slice(0, 4).map(a => { const e = estAl(a); return `<li data-ir="alertas"><span class="chip ${e[0]}">${e[1]}</span><span class="t">${titAl(a)}</span><span class="s mono">${esc(cuandoAl(a))} · ${esc(a.zona)}</span></li>`; }).join('') : '<li class="vacio">Sin alertas activas.</li>';
  $('#miniRep').innerHTML = porRev.length ? porRev.slice(0, 3).map(r => `<li data-ir="reportes">${r.foto ? `<img src="/fotos/${esc(r.foto)}" alt="">` : '<span class="chip pend">Sin foto</span>'}<span class="t">${esc(r.tipo)} · ${esc(r.zona)}</span><span class="s">${r.ia_texto ? esc(r.ia_texto) : esc(hora(r.fecha) + ' · ' + (r.via === 'telegram' ? 'Telegram' : 'Captura'))}</span></li>`).join('') : '<li class="vacio">No hay reportes por revisar.</li>';
};
const avisos = () => {
  const ids = new Set(S.alertas.map(a => a.clave)), conf = new Set(S.alertas.filter(a => a.estado === 'confirmada').map(a => a.clave));
  const reps = new Set(S.reportes.map(r => r.id));
  if (conocidas) {
    for (const a of S.alertas) if (!conocidas.has(a.clave) && !a.atendida) toast(`⚠ Nueva alerta: ${titAl(a)} · ${a.zona}`, 'alerta', actual === 'alertas' ? null : ['Ver', () => irA('alertas')]);
    for (const c of conf) if (!confirmadas.has(c) && conocidas.has(c)) toast('🔴 Alerta confirmada: coinciden dos fuentes.', 'alerta', actual === 'alertas' ? null : ['Ver', () => irA('alertas')]);
  }
  if (repConocidos) for (const r of S.reportes) if (!repConocidos.has(r.id)) toast(`📩 Nuevo reporte${r.via === 'telegram' ? ' por Telegram' : ''}: ${r.tipo} · ${r.zona}`, '', actual === 'reportes' ? null : ['Ver', () => irA('reportes')]);
  conocidas = ids; confirmadas = conf; repConocidos = reps;
};

/* ---------- Carga de datos ---------- */
const huella = {};   // sólo se vuelve a dibujar si los datos cambiaron (así no se pierde un clic)
const cambio = (k, datos) => { const j = JSON.stringify(datos); if (huella[k] === j) return false; huella[k] = j; return true; };
const cargarAlertas = async () => { const a = await api('/alertas?filtro=todas'); if (!cambio('al', a)) return; S.alertas = a; renderAlertas(); renderListas(); };
const cargarReportes = async () => { const r = await api('/reportes?estado=todos'); if (!cambio('rep', [r, S.ia.estado])) return; S.reportes = r; renderReportes(); renderListas(); drawMapa(); };
const cargarSensores = async () => {
  const [u, t, d] = await Promise.all([api('/sensores/ultimas'), api('/sensores/serie?parametro=turbidez&minutos=5'), api('/sensores/descarga')]);
  const antes = S.descarga.activa; S.ultimas = u; S.turb = t; S.descarga = d;
  renderSensores(); if (antes !== d.activa) drawMapa();
};
const cargarEstado = async () => {
  const [b, ia, s] = await Promise.all([api('/bot/estado'), api('/ia/estado'), fetch('/salud').then(r => r.json())]);
  S.bot = b; S.ia = ia; S.salud = s; renderEstado();
};
const ciclo = async () => {
  try { await cargarEstado(); await Promise.all([cargarAlertas(), cargarReportes(), cargarSensores()]); avisos(); }
  catch (e) { console.warn('Atlachia:', e); }
  setTimeout(ciclo, 3000);
};
const inicio = async () => {
  try {
    const [serie, zonas, sitios] = await Promise.all([api('/serie'), api('/zonas'), api('/sitios')]);
    S.serie = serie.map(r => ({fecha: r.fecha, ndti: r.ndti ?? NaN, ndci: r.ndci ?? NaN, lirio: r.lirio_pct == null ? NaN : r.lirio_pct / 100, ha: r.lirio_ha, desp: r.frac_despejada ?? NaN, mapa_satelite: r.mapa_satelite, mapa_ia: r.mapa_ia}));
    S.zonas = zonas; S.sitios = sitios;
    S.sel = S.serie.reduce((bi, r, i, a) => r.ndci > a[bi].ndci ? i : bi, 0);   // abre en la clorofila más alta
    $('#tSerie').textContent = `Gráficas de control · ${fmtD(S.serie[0].fecha)} – ${fmtD(S.serie.at(-1).fecha)}`;
    $('#rZona').innerHTML = zonas.map(z => `<option>${esc(z.nombre)}</option>`).join('');
    $('#rTipo').innerHTML = ['Espuma', 'Color extraño', 'Olor', 'Peces muertos', 'Lirio', 'Otro'].map(t => `<option>${t}</option>`).join('');
    renderSat(); renderConagua();
  } catch (e) { toast('No se pudo leer la base de datos. ¿Está abierto Docker Desktop?', 'alerta'); console.warn(e); }
  await ciclo();
  renderEjemplos();
};

/* ---------- Pestañas, avisos y reloj ---------- */
const TABS = ['resumen', 'historico', 'alertas', 'reportes', 'sensores', 'config'];
let actual = 'resumen';
const irA = t => {
  if (!TABS.includes(t)) t = 'resumen';
  actual = t;
  for (const k of TABS) { $('#p-' + k).hidden = k !== t; $('#t-' + k).setAttribute('aria-selected', k === t); }
  if (location.hash !== '#/' + t) history.replaceState(null, '', '#/' + t);
  if (t === 'config') renderEjemplos();
  scrollTo(0, 0);
};
document.addEventListener('click', e => { const b = e.target.closest && e.target.closest('[data-tab],[data-ir]'); if (b) irA(b.dataset.tab || b.dataset.ir); });
document.addEventListener('keydown', e => {
  if (e.altKey || e.ctrlKey || e.metaKey || /INPUT|TEXTAREA|SELECT/.test(document.activeElement && document.activeElement.tagName)) return;
  const n = Number(e.key); if (n >= 1 && n <= TABS.length) irA(TABS[n - 1]);
});
const filtro = (sel, set, render) => $(sel).addEventListener('click', e => {
  const b = e.target.closest('button[data-f]'); if (!b) return;
  $(sel).querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b));
  set(b.dataset.f); render();
});
filtro('#fAl', v => { S.filtroAl = v; }, renderAlertas);
filtro('#fRepF', v => { S.filtroRep = v; }, renderReportes);
function toast(txt, tipo, accion) {
  const d = document.createElement('div'); d.className = 'toast ' + (tipo || '');
  const s = document.createElement('span'); s.textContent = txt; d.appendChild(s);
  if (accion) { const b = document.createElement('button'); b.type = 'button'; b.textContent = accion[0]; b.addEventListener('click', () => { accion[1](); d.remove(); }); d.appendChild(b); }
  $('#toasts').appendChild(d);
  setTimeout(() => d.remove(), 7000);
}
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
const reloj = () => { const d = new Date(); $('#reloj').textContent = `${DIAS[d.getDay()]} ${d.getDate()} ${MES[d.getMonth()]} ${d.getFullYear()} · ${d.toLocaleTimeString('es-MX', {hour12: false})}`; if (S.descarga.activa) renderSensores(); };
reloj(); setInterval(reloj, 1000);
irA(location.hash.replace(/^#\/?/, '') || 'resumen');
addEventListener('hashchange', () => { const t = location.hash.replace(/^#\/?/, ''); if (t !== actual) irA(t); });
inicio();
}
