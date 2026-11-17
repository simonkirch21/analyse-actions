// =====================================================================
// Outils « pro » de l'application (chargé après le script principal :
// utilise ses fonctions globales $, fr, pctTxt, sens, echapper, mini, chercher…)
// =====================================================================

const couleur = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const allerMode = (m) => document.querySelector(`#mode button[data-m="${m}"]`).click();

// Appelée par le script principal à l'ouverture d'un écran
window.ouvertureModePro = function (m) {
  if (m === "graphique" && !gp.ticker) ouvrirGraphique(courant && courant.a ? courant.a.ticker : "^FCHI", courant && courant.a ? courant.a.nom : "CAC 40");
  if (m === "graphique") setTimeout(dessinerGP, 30);
  if (m === "carte") chargerCarte();
  if (m === "marches") chargerMarches();
  if (m === "options" && !opEtat.ticker) $("op-contenu").innerHTML = `<p class="note-a">Exemples : Apple (AAPL), Nvidia (NVDA), Tesla (TSLA), Microsoft (MSFT).</p>`;
};

// =====================================================================
// 1. GRAPHIQUE INTERACTIF (bougies, volumes, moyennes mobiles, Bollinger, RSI, comparaison)
// =====================================================================
const gp = { ticker: null, nom: "", periode: "1y", type: "bougies", indic: new Set(["mm50", "mm200", "volume"]),
             donnees: [], debut: 0, fin: 0, comp: [], survol: null, glisse: null };
const COULEURS_COMP = ["#6EA8FF", "#B48CFF", "#4FD1C5", "#F2A65A"];

async function ouvrirGraphique(ticker, nom) {
  gp.ticker = ticker; gp.nom = nom || ticker; gp.comp = [];      // avant le changement d'écran (sinon double chargement)
  if (mode !== "graphique") allerMode("graphique");
  majCompListe();
  await chargerGP();
}
async function donneesOHLC(t, periode) {
  const d = await (await fetch(`/api/marche/ohlc/${encodeURIComponent(t)}?periode=${periode}`)).json();
  if (d.erreur) throw new Error(d.erreur);
  return d;
}
async function chargerGP() {
  $("gp-titre").textContent = gp.nom;
  $("gp-sous").textContent = "Chargement…";
  try {
    const d = await donneesOHLC(gp.ticker, gp.periode);
    gp.donnees = d.bougies; gp.devise = d.devise; gp.debut = 0; gp.fin = d.bougies.length - 1;
    for (const c of gp.comp) c.bougies = (await donneesOHLC(c.ticker, gp.periode)).bougies;
    const p0 = gp.donnees[0][4], p1 = gp.donnees[gp.donnees.length - 1][4];
    $("gp-sous").innerHTML = `${echapper(gp.ticker)} · dernier cours <b>${fr(p1)}</b> ${echapper(gp.devise || "")} · sur la période
      <b class="${sens(p1 / p0 - 1)}">${pctTxt(p1 / p0 - 1)}</b> · ${gp.donnees.length} ${gp.donnees.length > 1500 ? "bougies" : "séances"}`;
  } catch (e) { $("gp-sous").textContent = e.message || "Données indisponibles."; gp.donnees = []; }
  dessinerGP();
}
function moyenne(c, n) { const r = []; let s = 0; for (let i = 0; i < c.length; i++) { s += c[i]; if (i >= n) s -= c[i - n]; r.push(i >= n - 1 ? s / n : null); } return r; }
function ecartType(c, n, m) { return c.map((_, i) => { if (i < n - 1) return null; let s = 0; for (let k = i - n + 1; k <= i; k++) s += (c[k] - m[i]) ** 2; return Math.sqrt(s / n); }); }
function rsi(c, n = 14) {
  const r = [null]; let h = 0, b = 0;
  for (let i = 1; i < c.length; i++) {
    const d = c[i] - c[i - 1], up = Math.max(d, 0), dn = Math.max(-d, 0);
    h = i <= n ? h + up / n : (h * (n - 1) + up) / n; b = i <= n ? b + dn / n : (b * (n - 1) + dn) / n;
    r.push(i < n ? null : 100 - 100 / (1 + h / (b || 1e-9)));
  }
  return r;
}

function dessinerGP() {
  const cv = $("gp-canvas"); if (!cv || !cv.offsetWidth) return;
  const dpr = window.devicePixelRatio || 1, W = cv.offsetWidth, avecRSI = gp.indic.has("rsi");
  const H = avecRSI ? 560 : 480; cv.style.height = H + "px";
  cv.width = W * dpr; cv.height = H * dpr;
  const ctx = cv.getContext("2d"); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
  const D = gp.donnees; if (D.length < 2) return;
  const C = { texte: couleur("--texte"), doux: couleur("--doux"), bord: couleur("--bord"), or: couleur("--or"),
              hausse: couleur("--eu"), baisse: couleur("--rouge"), bleu: "#6EA8FF" };
  const g = 8, d = 64, haut = 12, basPrix = avecRSI ? H - 150 : H - 30, hautRSI = basPrix + 26, basRSI = H - 30;
  const i0 = gp.debut, i1 = gp.fin, vue = D.slice(i0, i1 + 1), n = vue.length;
  const larg = (W - g - d) / n, X = (i) => g + (i - i0 + 0.5) * larg;
  const clot = D.map(b => b[4]);
  const comparaison = gp.comp.length > 0;

  // Séries affichées (en % depuis le début de la vue si comparaison)
  let series = [];
  if (comparaison) {
    const base = vue[0][4];
    series.push({ nom: gp.ticker, coul: C.or, pts: vue.map((b, k) => [i0 + k, (b[4] / base - 1) * 100]) });
    gp.comp.forEach((c, j) => {
      const map = new Map((c.bougies || []).map(b => [b[0], b[4]]));
      let dernier = null; const pts = [];
      vue.forEach((b, k) => { const v = map.get(b[0]) ?? dernier; if (v != null) { dernier = v; pts.push([i0 + k, v]); } });
      if (pts.length) { const b0 = pts[0][1]; series.push({ nom: c.ticker, coul: COULEURS_COMP[j % 4], pts: pts.map(([i, v]) => [i, (v / b0 - 1) * 100]) }); }
    });
  }
  // Échelle verticale
  let mn = Infinity, mx = -Infinity;
  if (comparaison) series.forEach(s => s.pts.forEach(([, v]) => { mn = Math.min(mn, v); mx = Math.max(mx, v); }));
  else vue.forEach(b => { mn = Math.min(mn, gp.type === "bougies" ? b[3] : b[4]); mx = Math.max(mx, gp.type === "bougies" ? b[2] : b[4]); });
  const mm = {}; ["mm20", "mm50", "mm200"].forEach(k => { if (gp.indic.has(k)) mm[k] = moyenne(clot, +k.slice(2)); });
  let bb = null;
  if (gp.indic.has("bollinger")) { const m20 = moyenne(clot, 20), et = ecartType(clot, 20, m20); bb = { m: m20, h: m20.map((v, i) => v == null ? null : v + 2 * et[i]), b: m20.map((v, i) => v == null ? null : v - 2 * et[i]) }; }
  if (!comparaison) {
    Object.values(mm).forEach(s => s.slice(i0, i1 + 1).forEach(v => { if (v != null) { mn = Math.min(mn, v); mx = Math.max(mx, v); } }));
    if (bb) [bb.h, bb.b].forEach(s => s.slice(i0, i1 + 1).forEach(v => { if (v != null) { mn = Math.min(mn, v); mx = Math.max(mx, v); } }));
  }
  const marge = (mx - mn) * 0.06 || 1; mn -= marge; mx += marge;
  const Y = (v) => haut + (1 - (v - mn) / (mx - mn)) * (basPrix - haut);

  // Grille et étiquettes
  ctx.font = "11px ui-monospace, SF Mono, Menlo, monospace"; ctx.textBaseline = "middle";
  for (let k = 0; k <= 5; k++) {
    const v = mn + (mx - mn) * k / 5, y = Y(v);
    ctx.strokeStyle = C.bord; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(g, y); ctx.lineTo(W - d, y); ctx.stroke();
    ctx.fillStyle = C.doux; ctx.textAlign = "left"; ctx.fillText(comparaison ? (v >= 0 ? "+" : "") + fr(v, 0) + " %" : fr(v, v < 10 ? 2 : 0), W - d + 6, y);
  }
  ctx.textAlign = "center";
  const pas = Math.max(1, Math.floor(n / 6));
  for (let k = 0; k < n; k += pas) {
    const dt = new Date(vue[k][0]);
    const lib = n < 140 ? dt.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) : dt.toLocaleDateString("fr-FR", { month: "short", year: "2-digit" });
    ctx.fillStyle = C.doux; ctx.fillText(lib, X(i0 + k), H - 14);
  }

  // Volumes (en bas de la zone de prix, 18 % de la hauteur)
  if (gp.indic.has("volume") && !comparaison) {
    const vmax = Math.max(...vue.map(b => b[5])) || 1, hv = (basPrix - haut) * 0.18;
    vue.forEach((b, k) => {
      const h = b[5] / vmax * hv; ctx.fillStyle = (b[4] >= b[1] ? C.hausse : C.baisse) + "40";
      ctx.fillRect(X(i0 + k) - Math.max(larg * 0.35, 0.5), basPrix - h, Math.max(larg * 0.7, 1), h);
    });
  }
  const ligne = (pts, coul, epais = 1.5, tirets = null) => {
    ctx.strokeStyle = coul; ctx.lineWidth = epais; ctx.setLineDash(tirets || []); ctx.beginPath(); let commence = false;
    pts.forEach(([i, v]) => { if (v == null) { commence = false; return; } const x = X(i), y = Y(v); commence ? ctx.lineTo(x, y) : ctx.moveTo(x, y); commence = true; });
    ctx.stroke(); ctx.setLineDash([]);
  };
  const tranche = (s) => s.slice(i0, i1 + 1).map((v, k) => [i0 + k, v]);

  if (comparaison) {
    ctx.strokeStyle = C.doux; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(g, Y(0)); ctx.lineTo(W - d, Y(0)); ctx.stroke(); ctx.setLineDash([]);
    series.forEach((s, j) => ligne(s.pts, s.coul, j === 0 ? 2.2 : 1.6));
  } else {
    if (bb) {
      ctx.fillStyle = C.bleu + "14"; ctx.beginPath(); let premier = true;
      for (let i = i0; i <= i1; i++) if (bb.h[i] != null) { premier ? ctx.moveTo(X(i), Y(bb.h[i])) : ctx.lineTo(X(i), Y(bb.h[i])); premier = false; }
      for (let i = i1; i >= i0; i--) if (bb.b[i] != null) ctx.lineTo(X(i), Y(bb.b[i]));
      ctx.fill(); ligne(tranche(bb.h), C.bleu + "90", 1); ligne(tranche(bb.b), C.bleu + "90", 1);
    }
    if (gp.type === "bougies") {
      vue.forEach((b, k) => {
        const x = X(i0 + k), monte = b[4] >= b[1], coul = monte ? C.hausse : C.baisse;
        ctx.strokeStyle = coul; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, Y(b[2])); ctx.lineTo(x, Y(b[3])); ctx.stroke();
        const y1 = Y(Math.max(b[1], b[4])), y2 = Y(Math.min(b[1], b[4])), lc = Math.max(larg * 0.66, 1);
        ctx.fillStyle = coul; ctx.fillRect(x - lc / 2, y1, lc, Math.max(y2 - y1, 1));
      });
    } else {
      const pts = vue.map((b, k) => [i0 + k, b[4]]);
      if (gp.type === "zone") {
        const grad = ctx.createLinearGradient(0, haut, 0, basPrix); grad.addColorStop(0, C.or + "55"); grad.addColorStop(1, C.or + "00");
        ctx.fillStyle = grad; ctx.beginPath(); ctx.moveTo(X(i0), basPrix);
        pts.forEach(([i, v]) => ctx.lineTo(X(i), Y(v))); ctx.lineTo(X(i1), basPrix); ctx.fill();
      }
      ligne(pts, C.or, 2);
    }
    const cmm = { mm20: "#B48CFF", mm50: "#6EA8FF", mm200: "#F2A65A" };
    Object.entries(mm).forEach(([k, s]) => ligne(tranche(s), cmm[k], 1.4));
  }

  // RSI
  let r = null;
  if (avecRSI && !comparaison) {
    r = rsi(clot); const YR = (v) => hautRSI + (1 - v / 100) * (basRSI - hautRSI);
    ctx.fillStyle = C.doux; ctx.textAlign = "left"; ctx.fillText("RSI 14", g + 4, hautRSI - 10);
    [30, 70].forEach(v => { ctx.strokeStyle = v === 70 ? C.baisse + "88" : C.hausse + "88"; ctx.setLineDash([4, 4]); ctx.beginPath(); ctx.moveTo(g, YR(v)); ctx.lineTo(W - d, YR(v)); ctx.stroke(); ctx.setLineDash([]); ctx.fillStyle = C.doux; ctx.fillText(v, W - d + 6, YR(v)); });
    ctx.strokeStyle = "#B48CFF"; ctx.lineWidth = 1.4; ctx.beginPath(); let c0 = false;
    for (let i = i0; i <= i1; i++) if (r[i] != null) { c0 ? ctx.lineTo(X(i), YR(r[i])) : ctx.moveTo(X(i), YR(r[i])); c0 = true; }
    ctx.stroke();
  }

  // Réticule et informations
  const s = gp.survol;
  let info = "";
  if (s != null && s >= i0 && s <= i1) {
    const b = D[s], x = X(s);
    ctx.strokeStyle = C.doux; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x, haut); ctx.lineTo(x, avecRSI ? basRSI : basPrix); ctx.stroke(); ctx.setLineDash([]);
    const prec = s > 0 ? D[s - 1][4] : b[1], v = b[4] / prec - 1;
    info = `<span class="l">${new Date(b[0]).toLocaleDateString("fr-FR")}</span>`;
    if (comparaison) series.forEach(se => { const p = se.pts.find(([i]) => i === s); if (p) info += `<span style="color:${se.coul}">${echapper(se.nom)} ${p[1] >= 0 ? "+" : ""}${fr(p[1], 1)} %</span>`; });
    else {
      info += `<span><span class="l">O</span> ${fr(b[1])}</span><span><span class="l">H</span> ${fr(b[2])}</span><span><span class="l">B</span> ${fr(b[3])}</span>
               <span><span class="l">C</span> ${fr(b[4])}</span><span class="${sens(v)}">${pctTxt(v, 2)}</span>`;
      if (gp.indic.has("volume")) info += `<span><span class="l">Vol</span> ${fr(b[5] / 1e6, 2)} M</span>`;
      Object.entries(mm).forEach(([k, se]) => { if (se[s] != null) info += `<span><span class="l">${k.toUpperCase().replace("MM", "MM ")}</span> ${fr(se[s])}</span>`; });
      if (r && r[s] != null) info += `<span><span class="l">RSI</span> ${fr(r[s], 0)}</span>`;
    }
  } else if (!comparaison && Object.keys(mm).length) {
    info = Object.keys(mm).map(k => `<span style="color:${{ mm20: "#B48CFF", mm50: "#6EA8FF", mm200: "#F2A65A" }[k]}">— ${k.toUpperCase().replace("MM", "MM ")}</span>`).join("")
         + (bb ? `<span style="color:#6EA8FF">▒ Bollinger</span>` : "");
  }
  $("gp-info").innerHTML = info;
  $("gp-info").style.display = info ? "" : "none";
}

(function brancherGP() {
  const cv = $("gp-canvas");
  const indexSouris = (e) => {
    const r = cv.getBoundingClientRect(), n = gp.fin - gp.debut + 1, larg = (r.width - 8 - 64) / n;
    return Math.min(gp.fin, Math.max(gp.debut, gp.debut + Math.floor((e.clientX - r.left - 8) / larg)));
  };
  cv.addEventListener("mousemove", (e) => {
    if (!gp.donnees.length) return;
    if (gp.glisse) {
      const r = cv.getBoundingClientRect(), n = gp.glisse.fin - gp.glisse.debut + 1, larg = (r.width - 72) / n;
      const dec = Math.round((gp.glisse.x - e.clientX) / larg);
      const debut = Math.min(Math.max(0, gp.glisse.debut + dec), gp.donnees.length - n);
      gp.debut = debut; gp.fin = debut + n - 1;
    }
    gp.survol = indexSouris(e); dessinerGP();
  });
  cv.addEventListener("mouseleave", () => { gp.survol = null; gp.glisse = null; dessinerGP(); });
  cv.addEventListener("mousedown", (e) => { gp.glisse = { x: e.clientX, debut: gp.debut, fin: gp.fin }; cv.style.cursor = "grabbing"; });
  window.addEventListener("mouseup", () => { gp.glisse = null; cv.style.cursor = "crosshair"; });
  cv.addEventListener("wheel", (e) => {
    if (!gp.donnees.length) return;
    e.preventDefault();
    const centre = indexSouris(e), n = gp.fin - gp.debut + 1, facteur = e.deltaY > 0 ? 1.15 : 0.87;
    const nn = Math.min(gp.donnees.length, Math.max(15, Math.round(n * facteur)));
    const part = (centre - gp.debut) / n;
    let debut = Math.round(centre - part * nn); debut = Math.min(Math.max(0, debut), gp.donnees.length - nn);
    gp.debut = debut; gp.fin = debut + nn - 1; dessinerGP();
  }, { passive: false });
  cv.addEventListener("dblclick", () => { gp.debut = 0; gp.fin = gp.donnees.length - 1; dessinerGP(); });
  window.addEventListener("resize", () => { if (mode === "graphique") dessinerGP(); });
  $("gp-periodes").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return;
    gp.periode = b.dataset.p; $("gp-periodes").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); chargerGP(); });
  $("gp-type").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return;
    gp.type = b.dataset.t; $("gp-type").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); dessinerGP(); });
  $("gp-indic").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return;
    const i = b.dataset.i; gp.indic.has(i) ? gp.indic.delete(i) : gp.indic.add(i); b.classList.toggle("on", gp.indic.has(i)); dessinerGP(); });
  $("gp-comparer").addEventListener("keydown", async (e) => {
    if (e.key !== "Enter") return;
    const q = e.target.value.trim(); if (!q) return;
    const a = (chercher(q)[0]) || { ticker: q.toUpperCase(), nom: q.toUpperCase() };
    if (a.ticker === gp.ticker || gp.comp.some(c => c.ticker === a.ticker) || gp.comp.length >= 4) return;
    e.target.value = "";
    try { gp.comp.push({ ticker: a.ticker, nom: a.nom, bougies: (await donneesOHLC(a.ticker, gp.periode)).bougies }); }
    catch { return; }
    majCompListe(); dessinerGP();
  });
  $("gp-comp-liste").addEventListener("click", (e) => { const b = e.target.closest("button[data-t]"); if (!b) return;
    gp.comp = gp.comp.filter(c => c.ticker !== b.dataset.t); majCompListe(); dessinerGP(); });
  $("voir-graphique").addEventListener("click", () => {
    if (courant && courant.a) ouvrirGraphique(courant.a.ticker, courant.a.nom);
  });
})();
function majCompListe() {
  $("gp-comp-liste").innerHTML = gp.comp.length
    ? `<span class="gp-comp-tag"><i style="background:${couleur("--or")}"></i>${echapper(gp.ticker || "")}</span>` +
      gp.comp.map((c, j) => `<span class="gp-comp-tag"><i style="background:${COULEURS_COMP[j % 4]}"></i>${echapper(c.ticker)}<button data-t="${echapper(c.ticker)}" title="Retirer" aria-label="Retirer">×</button></span>`).join("")
      + " (performance en % depuis le début de la période affichée)"
    : "";
}

// =====================================================================
// 2. CARTE DU MARCHÉ (treemap)
// =====================================================================
let carteUnivers = "cac";
function couleurVariation(v) {
  if (v == null) return "#2A3348";
  const t = Math.max(-1, Math.min(1, v / 0.03));
  const mel = (a, b, k) => a.map((x, i) => Math.round(x + (b[i] - x) * k));
  const neutre = [26, 34, 54], rouge = [194, 59, 59], vert = [47, 163, 111];
  const c = t < 0 ? mel(neutre, rouge, Math.sqrt(-t)) : mel(neutre, vert, Math.sqrt(t));
  return `rgb(${c.join(",")})`;
}
// Algorithme « squarified » (Bruls, Huizing, van Wijk) : des rectangles aussi carrés que possible
function squarifier(valeurs, x, y, w, h) {
  const total = valeurs.reduce((s, v) => s + v.valeur, 0) || 1, res = [];
  const items = valeurs.map(v => ({ ...v, aire: v.valeur / total * w * h })).sort((a, b) => b.aire - a.aire);
  let rx = x, ry = y, rw = w, rh = h, ligne = [];
  const pire = (l, cote) => { const s = l.reduce((t, i) => t + i.aire, 0), mx = Math.max(...l.map(i => i.aire)), mn = Math.min(...l.map(i => i.aire));
    return Math.max(cote * cote * mx / (s * s), s * s / (cote * cote * mn)); };
  const poser = () => {
    const s = ligne.reduce((t, i) => t + i.aire, 0);
    if (rw >= rh) { const lw = s / rh; let yy = ry; ligne.forEach(i => { const hh = i.aire / lw; res.push({ ...i, x: rx, y: yy, w: lw, h: hh }); yy += hh; }); rx += lw; rw -= lw; }
    else { const lh = s / rw; let xx = rx; ligne.forEach(i => { const ww = i.aire / lh; res.push({ ...i, x: xx, y: ry, w: ww, h: lh }); xx += ww; }); ry += lh; rh -= lh; }
    ligne = [];
  };
  items.forEach(it => {
    const cote = Math.min(rw, rh);
    if (!ligne.length || pire([...ligne, it], cote) <= pire(ligne, cote)) ligne.push(it); else { poser(); ligne.push(it); }
  });
  if (ligne.length) poser();
  return res;
}
async function chargerCarte(zone = $("carte-zone"), univers = carteUnivers, mini = false) {
  zone.innerHTML = `<p class="note-a" style="padding:12px">Chargement de la carte…</p>`;
  let d;
  for (let essai = 0; essai < 30; essai++) {
    try { const r = await fetch(`/api/marche/carte?univers=${univers}`); d = await r.json(); if (r.ok) break; }
    catch {}
    zone.innerHTML = `<p class="note-a" style="padding:12px">${echapper((d && d.erreur) || "Préparation des données…")}</p>`;
    await new Promise(r => setTimeout(r, 4000));
  }
  if (!Array.isArray(d)) return;
  dessinerCarte(zone, d, mini);
  if (!mini) {
    const avec = d.filter(x => x.var_jour != null), hausse = avec.filter(x => x.var_jour > 0).length;
    const moy = avec.reduce((s, x) => s + x.var_jour * x.capi, 0) / (avec.reduce((s, x) => s + x.capi, 0) || 1);
    $("carte-resume").innerHTML = `${hausse} en hausse, ${avec.length - hausse} en baisse · variation moyenne pondérée <b class="${sens(moy)}">${pctTxt(moy, 2)}</b>`;
  }
}
function dessinerCarte(zone, d, mini) {
  const W = zone.clientWidth, H = zone.clientHeight;
  const secteurs = {};
  d.forEach(x => (secteurs[x.secteur] = secteurs[x.secteur] || []).push(x));
  const blocs = squarifier(Object.entries(secteurs).map(([s, l]) => ({ nom: s, valeur: l.reduce((t, x) => t + x.capi, 0), liste: l })), 0, 0, W, H);
  let html = "";
  blocs.forEach(b => {
    html += `<div class="tm-secteur" style="left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px">${!mini && b.w > 70 && b.h > 30 ? `<div class="tm-nom">${echapper(b.nom)}</div>` : ""}`;
    const haut = !mini && b.h > 40 ? 14 : 0;
    squarifier(b.liste.map(x => ({ ...x, valeur: x.capi })), 0, haut, b.w, b.h - haut).forEach(c => {
      const cl = c.w < 34 || c.h < 22 ? "minuscule" : c.w < 64 || c.h < 40 ? "petit" : "";
      html += `<div class="tm-case ${cl}" data-t="${echapper(c.ticker)}" data-n="${echapper(c.nom)}" data-v="${c.var_jour ?? ""}" data-c="${c.capi}"
        style="left:${c.x}px;top:${c.y}px;width:${c.w}px;height:${c.h}px;background:${couleurVariation(c.var_jour)}">
        <b>${echapper(c.ticker.replace(/\.(PA|AS|BR|MI|LS|IR|OL)$/, ""))}</b><span>${c.var_jour == null ? "" : pctTxt(c.var_jour, 2)}</span></div>`;
    });
    html += "</div>";
  });
  zone.innerHTML = html;
}
let bulle = null;
document.addEventListener("mousemove", (e) => {
  const c = e.target.closest && e.target.closest(".tm-case");
  if (!c) { if (bulle) bulle.style.display = "none"; return; }
  if (!bulle) { bulle = document.createElement("div"); bulle.className = "tm-bulle"; document.body.appendChild(bulle); }
  const v = c.dataset.v === "" ? null : +c.dataset.v;
  bulle.innerHTML = `<b>${echapper(c.dataset.n)}</b> <span class="note-a">${echapper(c.dataset.t)}</span><br>
    Capitalisation : ${fr(+c.dataset.c / 1e9, 0)} Md € · Séance : <b class="${sens(v)}">${v == null ? "—" : pctTxt(v, 2)}</b>`;
  bulle.style.display = "block"; bulle.style.left = Math.min(e.clientX + 14, innerWidth - 300) + "px"; bulle.style.top = (e.clientY + 14) + "px";
});
document.addEventListener("click", (e) => {
  const c = e.target.closest && e.target.closest(".tm-case"); if (!c) return;
  if (bulle) bulle.style.display = "none";
  allerMode("simple"); lancerAnalyse({ ticker: c.dataset.t, nom: c.dataset.n, place: "" }, false);
});
$("carte-univers").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return;
  carteUnivers = b.dataset.u; $("carte-univers").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b)); chargerCarte(); });
window.addEventListener("resize", () => { if (mode === "carte") chargerCarte(); });

// =====================================================================
// 3. DEVISES, MATIÈRES PREMIÈRES, CRYPTOS
// =====================================================================
async function chargerMarches() {
  try {
    const d = await (await fetch("/api/marche/actifs")).json();
    $("marches-contenu").innerHTML = d.map(g => `<div class="groupe-actifs"><h3>${echapper(g.groupe)}</h3><div class="grille-indices">` +
      g.actifs.map(a => `<div class="indice" data-c="${echapper(a.code)}" data-n="${echapper(a.nom)}" title="${echapper(a.aide)}">
        <div class="n">${echapper(a.nom)} <span class="z">${echapper(a.unite)}</span></div>
        <div class="val">${fr(a.dernier, a.dernier < 10 ? 4 : 2)}</div>
        <div class="var ${sens(a.var_jour)}">${pctTxt(a.var_jour, 2)} <span class="z">· ${pctTxt(a.var_1an, 0)} sur 1 an · vol. ${fr(a.vol * 100, 0)} %</span></div>
        ${mini(a.mini)}</div>`).join("") + "</div></div>").join("");
  } catch { $("marches-contenu").innerHTML = `<p class="erreur">Données indisponibles.</p>`; }
}
$("marches-contenu").addEventListener("click", (e) => { const c = e.target.closest(".indice"); if (c) ouvrirGraphique(c.dataset.c, c.dataset.n); });

// =====================================================================
// 4. OPTIONS COTÉES
// =====================================================================
const opEtat = { ticker: null, nom: "" };
async function chargerOptions(ticker, nom, echeance = "") {
  if (mode !== "options") allerMode("options");
  opEtat.ticker = ticker; opEtat.nom = nom || ticker;
  $("op-titre").textContent = `Options cotées · ${opEtat.nom}`;
  $("op-contenu").innerHTML = `<p class="note-a">Chargement de la chaîne d'options…</p>`;
  const r = await fetch(`/api/options/${encodeURIComponent(ticker)}${echeance ? "?echeance=" + echeance : ""}`);
  const d = await r.json();
  if (d.erreur) { $("op-contenu").innerHTML = `<p class="erreur">${echapper(d.erreur)}</p>`; return; }
  const parK = new Map();
  d.calls.forEach(c => parK.set(c.strike, { k: c.strike, c }));
  d.puts.forEach(p => parK.set(p.strike, { ...(parK.get(p.strike) || { k: p.strike }), p }));
  const lignes = [...parK.values()].sort((a, b) => a.k - b.k);
  const atm = lignes.reduce((m, l) => Math.abs(l.k - d.cours) < Math.abs(m.k - d.cours) ? l : m, lignes[0]);
  const cel = (o, cote) => o ? `<td class="${o.dans_la_monnaie ? "itm" : ""}">${fr(o.dernier)}</td><td class="${o.dans_la_monnaie ? "itm" : ""}">${fr(o.achat)} / ${fr(o.vente)}</td>
      <td class="${o.dans_la_monnaie ? "itm" : ""}">${o.vol_implicite ? fr(o.vol_implicite * 100, 1) + " %" : "—"}</td><td class="${o.dans_la_monnaie ? "itm" : ""}">${fr(o.prix_bs)}</td>
      <td class="${o.dans_la_monnaie ? "itm" : ""}">${fr(o.volume, 0)}</td>` : `<td></td><td></td><td></td><td></td><td></td>`;
  $("op-contenu").innerHTML = `
    <div class="op-tete champs">
      <label>Échéance<select id="op-echeance">${d.echeances.map(e => `<option value="${e}" ${e === d.echeance ? "selected" : ""}>${new Date(e).toLocaleDateString("fr-FR", { day: "numeric", month: "short", year: "numeric" })}</option>`).join("")}</select></label>
      <div class="kpis-s" style="flex:1;margin:0">
        <div><div class="l">Cours</div><div class="v">${fr(d.cours)} $</div></div>
        <div><div class="l">Jours restants</div><div class="v">${d.jours}</div></div>
        <div><div class="l">Volatilité historique</div><div class="v">${fr(d.vol_historique * 100, 1)} %</div></div>
        <div><div class="l">Volatilité implicite</div><div class="v">${d.vol_implicite_atm ? fr(d.vol_implicite_atm * 100, 1) + " %" : "—"}</div></div></div>
    </div>
    <div class="lecture-s">${d.lecture.map(x => `<p>${echapper(x)}</p>`).join("")}</div>
    <h3>Sourire de volatilité</h3><svg id="op-sourire" class="svg-courbes" viewBox="0 0 1000 260" preserveAspectRatio="none" style="height:260px"></svg>
    <p class="note-a">Volatilité implicite selon le prix d'exercice (calls en or, puts en bleu ; trait vertical : cours actuel).
      Si la loi normale de Black-Scholes était exacte, la courbe serait plate : le « sourire » montre que le marché paie plus cher la protection contre les fortes baisses.</p>
    <h3>Chaîne d'options</h3>
    <div style="overflow-x:auto"><table class="t-options"><tr><th colspan="5">Calls (droit d'acheter)</th><th></th><th colspan="5" class="sep">Puts (droit de vendre)</th></tr>
      <tr><th>Dernier</th><th>Achat / vente</th><th>Vol. impl.</th><th>Black-Scholes</th><th>Volume</th><th style="text-align:center">Prix d'exercice</th>
          <th class="sep">Dernier</th><th>Achat / vente</th><th>Vol. impl.</th><th>Black-Scholes</th><th>Volume</th></tr>
      ${lignes.map(l => `<tr class="${l === atm ? "atm" : ""}">${cel(l.c)}<td class="k">${fr(l.k)}</td>${cel(l.p).replace("<td", '<td class="sep"')}</tr>`).join("")}</table></div>
    <p class="note-a">Prix en dollars par action (un contrat porte sur 100 actions). Surlignées : options « dans la monnaie », qui
      auraient une valeur si elles étaient exercées aujourd'hui. Colonne Black-Scholes : prix théorique avec la volatilité historique.</p>`;
  $("op-echeance").addEventListener("change", (e) => chargerOptions(opEtat.ticker, opEtat.nom, e.target.value));
  dessinerSourire(d);
}
function dessinerSourire(d) {
  const svg = $("op-sourire"), W = 1000, H = 260, g = 56, b = 26, h = 10;
  const pts = (l) => l.filter(o => o.vol_implicite && o.vol_implicite < 2).map(o => [o.strike, o.vol_implicite * 100]);
  const c = pts(d.calls), p = pts(d.puts), tous = c.concat(p); if (tous.length < 2) { svg.innerHTML = ""; return; }
  const xs = tous.map(t => t[0]), ys = tous.map(t => t[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.max(0, Math.min(...ys) - 3), y1 = Math.max(...ys) + 3;
  const X = v => g + (v - x0) / (x1 - x0) * (W - g - 10), Y = v => h + (1 - (v - y0) / (y1 - y0)) * (H - h - b);
  let out = "";
  for (let k = 0; k <= 4; k++) { const v = y0 + (y1 - y0) * k / 4; out += `<line class="grille" x1="${g}" x2="${W - 10}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${g - 6}" y="${Y(v) + 4}" text-anchor="end">${fr(v, 0)} %</text>`; }
  for (let k = 0; k <= 5; k++) { const v = x0 + (x1 - x0) * k / 5; out += `<text x="${X(v)}" y="${H - 6}" text-anchor="middle">${fr(v, 0)} $</text>`; }
  out += `<line x1="${X(d.cours)}" x2="${X(d.cours)}" y1="${h}" y2="${H - b}" stroke="var(--doux)" stroke-dasharray="4 4"/>`;
  const trace = (l, coul) => l.length ? `<path d="${l.map((t, i) => `${i ? "L" : "M"}${X(t[0])},${Y(t[1])}`).join("")}" fill="none" stroke="${coul}" stroke-width="2"/>` +
    l.map(t => `<circle cx="${X(t[0])}" cy="${Y(t[1])}" r="2.5" fill="${coul}"/>`).join("") : "";
  svg.innerHTML = out + trace(c, "var(--or)") + trace(p, "#6EA8FF");
}

// =====================================================================
// 5. ÉCONOMIE : COURBE DES TAUX ET CALENDRIER
// =====================================================================
let tauxDonnees = null, tauxChoix = 0;
async function afficherCourbeTaux() {
  const z = $("macro-contenu");
  if (!tauxDonnees) {
    z.innerHTML = `<p class="note-a">Chargement des courbes de taux…</p>`;
    try { tauxDonnees = await (await fetch("/api/taux")).json(); if (tauxDonnees.erreur) throw 0; }
    catch { tauxDonnees = null; z.innerHTML = `<p class="erreur">Données indisponibles.</p>`; return; }
  }
  const T = tauxDonnees, c = T.courbes[tauxChoix] || T.courbes[0];
  const coul = [couleur("--or"), "#6EA8FF", "#8D94A5", "#4A5470"];
  z.innerHTML = `
    <p class="aide">La courbe des taux relie le taux auquel un État emprunte à la durée de l'emprunt (de 3 mois à 30 ans).
      Normalement elle <b>monte</b> : prêter longtemps est plus risqué, donc mieux payé. Quand elle s'<b>inverse</b> (taux courts
      au-dessus des taux longs), les marchés anticipent des baisses de taux, souvent à cause d'un ralentissement : aux États-Unis,
      presque toutes les récessions depuis 50 ans ont été précédées d'une inversion.</p>
    <div class="onglets" id="taux-choix">${T.courbes.map((x, i) => `<button data-i="${i}" class="${i === tauxChoix ? "on" : ""}">${echapper(x.nom)}</button>`).join("")}</div>
    <div class="legende">${Object.keys(c.instantanes).map((k, j) => `<span style="--c:${coul[j]}">${echapper(k)}</span>`).join("")}</div>
    <svg id="taux-svg" class="svg-courbes" viewBox="0 0 1000 300" preserveAspectRatio="none"></svg>
    <h3>Écart entre les taux à 10 ans et à 2 ans</h3>
    <div class="legende">${T.ecarts.map((e, j) => `<span style="--c:${COULEURS_M[j]}">${echapper(e.nom)}</span>`).join("")}<span style="--c:var(--rouge)">Zéro : en dessous, courbe inversée</span></div>
    <svg id="ecart-svg" class="svg-courbes" viewBox="0 0 1000 300" preserveAspectRatio="none"></svg>
    <div class="lecture-s"><b>Ce qu'il faut retenir</b>${T.lecture.map(x => `<p>${x}</p>`).join("")}</div>
    <p class="note-a">Sources : Trésor américain (FRED) et Banque centrale européenne (courbes des emprunts d'État de la zone euro).</p>`;
  // Courbe : abscisse = échéance (échelle racine carrée pour lisibilité)
  const svg = $("taux-svg"), W = 1000, H = 300, g = 56, b = 30, h = 12;
  const ans = T.annees, xs = ans.map(a => Math.sqrt(a)), xmin = Math.min(...xs), xmax = Math.max(...xs);
  const vals = Object.values(c.instantanes).flat().filter(v => v != null);
  const y0 = Math.floor(Math.min(...vals) * 2) / 2 - 0.25, y1 = Math.ceil(Math.max(...vals) * 2) / 2 + 0.25;
  const X = i => g + (xs[i] - xmin) / (xmax - xmin) * (W - g - 20), Y = v => h + (1 - (v - y0) / (y1 - y0)) * (H - h - b);
  let out = "";
  for (let k = 0; k <= 4; k++) { const v = y0 + (y1 - y0) * k / 4; out += `<line class="grille" x1="${g}" x2="${W - 20}" y1="${Y(v)}" y2="${Y(v)}"/><text x="${g - 6}" y="${Y(v) + 4}" text-anchor="end">${fr(v, 1)} %</text>`; }
  const court = (e) => e.replace(" mois", " M").replace(" ans", " A").replace(" an", " A");
  T.echeances.forEach((e, i) => out += `<text x="${X(i)}" y="${H - 8}" text-anchor="middle">${court(e)}</text>`);
  Object.values(c.instantanes).reverse().forEach((serie, jj, arr) => {
    const j = arr.length - 1 - jj, pts = serie.map((v, i) => v == null ? null : [X(i), Y(v)]).filter(Boolean);
    out += `<path d="${pts.map((p, i) => `${i ? "L" : "M"}${p[0]},${p[1]}`).join("")}" fill="none" stroke="${coul[j]}" stroke-width="${j === 0 ? 3 : 1.6}"/>`;
    if (j === 0) out += pts.map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="4" fill="${coul[0]}"/><text x="${p[0]}" y="${p[1] - 10}" text-anchor="middle" style="fill:var(--texte)">${fr(serie.filter(v => v != null)[i], 2)}</text>`).join("");
  });
  svg.innerHTML = out;
  const ecarts = Object.fromEntries(T.ecarts.map(e => [e.nom, e.points]));
  courbes($("ecart-svg"), ecarts, COULEURS_M, null, { unite: " pt", decimales: 1, depuisZero: false, repere: 0, pointilles: false });
  $("taux-choix").addEventListener("click", (e) => { const bt = e.target.closest("button"); if (!bt) return; tauxChoix = +bt.dataset.i; afficherCourbeTaux(); });
}

let calDonnees = null, calFiltre = { imp: "High", zone: "princ" };
async function afficherCalendrier() {
  const z = $("macro-contenu");
  if (!calDonnees) {
    z.innerHTML = `<p class="note-a">Chargement du calendrier…</p>`;
    try { calDonnees = await (await fetch("/api/calendrier")).json(); if (calDonnees.erreur) throw 0; }
    catch { calDonnees = null; z.innerHTML = `<p class="erreur">Calendrier indisponible.</p>`; return; }
  }
  const imp = { High: 3, Medium: 2, Low: 1, Holiday: 0 };
  const ev = calDonnees.evenements.filter(e =>
    (calFiltre.imp === "tous" || imp[e.niveau] >= imp[calFiltre.imp]) &&
    (calFiltre.zone === "tous" || ["USD", "EUR", "CNY", "GBP", "JPY"].includes(e.code_pays)));
  const parJour = {};
  ev.forEach(e => (parJour[e.date] = parJour[e.date] || []).push(e));
  const etoiles = (n) => `<span class="imp">${"●".repeat(imp[n] || 0).split("").map((x, i) => `<span class="${n === "High" ? "r" : "o"}">${x}</span>`).join("")}${"●".repeat(3 - (imp[n] || 0))}</span>`;
  z.innerHTML = `
    <p class="aide">Les rendez-vous qui font bouger les marchés : décisions des banques centrales, chiffres de l'inflation et de
      l'emploi, croissance… Quand un chiffre s'écarte de la <b>prévision</b> des économistes, les marchés réagissent souvent fortement.</p>
    <div class="cal-filtres">
      <div class="segment" id="cal-imp"><button data-v="High">Importance forte</button><button data-v="Medium">Moyenne et forte</button><button data-v="tous">Tous</button></div>
      <div class="segment" id="cal-zone"><button data-v="princ">Grandes économies</button><button data-v="tous">Tous les pays</button></div>
    </div>
    ${Object.entries(parJour).map(([j, l]) => `<div class="cal-jour">${new Date(j).toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long" })}</div>` +
      l.map(e => `<div class="cal-ligne"><span class="h">${e.heure}</span><span class="p">${echapper(e.pays)}</span>
        <span>${echapper(e.titre)}${e.titre !== e.titre_original ? ` <span class="note-a">(${echapper(e.titre_original)})</span>` : ""}</span>
        ${etoiles(e.niveau)}<span class="v">prévu <b>${echapper(e.prevision || "—")}</b></span><span class="v">avant <b>${echapper(e.precedent || "—")}</b></span></div>`).join("")).join("")
      || `<p class="note-a">Aucun événement pour ces filtres.</p>`}
    <h3 style="margin-top:22px">Publications de résultats à venir</h3>
    <ul class="mini-liste">${(calDonnees.resultats || []).slice(0, 25).map(r => `<li><span><span class="tk">${echapper(r.ticker || "")}</span> ${echapper(r.nom || "")}</span>
      <span class="note-a">${r.date ? new Date(r.date).toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) : ""} ${r.moment || r.heure || ""}
      ${r.bpa_attendu != null ? `· BPA attendu ${fr(r.bpa_attendu)}` : ""}</span></li>`).join("") || "<li>Aucune donnée.</li>"}</ul>
    <p class="note-a">Heures de Paris. Sources : calendrier public Forex Factory (titres traduits pour les plus courants) et Yahoo Finance.</p>`;
  ["cal-imp", "cal-zone"].forEach(id => {
    const cle = id === "cal-imp" ? "imp" : "zone";
    $(id).querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.v === calFiltre[cle]));
    $(id).addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; calFiltre[cle] = b.dataset.v; afficherCalendrier(); });
  });
}

// =====================================================================
// 6. BARRE DE COMMANDES (⌘K)
// =====================================================================
const COMMANDES = [
  { c: "LVMH", d: "Analyser une action (nom ou ticker)", x: "ex. LVMH, AAPL, Airbus" },
  { c: "G LVMH", d: "Graphique interactif d'une action", x: "G = graphique" },
  { c: "COMP MC.PA KER.PA", d: "Comparer deux actions", x: "COMP" },
  { c: "CARTE", d: "Carte du marché", x: "CARTE CAC · CARTE EU · CARTE SP" },
  { c: "FX", d: "Devises, matières premières et cryptomonnaies", x: "aussi MP, CRYPTO" },
  { c: "ECO", d: "Économie : inflation, taux, chômage, croissance", x: "" },
  { c: "TAUX", d: "Courbe des taux", x: "" },
  { c: "CAL", d: "Calendrier économique et résultats", x: "" },
  { c: "OPT AAPL", d: "Options cotées d'une action américaine", x: "" },
  { c: "PF", d: "Mon portefeuille", x: "+ AAPL : ajouter au portefeuille" },
  { c: "SUIVI", d: "Liste de suivi et agenda", x: "SUIVRE AAPL : ajouter" },
  { c: "BF", d: "Bourse fictive", x: "ACHAT 10 AIR.PA · VENTE 5 AIR.PA" },
  { c: "SIM", d: "Simulateur d'investissement mensuel", x: "SIM ^FCHI" },
  { c: "FILTRE", d: "Filtre d'actions", x: "" },
  { c: "ACCUEIL", d: "Tableau de bord des marchés", x: "aussi HOME" },
];
let cmdChoix = [], cmdActif = 0;
const resoudre = (txt) => {
  const q = (txt || "").trim(); if (!q) return null;
  return chercher(q)[0] || { ticker: q.toUpperCase(), nom: q.toUpperCase(), place: "" };
};
function ouvrirCmd() { $("cmd-fond").hidden = false; $("cmd-champ").value = ""; majCmd(); setTimeout(() => $("cmd-champ").focus(), 10); }
function fermerCmd() { $("cmd-fond").hidden = true; }
function majCmd() {
  const v = $("cmd-champ").value.trim(), V = v.toUpperCase(), mots = V.split(/\s+/);
  cmdChoix = [];
  const ajouter = (lib, desc, act, groupe = "Commandes") => cmdChoix.push({ lib, desc, act, groupe });
  if (!v) COMMANDES.forEach(c => ajouter(c.c, c.d + (c.x ? ` <span class="x">${c.x}</span>` : ""), () => executerCmd(c.c)));
  else {
    ajouter(v, "Exécuter cette commande", () => executerCmd(v), "Ta saisie");
    COMMANDES.filter(c => c.c.startsWith(mots[0]) && c.c !== V).slice(0, 4).forEach(c => ajouter(c.c, c.d, () => { $("cmd-champ").value = c.c.split(" ")[0] + " "; majCmd(); }));
    const reste = mots.length > 1 && ["G", "OPT", "SIM", "SUIVRE", "+", "COMP"].includes(mots[0]) ? v.split(/\s+/).slice(-1)[0] : v;
    chercher(reste).slice(0, 7).forEach(a => ajouter(a.ticker, `${echapper(a.nom)} <span class="x">${echapper(a.place)}</span>`,
      () => mots.length > 1 ? executerCmd(v.split(/\s+/).slice(0, -1).join(" ") + " " + a.ticker) : (fermerCmd(), allerMode("simple"), lancerAnalyse(a, false)), "Actions"));
  }
  cmdActif = 0;
  let groupe = null;
  $("cmd-liste").innerHTML = cmdChoix.map((c, i) => {
    const t = c.groupe !== groupe ? `<div class="cmd-groupe">${c.groupe}</div>` : ""; groupe = c.groupe;
    return t + `<div class="cmd-item${i === 0 ? " actif" : ""}" data-i="${i}"><span class="c">${echapper(c.lib)}</span><span class="d">${c.desc}</span></div>`;
  }).join("");
}
async function executerCmd(texte) {
  const t = texte.trim(), m = t.split(/\s+/), C = m[0].toUpperCase(), args = m.slice(1);
  fermerCmd();
  const simple = { ACCUEIL: allerAccueil, HOME: allerAccueil, PF: () => allerMode("portefeuille"), SUIVI: () => allerMode("suivi"),
    BF: () => allerMode("fictifs"), FICTIF: () => allerMode("fictifs"), FILTRE: () => allerMode("screener"),
    ECO: () => { macroTheme = "inflation"; allerMode("macro"); }, TAUX: () => { macroTheme = "courbe"; allerMode("macro"); },
    CAL: () => { macroTheme = "calendrier"; allerMode("macro"); }, FX: () => allerMode("marches"), MP: () => allerMode("marches"),
    CRYPTO: () => allerMode("marches"), MARCHES: () => allerMode("marches"), AIDE: () => { ouvrirCmd(); }, HELP: () => { ouvrirCmd(); } };
  if (simple[C] && !args.length) return simple[C]();
  if (C === "CARTE") { const u = { CAC: "cac", EU: "eu", EURONEXT: "eu", SP: "sp", US: "sp" }[(args[0] || "CAC").toUpperCase()] || "cac";
    carteUnivers = u; $("carte-univers").querySelectorAll("button").forEach(x => x.classList.toggle("on", x.dataset.u === u)); return allerMode("carte"); }
  if (C === "G" || C === "GR" || C === "GRAPHIQUE") { const a = resoudre(args.join(" ")) || { ticker: "^FCHI", nom: "CAC 40" }; return ouvrirGraphique(a.ticker, a.nom); }
  if (C === "OPT" || C === "OPTIONS") { const a = resoudre(args.join(" ")); if (a) return chargerOptions(a.ticker, a.nom); return allerMode("options"); }
  if (C === "COMP" && args.length >= 2) return comparerDepuis(resoudre(args[0]), resoudre(args[1]));
  if (C === "SIM") { allerMode("simulateur"); const a = resoudre(args.join(" ")); if (a) choisirActifSim(a.ticker, a.nom); return; }
  if (C === "SUIVRE" && args.length) { const a = resoudre(args.join(" ")); await ajouterAuSuivi(a); return allerMode("suivi"); }
  if (C === "+" && args.length) { ajouterAuPf(resoudre(args.join(" "))); return allerMode("portefeuille"); }
  if ((C === "ACHAT" || C === "VENTE") && args.length >= 2) {
    const q = +args[0], a = resoudre(args.slice(1).join(" "));
    allerMode("fictifs");
    let l = []; try { l = await (await fetch("/api/fictifs")).json(); } catch {}
    if (!Array.isArray(l) || !l.length) return alert("Crée d'abord un portefeuille fictif.");
    const id = fxCourant || l[0].id;
    const r = await (await fetch(`/api/fictifs/${id}/ordre`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sens: C === "ACHAT" ? "achat" : "vente", ticker: a.ticker, nom: a.nom, quantite: q }) })).json();
    await chargerFictifs();
    const msg = $("fx-message"); if (msg) { msg.className = r.erreur ? "err" : "ok"; msg.textContent = r.erreur || `Ordre exécuté : ${C === "ACHAT" ? "achat" : "vente"} de ${q} ${a.ticker} à ${fr(r.prix)} ${r.devise}.`; }
    return;
  }
  const a = resoudre(t); if (a) { allerMode("simple"); lancerAnalyse(a, false); }
}
$("cmd-champ").addEventListener("input", majCmd);
$("cmd-champ").addEventListener("keydown", (e) => {
  const items = $("cmd-liste").querySelectorAll(".cmd-item");
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault(); cmdActif = (cmdActif + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items.forEach((x, i) => x.classList.toggle("actif", i === cmdActif)); items[cmdActif]?.scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter") { e.preventDefault(); cmdChoix[cmdActif]?.act(); }
  else if (e.key === "Escape") fermerCmd();
});
$("cmd-liste").addEventListener("click", (e) => { const it = e.target.closest(".cmd-item"); if (it) cmdChoix[+it.dataset.i].act(); });
$("cmd-fond").addEventListener("mousedown", (e) => { if (e.target === $("cmd-fond")) fermerCmd(); });
$("ouvrir-cmd").addEventListener("click", ouvrirCmd);
document.addEventListener("keydown", (e) => {
  if (e.metaKey && e.key.toLowerCase() === "k") { e.preventDefault(); $("cmd-fond").hidden ? ouvrirCmd() : fermerCmd(); }
});

// =====================================================================
// 7. ACCUEIL PERSONNALISABLE
// =====================================================================
const BLOCS_ACCUEIL = [
  { id: "bandeau", nom: "Bandeau défilant des marchés" },
  { id: "marches", nom: "Indices et grand graphique" },
  { id: "carte", nom: "Carte du marché (CAC 40)" },
  { id: "agenda", nom: "Agenda économique de la semaine" },
  { id: "phares", nom: "Valeurs phares et actualité économique" },
  { id: "suivi", nom: "Ma liste de suivi" },
  { id: "fictifs", nom: "Mes portefeuilles fictifs" },
  { id: "palmares", nom: "Hausses, baisses et actions volatiles" },
];
(function construireAccueil() {
  const acc = $("accueil"), enfants = [...acc.children];
  const trouve = (sel) => enfants.find(e => e.matches(sel));
  const envelopper = (id, elements) => {
    const div = document.createElement("div"); div.className = "bloc-accueil"; div.dataset.bloc = id;
    elements.filter(Boolean).forEach(e => div.appendChild(e)); return div;
  };
  const intro = trouve(".intro");
  const blocs = {
    bandeau: envelopper("bandeau", [trouve(".bandeau")]),
    marches: envelopper("marches", [trouve(".titre-section"), trouve(".grille-indices"), trouve(".grand-graphe")]),
    phares: envelopper("phares", [trouve(".colonnes-a")]),
    palmares: envelopper("palmares", [trouve(".trois-a"), trouve("#note-univers")]),
  };
  const neuf = (id, html) => { const d = document.createElement("div"); d.className = "bloc-accueil"; d.dataset.bloc = id; d.innerHTML = html; return d; };
  blocs.carte = neuf("carte", `<div class="titre-section">Carte du marché <small>CAC 40 · dernière séance</small></div>
    <div class="carte-a"><div id="carte-mini" class="carte-zone mini"></div></div>`);
  blocs.agenda = neuf("agenda", `<div class="titre-section">Cette semaine <small>événements économiques importants</small></div>
    <div class="carte-a"><div id="agenda-mini"><p class="note-a">Chargement…</p></div></div>`);
  blocs.suivi = neuf("suivi", `<div class="titre-section">Ma liste de suivi</div><div class="carte-a"><ul class="mini-liste" id="suivi-mini"><li>Chargement…</li></ul></div>`);
  blocs.fictifs = neuf("fictifs", `<div class="titre-section">Mes portefeuilles fictifs</div><div class="carte-a"><ul class="mini-liste" id="fictifs-mini"><li>Chargement…</li></ul></div>`);
  acc.innerHTML = "";
  if (intro) acc.appendChild(intro);
  const perso = document.createElement("div");
  perso.innerHTML = `<button class="bouton secondaire perso-bouton" id="perso-ouvrir">⚙︎ Personnaliser l'accueil</button><div id="perso-panneau"></div>`;
  acc.appendChild(perso);
  window.__blocsAccueil = blocs;
  appliquerAccueil();
  $("perso-ouvrir").addEventListener("click", () => {
    const p = $("perso-panneau"); if (p.innerHTML) { p.innerHTML = ""; return; }
    afficherPerso();
  });
})();
function lireConfigAccueil() {
  let c; try { c = JSON.parse(localStorage.getItem("accueil") || "null"); } catch {}
  const defaut = BLOCS_ACCUEIL.map(b => ({ id: b.id, visible: true }));
  if (!Array.isArray(c)) return defaut;
  BLOCS_ACCUEIL.forEach(b => { if (!c.some(x => x.id === b.id)) c.push({ id: b.id, visible: true }); });
  return c.filter(x => BLOCS_ACCUEIL.some(b => b.id === x.id));
}
function appliquerAccueil() {
  const acc = $("accueil"), cfg = lireConfigAccueil();
  cfg.forEach(c => { const el = window.__blocsAccueil[c.id]; if (el) { el.hidden = !c.visible; acc.appendChild(el); } });
  const vis = (id) => cfg.find(c => c.id === id)?.visible;
  if (vis("carte") && !$("carte-mini").innerHTML) chargerCarte($("carte-mini"), "cac", true);
  if (vis("agenda")) agendaMini();
  if (vis("suivi")) suiviMini();
  if (vis("fictifs")) fictifsMini();
}
function afficherPerso() {
  const cfg = lireConfigAccueil();
  $("perso-panneau").innerHTML = `<div class="perso-panneau"><b>Blocs de l'accueil</b> <span class="note-a">— coche ceux à afficher, change leur ordre avec les flèches</span>
    <ul>${cfg.map((c, i) => `<li><input type="checkbox" data-i="${i}" ${c.visible ? "checked" : ""}><span>${BLOCS_ACCUEIL.find(b => b.id === c.id).nom}</span>
      <button class="lien" data-h="${i}" aria-label="Monter" ${i === 0 ? "disabled" : ""}>↑</button><button class="lien" data-b="${i}" aria-label="Descendre" ${i === cfg.length - 1 ? "disabled" : ""}>↓</button></li>`).join("")}</ul>
    <button class="lien" id="perso-defaut">Revenir à l'accueil par défaut</button></div>`;
  const sauver = (c) => { try { localStorage.setItem("accueil", JSON.stringify(c)); } catch {} appliquerAccueil(); afficherPerso(); };
  $("perso-panneau").onclick = (e) => {
    const t = e.target, c = lireConfigAccueil();
    if (t.dataset.h) { const i = +t.dataset.h; [c[i - 1], c[i]] = [c[i], c[i - 1]]; sauver(c); }
    else if (t.dataset.b) { const i = +t.dataset.b; [c[i + 1], c[i]] = [c[i], c[i + 1]]; sauver(c); }
    else if (t.id === "perso-defaut") { try { localStorage.removeItem("accueil"); } catch {} appliquerAccueil(); afficherPerso(); }
  };
  $("perso-panneau").onchange = (e) => { if (e.target.dataset.i == null) return; const c = lireConfigAccueil(); c[+e.target.dataset.i].visible = e.target.checked; sauver(c); };
}
async function agendaMini() {
  try {
    const d = await (await fetch("/api/calendrier")).json();
    const ev = (d.evenements || []).filter(e => e.niveau === "High" && ["USD", "EUR", "CNY"].includes(e.code_pays) && e.date >= new Date().toISOString().slice(0, 10)).slice(0, 8);
    $("agenda-mini").innerHTML = ev.length ? `<ul class="mini-liste">${ev.map(e => `<li><span><b>${new Date(e.date).toLocaleDateString("fr-FR", { weekday: "short", day: "numeric" })}</b>
      <span class="note-a">${e.heure}</span> ${echapper(e.pays)} · ${echapper(e.titre)}</span><span class="note-a">prévu ${echapper(e.prevision || "—")}</span></li>`).join("")}</ul>
      <button class="lien" onclick="executerCmd('CAL')">Tout le calendrier →</button>` : `<p class="note-a">Aucun événement majeur cette semaine.</p>`;
  } catch { $("agenda-mini").innerHTML = `<p class="note-a">Calendrier indisponible.</p>`; }
}
async function suiviMini() {
  try {
    const d = await (await fetch("/api/suivi/etat")).json();
    $("suivi-mini").innerHTML = (d.lignes || []).map(l => `<li><span><span class="tk">${echapper(l.ticker)}</span> ${echapper(l.nom)}</span>
      <span>${l.dernier != null ? fr(l.dernier) : "…"} <b class="${sens(l.var_jour)}">${l.var_jour != null ? pctTxt(l.var_jour) : ""}</b></span></li>`).join("")
      || `<li class="note-a">Liste vide : ⌘K puis « SUIVRE LVMH » pour suivre une action.</li>`;
  } catch {}
}
async function fictifsMini() {
  try {
    const l = await (await fetch("/api/fictifs")).json();
    $("fictifs-mini").innerHTML = (Array.isArray(l) ? l : []).map(p => `<li><span>${echapper(p.nom)}</span><span>${p.valeur != null ? fr(p.valeur, 0) + " €" : "—"}
      <b class="${sens(p.performance)}">${p.performance != null ? pctTxt(p.performance) : ""}</b></span></li>`).join("")
      || `<li class="note-a">Aucun portefeuille fictif : ⌘K puis « BF » pour en créer un.</li>`;
  } catch {}
}


// ---------- Accessibilité clavier ----------
// Les cases de la carte, les cartes d'indices et les lignes de tableau cliquables sont des <div>/<tr> :
// on les rend atteignables avec Tab et activables avec Entrée ou Espace, comme de vrais boutons.
const CLIQUABLES = ".tm-case, .indice, tr.cliquable";
let _accesPrevu = false;
function rendreAccessibles() {
  _accesPrevu = false;
  document.querySelectorAll(CLIQUABLES).forEach(el => {
    if (el.hasAttribute("tabindex")) return;
    el.tabIndex = 0;
    if (!el.getAttribute("role")) el.setAttribute("role", "button");
    if (el.classList.contains("tm-case") && el.dataset.n)
      el.setAttribute("aria-label", `${el.dataset.n}, séance : ${el.dataset.v === "" ? "variation inconnue" : pctTxt(+el.dataset.v, 2)}`);
  });
}
new MutationObserver(() => { if (!_accesPrevu) { _accesPrevu = true; requestAnimationFrame(rendreAccessibles); } })
  .observe(document.body, { childList: true, subtree: true });
rendreAccessibles();
document.addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches && e.target.matches(CLIQUABLES)) {
    e.preventDefault(); e.target.click();
  }
});
