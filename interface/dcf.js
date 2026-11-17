// =====================================================================
// MODÈLE DCF COMPLET (chargé après pro.js : utilise $, fr, pctTxt, sens, echapper, allerMode, mode…)
// Les calculs sont faits par le serveur (dcf_avance.py) : la page envoie les hypothèses,
// reçoit le modèle et met à jour les cellules calculées sans toucher aux champs saisis.
// =====================================================================
const dcf = { ticker: null, nom: "", h: null, r: null, minuteur: null, requete: 0 };
const HORIZON_DCF = 5;

window.ouvertureDCF = function () {
  if (dcf.ticker) return;
  const a = (typeof courant !== "undefined" && courant && courant.a) ? courant.a : null;
  $("dcf-contenu").innerHTML = `<p class="note-a">Exemples : LVMH (MC.PA), Airbus (AIR.PA), Apple (AAPL), Microsoft (MSFT).</p>` +
    (a ? `<p><button class="bouton" id="dcf-courant">Évaluer ${echapper(a.nom)}</button></p>` : "");
  if (a) $("dcf-courant").addEventListener("click", () => ouvrirDCF(a.ticker, a.nom));
};

async function ouvrirDCF(ticker, nom) {
  dcf.ticker = ticker; dcf.nom = nom || ticker; dcf.h = null; dcf.r = null;
  if (mode !== "dcf") allerMode("dcf");
  $("dcf-titre").textContent = `Modèle DCF · ${dcf.nom}`;
  $("dcf-contenu").innerHTML = `<p class="note-a" role="status">Chargement des comptes et du consensus des analystes…</p>`;
  const r = await calculerDCF();
  if (!r) return;
  dcf.h = structuredClone(r.hypotheses);
  construireDCF(r);
  majDCF(r);
}

async function calculerDCF() {
  const n = ++dcf.requete;
  try {
    const rep = await fetch(`/api/dcf/${encodeURIComponent(dcf.ticker)}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hypotheses: dcf.h || {} }) });
    const r = await rep.json();
    if (n !== dcf.requete) return null;                     // une réponse plus récente arrive
    if (r.erreur) {
      if (!dcf.r) $("dcf-contenu").innerHTML = `<p class="note-a">${echapper(r.erreur)}</p>`;
      else $("dcf-erreur").textContent = r.erreur;
      return null;
    }
    if ($("dcf-erreur")) $("dcf-erreur").textContent = "";
    dcf.r = r;
    return r;
  } catch {
    if (!dcf.r) $("dcf-contenu").innerHTML = `<p class="note-a">Calcul impossible pour le moment (connexion ?).</p>`;
    return null;
  }
}

// ---------- Mise en forme ----------
const md = (x) => x == null ? "—" : fr(x / 1e9, 1).replace("-", "−");
const pc = (x, d = 1) => x == null ? "—" : fr(x * 100, d).replace("-", "−") + " %";
const champPct = (cle, i, v, step = 0.1) =>
  `<input class="dcf-in" type="number" step="${step}" data-h="${cle}"${i != null ? ` data-i="${i}"` : ""} value="${+(v * 100).toFixed(2)}" aria-label="${cle}">`;

function construireDCF(r) {
  const c = r.contexte, h = r.hypotheses, hist = c.historique.slice(-3);
  const dev = c.devise_compta, devc = c.devise_cours;
  const ans = r.resultat.projections.map(p => p.annee);
  const consensus = (c.consensus || []).map(x => x != null);
  const thHist = hist.map(a => `<th class="hist">${a.annee}</th>`).join("");
  const thProj = ans.map((a, i) => `<th>${a}${i < 2 && consensus[i] ? ' <span class="dcf-cons" title="Croissance issue du consensus des analystes">consensus</span>' : ""}</th>`).join("");
  const histCel = (k, f) => hist.map(a => `<td class="hist">${f(a[k])}</td>`).join("");
  const calc = (k) => ans.map((_, i) => `<td data-p="${k}" data-i="${i}"></td>`).join("");
  const saisie = (k) => ans.map((_, i) => `<td>${champPct(k, i, h[k][i])}</td>`).join("");
  const ligne = (lib, cellsHist, cells, cls = "") => `<tr class="${cls}"><th scope="row">${lib}</th>${cellsHist}${cells}</tr>`;
  const vide = hist.map(() => `<td class="hist"></td>`).join("");

  const tableau = `<table class="t-dcf">
    <thead><tr><th>En milliards de ${echapper(dev)}</th>${thHist}${thProj}</tr></thead><tbody>
    ${ligne("Croissance du chiffre d'affaires", histCel("croissance", x => pc(x)), saisie("croissance"), "entree")}
    ${ligne("Chiffre d'affaires", histCel("ca", md), calc("ca"))}
    ${ligne("Marge d'EBITDA (EBE / CA)", histCel("marge_ebitda", x => pc(x)), saisie("marge_ebitda"), "entree")}
    ${ligne("EBITDA (EBE)", histCel("ebitda", md), calc("ebitda"))}
    ${ligne("Amortissements en % du CA", histCel("da_ca", x => pc(x)), saisie("da_ca"), "entree")}
    ${ligne("EBIT (résultat d'exploitation)", histCel("ebit", md), calc("ebit"))}
    ${ligne("Impôt sur l'EBIT", vide, calc("impot"))}
    ${ligne("Investissements (capex) en % du CA", histCel("capex_ca", x => pc(x)), saisie("capex_ca"), "entree")}
    ${ligne("Investissements (capex)", histCel("capex", x => md(x == null ? null : -x)), calc("capex"))}
    ${ligne("Variation du BFR (effet sur la trésorerie)", vide, calc("dbfr"))}
    ${ligne("= FCFF (flux disponible)", vide, calc("fcff"), "total")}
    ${ligne("× Facteur d'actualisation", vide, calc("facteur"))}
    ${ligne("= FCFF actualisé", vide, calc("fcff_actualise"), "total")}
    </tbody></table>`;

  const param = (lib, cle, aide, pct = true, step = 0.1) => `<label class="dcf-param" title="${aide}">${lib}
      ${pct ? champPct(cle, null, h[cle], step) : `<input class="dcf-in" type="number" step="${step}" data-h="${cle}" data-brut="1" value="${h[cle]}" aria-label="${cle}">`}
      <span>${pct ? "%" : ""}</span></label>`;
  const scen = (cle, lib) => `<tr><th scope="row">${lib}</th>
      <td>${champPct("sc." + cle + ".dg", null, h.scenarios[cle].dg, 0.5)} pt</td>
      <td>${champPct("sc." + cle + ".dm", null, h.scenarios[cle].dm, 0.5)} pt</td>
      <td>${champPct("sc." + cle + ".p", null, h.scenarios[cle].p, 5)}</td>
      <td data-s="${cle}.v"></td><td data-s="${cle}.pot"></td></tr>`;

  $("dcf-contenu").innerHTML = `
    <div class="kpis-s dcf-kpis">
      <div><div class="l">Valeur par action</div><div class="v" id="dcf-k-valeur"></div></div>
      <div><div class="l">Cours actuel</div><div class="v">${fr(c.cours, 2)} ${echapper(devc)}</div></div>
      <div><div class="l">Potentiel</div><div class="v" id="dcf-k-pot"></div></div>
      <div><div class="l">Valeur pondérée (3 scénarios)</div><div class="v" id="dcf-k-pond"></div></div>
      <div><div class="l">Croissance anticipée par le cours</div><div class="v" id="dcf-k-inverse"></div></div>
      <div><div class="l">CMPC</div><div class="v" id="dcf-k-cmpc"></div></div>
    </div>
    <p class="dcf-erreur" id="dcf-erreur" role="alert"></p>
    <div class="lecture-s" id="dcf-lecture" aria-live="polite"></div>

    <h3>1. Projection année par année</h3>
    <p class="note-a">Colonnes grisées : comptes publiés. Par défaut, la croissance des deux premières années vient du consensus des
      analystes (si disponible), puis converge vers la croissance à l'infini ; marges, amortissements et investissements reprennent
      la moyenne des trois derniers exercices.</p>
    <div class="dcf-defile">${tableau}</div>

    <div class="dcf-grille">
      <div>
        <h3>2. Coût du capital et hypothèses générales</h3>
        <div class="dcf-params">
          ${param("Taux sans risque", "rf", "Rendement d'un emprunt d'État sans risque")}
          ${param("Prime de risque du marché", "prime", "Supplément de rendement exigé pour détenir des actions")}
          ${param("Bêta ajusté", "beta", "Bêta sur 5 ans (rendements hebdomadaires), ajusté de Blume : 0,67 × bêta + 0,33, avec un plancher de 0,7", false, 0.05)}
          ${param("Coût de la dette (avant impôt)", "kd", "Taux d'intérêt moyen payé sur la dette")}
          ${param("Taux d'impôt", "taux_is", "Taux d'impôt effectif moyen des derniers exercices")}
          ${param("Poids des capitaux propres", "poids_cp", "Capitalisation / (capitalisation + dette)", true, 1)}
        </div>
        <p class="dcf-formule">Coût des capitaux propres = rf + β × prime = <b id="dcf-kcp"></b><br>
          CMPC = poids × coût des capitaux propres + (1 − poids) × coût de la dette × (1 − impôt) = <b id="dcf-cmpc"></b></p>
        <div class="dcf-params">
          ${param("Croissance à l'infini (g)", "g_inf", "Croissance des flux après l'année 5 : proche de l'inflation de long terme", true, 0.1)}
          ${param("Multiple de sortie (VE / EBITDA)", "multiple_sortie", "Prix de revente de l'entreprise en année 5, en nombre de fois l'EBITDA", false, 0.5)}
          ${param("BFR en % du CA", "bfr_ca", "Besoin en fonds de roulement : chaque euro de CA en plus immobilise ce pourcentage")}
        </div>
        <div class="dcf-ligne-choix">Valeur terminale retenue :
          <div class="segment" id="dcf-methode">
            <button data-v="gordon">Gordon-Shapiro</button><button data-v="multiple">Multiple de sortie</button><button data-v="moyenne">Moyenne</button>
          </div></div>
        <label class="dcf-coche"><input type="checkbox" id="dcf-demi" ${h.demi_annee ? "checked" : ""}> Convention de demi-année
          <span class="note-a">(les flux arrivent en moyenne au milieu de l'année : actualisation à t − 0,5)</span></label>
      </div>
      <div>
        <h3>3. De la valeur d'entreprise à la valeur par action</h3>
        <table class="t-pont" id="dcf-pont"></table>
        <h3>4. Valeur terminale : deux méthodes</h3>
        <table class="t-pont" id="dcf-vt"></table>
        <p class="note-a" id="dcf-pairs"></p>
      </div>
    </div>

    <h3>5. Scénarios</h3>
    <p class="note-a">Écarts appliqués à chaque année du scénario central : croissance du CA et marge d'EBITDA, en points de pourcentage.</p>
    <table class="t-dcf t-scen"><thead><tr><th>Scénario</th><th>Écart de croissance</th><th>Écart de marge</th><th>Probabilité</th>
      <th>Valeur par action</th><th>Potentiel</th></tr></thead><tbody>
      ${scen("pessimiste", "Pessimiste")}
      <tr><th scope="row">Central</th><td>0 pt</td><td>0 pt</td><td data-s="central.p"></td><td data-s="central.v"></td><td data-s="central.pot"></td></tr>
      ${scen("optimiste", "Optimiste")}
      <tr class="total"><th scope="row">Valeur pondérée</th><td></td><td></td><td></td><td data-s="pond.v"></td><td data-s="pond.pot"></td></tr>
    </tbody></table>

    <h3>6. Sensibilité de la valeur par action</h3>
    <div class="dcf-grille" id="dcf-sens"></div>

    <div class="dcf-actions">
      <button class="bouton" id="dcf-excel">Exporter le modèle Excel (avec formules)</button>
      <button class="bouton secondaire" id="dcf-reinit">Revenir aux hypothèses par défaut</button>
      <span id="dcf-msg" class="note-a" role="status" aria-live="polite"></span>
    </div>
    <p class="note-a">Un DCF ne donne pas « la » valeur d'une action : il traduit des hypothèses en prix. Le DCF inversé et les
      sensibilités montrent quelles hypothèses comptent vraiment. Outil pédagogique, pas un conseil en investissement.</p>`;

  $("dcf-methode").querySelectorAll("button").forEach(b => b.classList.toggle("on", b.dataset.v === h.methode_vt));
  $("dcf-methode").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    dcf.h.methode_vt = b.dataset.v;
    $("dcf-methode").querySelectorAll("button").forEach(x => x.classList.toggle("on", x === b));
    relancer(0);
  });
  $("dcf-demi").addEventListener("change", (e) => { dcf.h.demi_annee = e.target.checked; relancer(0); });
  $("dcf-reinit").addEventListener("click", () => { dcf.h = null; ouvrirDCF(dcf.ticker, dcf.nom); });
  $("dcf-excel").addEventListener("click", exporterDCF);
}

document.addEventListener("input", (e) => { if (e.target.closest && e.target.closest("#dcf-contenu")) lireSaisie(e); });
function lireSaisie(e) {
  const el = e.target;
  if (!el.matches || !el.matches("input.dcf-in")) return;
  const v = parseFloat(el.value);
  if (isNaN(v)) return;
  const val = el.dataset.brut ? v : v / 100, cle = el.dataset.h;
  if (cle.startsWith("sc.")) { const [, s, k] = cle.split("."); dcf.h.scenarios[s][k] = val; }
  else if (el.dataset.i != null) dcf.h[cle][+el.dataset.i] = val;
  else dcf.h[cle] = val;
  relancer(300);
}

function relancer(delai) {
  clearTimeout(dcf.minuteur);
  dcf.minuteur = setTimeout(async () => { const r = await calculerDCF(); if (r) majDCF(r); }, delai);
}

function majDCF(r) {
  const c = r.contexte, m = r.resultat, h = r.hypotheses, devc = c.devise_cours, dev = c.devise_compta;
  const val = (x) => x == null ? "—" : `${fr(x, 2)} ${echapper(devc)}`;
  $("dcf-k-valeur").textContent = val(m.valeur_action);
  const negatif = m.valeur_action != null && m.valeur_action <= 0;
  $("dcf-k-pot").textContent = negatif ? "n. s." : pctTxt(m.potentiel); $("dcf-k-pot").className = "v " + (negatif ? "" : sens(m.potentiel));
  $("dcf-k-pond").textContent = val(r.valeur_ponderee);
  $("dcf-k-inverse").textContent = r.g_marche == null ? "—" : pc(r.g_marche) + " / an";
  $("dcf-k-cmpc").textContent = pc(m.cmpc, 2);
  $("dcf-kcp").textContent = pc(m.kcp, 2); $("dcf-cmpc").textContent = pc(m.cmpc, 2);
  $("dcf-lecture").innerHTML = r.lecture.map(x => `<p>${x}</p>`).join("");

  // Cellules calculées de la projection
  document.querySelectorAll("#dcf-contenu td[data-p]").forEach(td => {
    const p = m.projections[+td.dataset.i], k = td.dataset.p;
    td.textContent = k === "facteur" ? fr(p[k], 3) : md(["impot", "capex", "dbfr"].includes(k) ? -p[k] : p[k]);
  });

  // Pont VE → valeur par action
  const lp = (lib, v, cls = "") => `<tr class="${cls}"><th scope="row">${lib}</th><td>${v}</td></tr>`;
  $("dcf-pont").innerHTML =
    lp("Somme des FCFF actualisés (années 1 à 5)", md(m.somme_fcff_actualises) + " Md") +
    lp("+ Valeur terminale actualisée", md(m.vt_actualisee) + " Md") +
    lp("= Valeur d'entreprise (VE)", md(m.valeur_entreprise) + " Md", "total") +
    lp("− Dette financière (y c. dettes de location)", md(c.dette) + " Md") +
    lp("+ Trésorerie et placements", md(c.tresorerie) + " Md") +
    lp("− Intérêts minoritaires", md(c.minoritaires) + " Md") +
    lp("= Valeur des capitaux propres", md(m.valeur_capitaux_propres) + ` Md ${echapper(dev)}`, "total") +
    lp("÷ Nombre d'actions dilué", fr(c.actions_diluees / 1e6, 1) + " M" + (c.dilution > 1.001 ? ` <span class="note-a">(dilution ${pc(c.dilution - 1)})</span>` : "")) +
    (c.fx && Math.abs(c.fx - 1) > 1e-6 ? lp(`× Taux de change ${echapper(dev)} → ${echapper(devc)}`, fr(c.fx, 4)) : "") +
    lp("= Valeur par action", val(m.valeur_action), "total") +
    lp("Part de la valeur terminale dans la VE", pc(m.part_vt, 0));

  const choisie = { gordon: "Gordon-Shapiro", multiple: "Multiple de sortie", moyenne: "Moyenne" }[h.methode_vt];
  $("dcf-vt").innerHTML = `<tr><th></th><td><b>Gordon-Shapiro</b></td><td><b>Multiple de sortie</b></td></tr>
    <tr><th scope="row">Formule</th><td>FCFF × (1 + g) / (CMPC − g)</td><td>EBITDA an 5 × ${fr(h.multiple_sortie, 1)}</td></tr>
    <tr><th scope="row">Valeur terminale actualisée</th><td>${md(m.vt_gordon_actualisee)} Md</td><td>${md(m.vt_multiple_actualisee)} Md</td></tr>
    <tr><th scope="row">Valeur par action</th><td>${val(m.valeur_gordon)}</td><td>${val(m.valeur_multiple)}</td></tr>
    <tr><th scope="row">Ce que la méthode suppose</th><td>un multiple de ${m.multiple_implicite == null ? "—" : fr(m.multiple_implicite, 1)} × l'EBITDA</td>
      <td>une croissance à l'infini de ${pc(m.g_implicite)}</td></tr>
    <tr class="total"><th scope="row">Méthode retenue</th><td colspan="2">${choisie}</td></tr>`;
  $("dcf-pairs").innerHTML = c.pairs && c.pairs.length
    ? `Multiple par défaut : ${echapper(c.source_multiple)} (` + c.pairs.map(p => `${echapper(p.nom)} ${fr(p.ve_ebe, 1)}×`).join(", ") + `). Multiple actuel de ${echapper(r.nom)} : ${c.multiple_actuel == null ? "—" : fr(c.multiple_actuel, 1) + "×"}.`
    : `Multiple par défaut : ${echapper(c.source_multiple)}.`;

  // Scénarios
  const sc = { Pessimiste: "pessimiste", Central: "central", Optimiste: "optimiste" };
  r.scenarios.forEach(s => {
    const k = sc[s.nom];
    const cv = document.querySelector(`[data-s="${k}.v"]`), cp = document.querySelector(`[data-s="${k}.pot"]`);
    cv.textContent = val(s.valeur_action); cp.textContent = pctTxt(s.potentiel); cp.className = sens(s.potentiel);
    if (k === "central") document.querySelector('[data-s="central.p"]').textContent = pc(s.p, 0);
  });
  document.querySelector('[data-s="pond.v"]').textContent = val(r.valeur_ponderee);
  const pp = document.querySelector('[data-s="pond.pot"]'); pp.textContent = pctTxt(r.potentiel_pondere); pp.className = sens(r.potentiel_pondere);

  // Sensibilités
  const table = (titre, s, fmtCol) => `<div><p class="dcf-st">${titre}</p><table class="t-sens"><tr><th>CMPC ↓</th>${s.colonnes.map(x => `<th>${fmtCol(x)}</th>`).join("")}</tr>` +
    s.lignes.map((w, i) => `<tr><th>${pc(w, 1)}</th>` + s.valeurs[i].map((v, j) => {
      const pot = v == null ? null : v / c.cours - 1;
      const centre = i === 2 && j === Math.floor(s.colonnes.length / 2) ? " centre" : "";
      const fond = pot == null ? "" : `background: color-mix(in srgb, ${pot >= 0 ? "var(--eu)" : "var(--rouge)"} ${Math.min(Math.abs(pot) * 60, 38).toFixed(0)}%, transparent)`;
      return `<td class="${centre}" style="${fond}" title="${pot == null ? "" : "Potentiel " + pctTxt(pot)}">${v == null ? "—" : fr(v, 0)}</td>`;
    }).join("") + "</tr>").join("") + "</table></div>";
  $("dcf-sens").innerHTML = table(`Selon le CMPC et la croissance à l'infini (Gordon-Shapiro), en ${echapper(devc)}`, r.sensibilite_gordon, x => pc(x, 1)) +
    table(`Selon le CMPC et le multiple de sortie, en ${echapper(devc)}`, r.sensibilite_multiple, x => fr(x, 1) + "×");
}

async function exporterDCF() {
  const b = $("dcf-excel"), msg = $("dcf-msg");
  b.disabled = true; msg.textContent = "Création du classeur Excel…";
  try {
    const rep = await fetch(`/api/dcf/${encodeURIComponent(dcf.ticker)}/excel`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hypotheses: dcf.h }) });
    const r = await rep.json();
    if (r.erreur) throw new Error(r.erreur);
    if (window.pywebview && window.pywebview.api) {
      const chemin = await window.pywebview.api.enregistrer("xlsx", r.nom);
      msg.textContent = chemin ? "Enregistré : " + chemin.split("/").pop() : "";
    } else {
      window.location.href = `/api/export/xlsx/${encodeURIComponent(r.nom)}`;
      msg.textContent = "Téléchargement lancé.";
    }
  } catch (e) {
    msg.textContent = "L'export a échoué" + (e.message ? " : " + e.message : ".");
  } finally {
    b.disabled = false;
  }
}
