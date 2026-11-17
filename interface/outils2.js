// =====================================================================
// Journal d'investissement, Secteurs, ETF, dividendes du portefeuille
// (chargé après pro.js et dcf.js : utilise $, fr, pctTxt, sens, echapper, courant, allerMode, lancerAnalyse, courbes…)
// =====================================================================
const pcA = (x, d = 1) => x == null ? "—" : (fr(x * 100, d) + " %").replace("-", "−");
const nbA = (x, d = 1) => x == null ? "—" : fr(x, d).replace("-", "−");

window.ouvertureOutils2 = function (m) {
  if (m === "secteurs") chargerSecteurs();
  if (m === "etf") { chargerPopulaires(); if (!$("etf-contenu").innerHTML) chargerETF(); }
  if (m === "suivi") afficherJournal();
};

// ---------------------------------------------------------------------
// 1. JOURNAL D'INVESTISSEMENT
// ---------------------------------------------------------------------
let journal = {};
async function lireJournal() { try { journal = await (await fetch("/api/journal")).json(); } catch { journal = {}; } return journal; }
const tickerCourant = () => courant && courant.type === "simple" && courant.a ? courant.a : null;

window.majRappelJournal = async function () {
  const a = tickerCourant(), z = $("rappel-journal");
  if (!a) { z.hidden = true; return; }
  await lireJournal();
  const j = journal[a.ticker];
  // (vérifié après le chargement : l'utilisateur a pu quitter le rapport entre-temps)
  if (!j || !$("outils").classList.contains("ouvert")) { z.hidden = true; return; }
  const prix = [j.achat != null ? `achat visé ${fr(j.achat, 2)}` : "", j.vente != null ? `vente visée ${fr(j.vente, 2)}` : ""].filter(Boolean).join(" · ");
  z.innerHTML = `<b>📝 Ta note du ${new Date(j.maj).toLocaleDateString("fr-FR")}</b> — « ${echapper((j.these || "").slice(0, 220))}${(j.these || "").length > 220 ? "…" : ""} »
    ${prix ? `<span class="note-a"> · ${prix}</span>` : ""} <button class="lien" id="rappel-ouvrir">Relire et mettre à jour</button>`;
  z.hidden = false;
  $("rappel-ouvrir").addEventListener("click", ouvrirJournal);
};

async function ouvrirJournal() {
  const a = tickerCourant(); if (!a) return;
  await lireJournal();
  const j = journal[a.ticker] || {};
  $("j-titre").textContent = `Journal · ${a.nom}`;
  $("j-these").value = j.these || ""; $("j-risque").value = j.risque || "";
  $("j-achat").value = j.achat ?? ""; $("j-vente").value = j.vente ?? "";
  $("j-msg").textContent = j.maj ? `Dernière mise à jour : ${new Date(j.maj).toLocaleDateString("fr-FR")}` : "";
  $("tiroir-journal").hidden = false;
  requestAnimationFrame(() => $("tiroir-journal").classList.add("ouvert"));
  $("j-these").focus();
}
function fermerJournal() {
  $("tiroir-journal").classList.remove("ouvert");
  setTimeout(() => { $("tiroir-journal").hidden = true; }, 220);
  $("ouvrir-journal").focus();
}
$("ouvrir-journal").addEventListener("click", ouvrirJournal);
$("fermer-journal").addEventListener("click", fermerJournal);
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("tiroir-journal").hidden) fermerJournal(); });
$("j-enregistrer").addEventListener("click", async () => {
  const a = tickerCourant(); if (!a) return;
  const corps = { nom: a.nom, these: $("j-these").value, risque: $("j-risque").value, achat: $("j-achat").value, vente: $("j-vente").value };
  await fetch(`/api/journal/${encodeURIComponent(a.ticker)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corps) });
  $("j-msg").textContent = "Enregistré.";
  majRappelJournal();
});

async function afficherJournal() {
  await lireJournal();
  const e = Object.entries(journal);
  if (!e.length) return;
  $("liste-journal").innerHTML = `<table class="t-pf"><thead><tr><th>Action</th><th>Ma thèse</th><th>Achat visé</th><th>Vente visée</th><th>Mise à jour</th></tr></thead><tbody>` +
    e.sort((x, y) => y[1].maj.localeCompare(x[1].maj)).map(([t, j]) => `<tr class="cliquable" data-t="${echapper(t)}" data-n="${echapper(j.nom)}">
      <td><b>${echapper(j.nom)}</b> <span class="note-a">${echapper(t)}</span></td><td>${echapper((j.these || "—").slice(0, 120))}${(j.these || "").length > 120 ? "…" : ""}</td>
      <td>${j.achat != null ? fr(j.achat, 2) : "—"}</td><td>${j.vente != null ? fr(j.vente, 2) : "—"}</td><td>${new Date(j.maj).toLocaleDateString("fr-FR")}</td></tr>`).join("") + "</tbody></table>";
}
$("liste-journal").addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-t]"); if (!tr) return;
  allerMode("simple"); lancerAnalyse({ ticker: tr.dataset.t, nom: tr.dataset.n, place: "" }, false);
});

// ---------------------------------------------------------------------
// 2. SECTEURS
// ---------------------------------------------------------------------
let secteurChoisi = null, secteurUnivers = "", requeteSect = 0;
async function chargerSecteurs() {
  if (secteurChoisi) return chargerSecteur(secteurChoisi);
  $("sect-titre").textContent = "Secteurs";
  $("sect-contenu").innerHTML = `<p class="note-a">Chargement…</p>`;
  const r = await (await fetch("/api/secteurs")).json();
  if (r.erreur || !r.secteurs) { $("sect-contenu").innerHTML = `<p class="note-a">La base sectorielle n'est pas encore prête (elle se construit au premier lancement).</p>`; return; }
  const m = r.marche;
  $("sect-contenu").innerHTML = `<table class="t-dcf t-sect"><thead><tr><th>Secteur</th><th>Entreprises</th><th>Capitalisation</th><th>Perf. 1 an (médiane)</th>
      <th>PER médian</th><th>VE / EBITDA</th><th>Marge nette</th><th>ROE</th><th>Rendement</th></tr></thead><tbody>` +
    r.secteurs.map(s => `<tr class="cliquable" data-s="${echapper(s.secteur)}" tabindex="0" role="button"><th scope="row">${echapper(s.secteur)}</th><td>${s.nb}</td>
      <td>${fr(s.capi / 1e12, 2)} T€</td><td class="${sens(s.var_1an)}">${pctTxt(s.var_1an)}</td><td>${nbA(s.per)}</td><td>${nbA(s.ve_ebe)}</td>
      <td>${pcA(s.marge_nette)}</td><td>${pcA(s.roe)}</td><td>${pcA(s.rdt_div)}</td></tr>`).join("") +
    `<tr class="total"><th scope="row">Ensemble (${r.nb})</th><td></td><td></td><td>${pctTxt(m.var_1an)}</td><td>${nbA(m.per)}</td><td>${nbA(m.ve_ebe)}</td>
      <td>${pcA(m.marge_nette)}</td><td>${pcA(m.roe)}</td><td>${pcA(m.rdt_div)}</td></tr></tbody></table>
    <p class="note-a">Clique sur un secteur pour son tableau de bord. Médianes : la valeur du milieu, moins sensible aux cas extrêmes qu'une moyenne.</p>`;
}
$("sect-contenu").addEventListener("click", (e) => {
  const s = e.target.closest("[data-s]"); if (s) return chargerSecteur(s.dataset.s);
  const t = e.target.closest("[data-t]"); if (t) { allerMode("simple"); return lancerAnalyse({ ticker: t.dataset.t, nom: t.dataset.n, place: "" }, false); }
  const u = e.target.closest("[data-u]"); if (u) { secteurUnivers = u.dataset.u; return chargerSecteur(secteurChoisi); }
  if (e.target.closest("#sect-retour")) { secteurChoisi = null; chargerSecteurs(); }
});
$("sect-contenu").addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("[data-s]")) chargerSecteur(e.target.dataset.s); });

async function chargerSecteur(nom) {
  secteurChoisi = nom;
  if (mode !== "secteurs") allerMode("secteurs");
  $("sect-titre").textContent = `Secteur · ${nom}`;
  $("sect-contenu").innerHTML = `<p class="note-a">Chargement…</p>`;
  const n = ++requeteSect;
  const r = await (await fetch(`/api/secteurs/detail?nom=${encodeURIComponent(nom)}&univers=${secteurUnivers}`)).json();
  if (n !== requeteSect) return;
  if (r.erreur) { $("sect-contenu").innerHTML = `<p class="note-a">${echapper(r.erreur)}</p><button class="lien" id="sect-retour">← Tous les secteurs</button>`; return; }
  const md = r.medianes, mk = r.marche;
  const tuile = (l, v, m, pct) => `<div><div class="l">${l}</div><div class="v">${pct ? pcA(v) : nbA(v)}</div><div class="note-a">ensemble : ${pct ? pcA(m) : nbA(m)}</div></div>`;
  const fmt = (c, v) => c.pourcentage ? pcA(v) : nbA(v);
  const ligneCl = (c, x) => `<li><a href="#" data-t="${echapper(x.ticker)}" data-n="${echapper(x.nom)}">${echapper(x.nom)}</a> <b>${fmt(c, x.valeur)}</b></li>`;
  $("sect-contenu").innerHTML = `<p><button class="lien" id="sect-retour">← Tous les secteurs</button>
      <span class="segment sect-univ">${[["", "Tous"], ["eu", "Europe"], ["us", "S&P 500"]].map(([u, t]) => `<button data-u="${u}" class="${secteurUnivers === u ? "on" : ""}">${t}</button>`).join("")}</span></p>
    <div class="kpis-s">${tuile("Perf. 1 an (médiane)", md.var_1an, mk.var_1an, true)}${tuile("PER médian", md.per, mk.per)}${tuile("VE / EBITDA", md.ve_ebe, mk.ve_ebe)}
      ${tuile("Marge nette", md.marge_nette, mk.marge_nette, true)}${tuile("ROE", md.roe, mk.roe, true)}${tuile("Croissance du CA", md.croissance_ca, mk.croissance_ca, true)}
      ${tuile("Rendement", md.rdt_div, mk.rdt_div, true)}${tuile("Dette nette / EBITDA", md.levier, mk.levier)}</div>
    <div class="lecture-s">${r.lecture.map(x => `<p>${x}</p>`).join("")}</div>
    <h3>Les meilleures et les moins bonnes, critère par critère</h3>
    <div class="sect-classements">${r.classements.map(c => `<div class="carte-mini"><b>${c.libelle}</b>
      <ul class="cl-haut">${c.meilleurs.map(x => ligneCl(c, x)).join("")}</ul>
      ${c.moins_bons.length ? `<ul class="cl-bas">${c.moins_bons.map(x => ligneCl(c, x)).join("")}</ul>` : ""}</div>`).join("")}</div>
    <p class="note-a">PER, VE/EBITDA et endettement : les plus bas sont en tête (moins chers, moins endettés). Industries principales :
      ${r.industries.map(([i, n]) => `${echapper(i)} (${n})`).join(", ")}.</p>
    <h3>Les ${r.nb} entreprises du secteur</h3>
    <div class="dcf-defile"><table class="t-dcf t-sect"><thead><tr><th>Entreprise</th><th>Place</th><th>Capi.</th><th>1 an</th><th>PER</th><th>VE/EBITDA</th>
      <th>Marge nette</th><th>ROE</th><th>Croiss. CA</th><th>Rdt</th><th>Dette/EBITDA</th><th>Potentiel analystes</th></tr></thead><tbody>` +
    r.entreprises.slice(0, 80).map(a => `<tr class="cliquable" data-t="${echapper(a.ticker)}" data-n="${echapper(a.nom)}"><th scope="row">${echapper(a.nom)}</th>
      <td>${echapper(a.place || "")}</td><td>${a.capi_eur ? fr(a.capi_eur / 1e9, 1) + " Md€" : "—"}</td><td class="${sens(a.var_1an)}">${pctTxt(a.var_1an)}</td>
      <td>${nbA(a.per)}</td><td>${nbA(a.ve_ebe)}</td><td>${pcA(a.marge_nette)}</td><td>${pcA(a.roe)}</td><td>${pcA(a.croissance_ca)}</td>
      <td>${pcA(a.rdt_div)}</td><td>${nbA(a.levier)}</td><td class="${sens(a.potentiel_analystes)}">${pctTxt(a.potentiel_analystes)}</td></tr>`).join("") +
    `</tbody></table></div>${r.nb > 80 ? `<p class="note-a">Les 80 plus grandes entreprises sur ${r.nb}.</p>` : ""}`;
}
window.ouvrirSecteur = (nom) => { secteurChoisi = null; chargerSecteur(nom); };
window.addEventListener("message", (e) => { const d = e.data || {}; if (d.type === "secteur" && d.nom) ouvrirSecteur(d.nom); });

// ---------------------------------------------------------------------
// 3. ETF
// ---------------------------------------------------------------------
async function chargerPopulaires() {
  if ($("etf-populaires").innerHTML) return;
  const l = await (await fetch("/api/etf/populaires")).json();
  $("etf-populaires").innerHTML = "<span class='note-a'>Populaires :</span> " + l.map(x => `<button class="chip" data-e="${x.ticker}" title="${echapper(x.nom)}">${echapper(x.ticker)}</button>`).join("");
}
$("etf-populaires").addEventListener("click", (e) => {
  const b = e.target.closest("[data-e]"); if (!b) return;
  if ($("etf-a").value && $("etf-contenu").innerHTML && !$("etf-b").value && b.dataset.e !== $("etf-a").value.toUpperCase()) $("etf-b").value = b.dataset.e;
  else { $("etf-a").value = b.dataset.e; $("etf-b").value = ""; }
  chargerETF();
});
$("etf-go").addEventListener("click", chargerETF);
["etf-a", "etf-b"].forEach(id => $(id).addEventListener("keydown", e => { if (e.key === "Enter") chargerETF(); }));

let requeteETF = 0;
async function chargerETF() {
  const a = $("etf-a").value.trim().toUpperCase(), b = $("etf-b").value.trim().toUpperCase();
  if (!a) return;
  const n = ++requeteETF;
  $("etf-contenu").innerHTML = `<p class="note-a" role="status">Chargement de ${echapper(a)}${b ? " et " + echapper(b) : ""}…</p>`;
  const r = await (await fetch(`/api/etf/${encodeURIComponent(a)}${b ? "?comparer=" + encodeURIComponent(b) : ""}`)).json();
  if (n !== requeteETF) return;                  // une demande plus récente est en cours
  if (r.erreur) { $("etf-contenu").innerHTML = `<p class="note-a">${echapper(r.erreur)}</p>`; return; }
  const etfs = b ? [r.a, r.b] : [r];
  const couleurs = ["var(--or)", "#6EA8FF"];
  const fiche = (x, i) => `<div class="etf-fiche" style="--c:${couleurs[i]}">
      <h3>${echapper(x.ticker)} <span class="note-a">${echapper(x.devise)}</span></h3><p class="etf-nom">${echapper(x.nom)}</p>
      <table class="t-pont"><tr><th>Frais annuels (TER)</th><td>${x.ter != null ? pcA(x.ter, 2) : "non communiqué"}</td></tr>
        ${x.encours ? `<tr><th>Encours</th><td>${fr(x.encours / 1e9, 1)} Md</td></tr>` : ""}
        ${Object.entries(x.perf).map(([k, v]) => `<tr><th>Rendement annuel sur ${k}</th><td class="${sens(v)}">${pctTxt(v)}</td></tr>`).join("")}
        <tr><th>Volatilité</th><td>${pcA(x.volatilite)}</td></tr><tr><th>Perte maximale</th><td class="baisse">${pcA(x.perte_max)}</td></tr>
        ${x.concentration != null ? `<tr><th>Poids des 10 premières lignes</th><td>${pcA(x.concentration)}</td></tr>` : ""}</table>
      <p><b>PEA :</b> ${echapper(x.pea)}</p><p><b>Réplication :</b> ${echapper(x.replication)}</p><p><b>Dividendes :</b> ${echapper(x.dividendes)}</p>
      ${x.cout_frais ? `<p class="note-a">Coût des frais : sur 10 000 € placés 20 ans à 7 % par an, ils représentent environ <b>${fr(x.cout_frais.cout, 0)} €</b>
        (${fr(x.cout_frais.avec_frais, 0)} € au lieu de ${fr(x.cout_frais.sans_frais, 0)} €).</p>` : ""}
      ${x.secteurs.length ? `<p><b>Secteurs</b></p>${x.secteurs.slice(0, 8).map(s => `<div class="barre-s"><span>${echapper(s.secteur)}</span><i style="width:${(s.poids * 100 * 2.2).toFixed(0)}px"></i><b>${pcA(s.poids)}</b></div>`).join("")}` : ""}
      ${x.lignes.length ? `<p><b>10 premières lignes</b></p><ul class="mini-liste">${x.lignes.map(l => `<li><span>${echapper(l.nom)}</span><span>${pcA(l.poids)}</span></li>`).join("")}</ul>`
        : `<p class="note-a">Composition détaillée non fournie par Yahoo Finance pour cet ETF.</p>`}</div>`;
  // Courbe en base 100 sur les dates communes
  const dates = etfs.map(x => new Map(x.serie.map(p => [p[0], p[1]])));
  const communes = etfs[0].serie.map(p => p[0]).filter(d => dates.every(m => m.has(d)));
  const series = {};
  etfs.forEach((x, i) => { const m = dates[i], d0 = m.get(communes[0]); series[x.ticker] = communes.map(d => [d, m.get(d) / d0 * 100]); });
  $("etf-contenu").innerHTML = (b && r.lecture.length ? `<div class="lecture-s">${r.lecture.map(x => `<p>${x}</p>`).join("")}</div>` : "") +
    `<h3>Évolution (base 100${communes.length ? " le " + new Date(communes[0]).toLocaleDateString("fr-FR") : ""}, dividendes réinvestis)</h3>
    <div class="legende">${etfs.map((x, i) => `<span style="--c:${couleurs[i]}">${echapper(x.ticker)}</span>`).join("")}</div>
    <svg class="svg-courbes" id="etf-svg" viewBox="0 0 1000 300" preserveAspectRatio="none"></svg>
    <div class="etf-grille">${etfs.map(fiche).join("")}</div>
    <p class="note-a">Performances passées, en devise de cotation : elles ne préjugent pas des performances futures. L'éligibilité au PEA se
      vérifie dans le document d'informations clés (DIC) du fonds.</p>`;
  if (communes.length > 2) courbes($("etf-svg"), series, couleurs, null, { unite: "", decimales: 0, depuisZero: false, repere: 100 });
}

// ---------------------------------------------------------------------
// 4. DIVIDENDES DU PORTEFEUILLE
// ---------------------------------------------------------------------
$("voir-div-pf").addEventListener("click", async () => {
  const z = $("div-pf");
  z.innerHTML = `<p class="note-a" role="status">Calcul des dividendes…</p>`;
  const r = await (await fetch("/api/dividendes/portefeuille")).json();
  if (r.erreur || !r.lignes) { z.innerHTML = `<p class="note-a">${echapper(r.erreur || "Calcul impossible.")}</p>`; return; }
  if (!r.lignes.length) { z.innerHTML = `<p class="note-a">Indique des montants dans le portefeuille pour estimer tes dividendes.</p>`; return; }
  const mx = Math.max(...r.par_mois.map(m => m.montant), 1);
  z.innerHTML = `<div class="kpis-s"><div><div class="l">Dividendes par an (estimation)</div><div class="v">${fr(r.total, 0)} €</div></div>
      <div><div class="l">Après flat tax de 30 %</div><div class="v">${fr(r.apres_impot, 0)} €</div></div>
      <div><div class="l">Rendement du portefeuille</div><div class="v">${pcA(r.rendement, 2)}</div></div></div>
    <div class="cal-div">${r.par_mois.map(m => `<div><i style="height:${(m.montant / mx * 90).toFixed(0)}px" title="${fr(m.montant, 0)} €"></i><span>${m.mois}</span><b>${m.montant >= 1 ? fr(m.montant, 0) : ""}</b></div>`).join("")}</div>
    <table class="t-pf"><thead><tr><th>Action</th><th>Montant</th><th>Rendement</th><th>Dividendes / an</th><th>Mois de versement</th></tr></thead><tbody>
    ${r.lignes.map(l => `<tr><td>${echapper(l.nom)}</td><td>${fr(l.montant, 0)} €</td><td>${pcA(l.rendement, 2)}</td><td>${fr(l.revenu, 0)} €</td>
      <td>${l.mois.map(m => ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."][m - 1]).join(", ") || "—"}</td></tr>`).join("")}</tbody></table>
    <p class="note-a">Estimation à partir des dividendes des 12 derniers mois et des mois habituels de détachement. Dans un PEA, les dividendes
      réinvestis ne sont pas imposés tant que tu ne retires pas d'argent (seulement 17,2 % de prélèvements sociaux au retrait après 5 ans).</p>`;
});

lireJournal();

// Le rappel du journal n'est visible qu'avec un rapport d'action affiché
new MutationObserver(() => {
  if (!$("outils").classList.contains("ouvert")) $("rappel-journal").hidden = true;
  else majRappelJournal();
}).observe($("outils"), { attributes: true, attributeFilter: ["class"] });
