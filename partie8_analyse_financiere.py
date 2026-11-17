"""
PARTIE 8 — Analyse financière de l'entreprise (d'après le cours de M1 Finance)
=============================================================================

On quitte le cours de bourse pour étudier les COMPTES de l'entreprise
(compte de résultat, bilan, tableau des flux), sur 4 à 5 exercices.
Plan suivi (celui du cours) :

  Partie 2 du cours — Profitabilité et marges
      SIG (adaptés aux normes IFRS), CAF, ratios de marge, effet ciseau,
      point mort d'exploitation / financier / total, indice de sécurité, levier opérationnel
  Partie 3 du cours — Structure financière
      bilan fonctionnel (FR, BFR, TN), BFR normatif en jours, délais clients /
      fournisseurs / stocks, état de l'outil industriel, politique d'investissement
  Partie 4 du cours — Financement
      flux de trésorerie disponible (FTD), autofinancement, politique de dividendes,
      solvabilité (levier, DSCR, ICR, gearing), liquidité
  Partie 5 du cours — Rentabilité
      rentabilité économique (ROIC, ROCE), décomposition marge × rotation,
      ROE, effet de levier / effet de massue, répartition de la richesse

Les comptes viennent de Yahoo Finance, présentés selon les normes IFRS / US GAAP
(« par fonction ») : certains postes du Plan Comptable Général (valeur ajoutée,
production de l'exercice, charges de personnel) n'y figurent pas.

Lancer :  .venv/bin/python partie8_analyse_financiere.py MC.PA
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

TAUX_IS = 0.25          # impôt « normatif » du cours (taux théorique, pas l'impôt réel)
PRIME_RISQUE = 0.055    # prime de risque du marché actions, pour le coût des capitaux propres
TAUX_SANS_RISQUE = 0.03
JOURS = 360             # convention du cours pour les délais et le BFR normatif


# ---------------------------------------------------------------------------
# 1. Chargement des états financiers
# ---------------------------------------------------------------------------
def _ligne(df: pd.DataFrame, *noms) -> pd.Series:
    """Première ligne disponible parmi plusieurs libellés Yahoo (sinon NaN)."""
    for nom in noms:
        if nom in df.columns and df[nom].notna().any():
            return df[nom].astype(float)
    return pd.Series(np.nan, index=df.index)


def div(a, b):
    """Division qui renvoie NaN au lieu d'une erreur si b vaut 0 ou NaN."""
    with np.errstate(divide="ignore", invalid="ignore"):
        r = a / b
    if isinstance(r, pd.Series):
        return r.replace([np.inf, -np.inf], np.nan)
    return np.nan if (b == 0 or pd.isna(b) or pd.isna(a)) else r


def charger(ticker: str) -> dict:
    """Télécharge les 3 états financiers annuels, une ligne par exercice."""
    k = yf.Ticker(ticker)

    def prep(df):
        if df is None or df.empty:
            return pd.DataFrame()
        t = df.T.sort_index()                 # lignes = exercices, du plus ancien au plus récent
        t.index = pd.to_datetime(t.index).year
        return t[~t.index.duplicated(keep="last")]

    cr, bilan, flux = prep(k.income_stmt), prep(k.balance_sheet), prep(k.cashflow)
    try:
        info = k.info
    except Exception:
        info = {}
    try:
        dividendes = k.dividends
    except Exception:
        dividendes = pd.Series(dtype=float)
    return {"cr": cr, "bilan": bilan, "flux": flux, "info": info, "dividendes": dividendes}


# ---------------------------------------------------------------------------
# 2. Calculs
# ---------------------------------------------------------------------------
def analyser(ticker: str, beta: float = 1.0, cours: float = None) -> dict:
    d = charger(ticker)
    cr, bilan, flux, info = d["cr"], d["bilan"], d["flux"], d["info"]
    secteur = info.get("sector") or ""

    if cr.empty or bilan.empty:
        return {"applicable": False, "raison": "Yahoo Finance ne fournit pas les comptes de cette entreprise."}

    ca = _ligne(cr, "Total Revenue", "Operating Revenue")
    rex = _ligne(cr, "Operating Income", "EBIT")
    if secteur == "Financial Services" and (rex.isna().all() or _ligne(bilan, "Current Assets").isna().all()):
        return {"applicable": False, "raison": (
            "C'est un établissement financier (banque, assurance…). Ses comptes ne se lisent pas "
            "comme ceux d'une entreprise industrielle ou commerciale : pas de chiffre d'affaires ni de "
            "BFR au sens habituel, et la dette est sa « matière première ». Les ratios du cours "
            "(SIG, BFR, levier…) n'ont donc pas de sens ici.")}

    # On ne garde que les exercices où le chiffre d'affaires est connu
    annees = ca.dropna().index
    annees = [a for a in annees if a in bilan.index]
    if len(annees) < 2:
        return {"applicable": False, "raison": "Moins de deux exercices disponibles : analyse impossible."}
    cr, bilan = cr.loc[annees], bilan.loc[annees]
    flux = flux.reindex(annees)
    ca = ca.loc[annees]
    rex = rex.loc[annees]

    # ---------------- Partie 2 : SIG et profitabilité ----------------
    cout_ventes = _ligne(cr, "Cost Of Revenue", "Reconciled Cost Of Revenue")
    marge_brute = _ligne(cr, "Gross Profit")
    marge_brute = marge_brute.fillna(ca - cout_ventes)
    dotations = _ligne(cr, "Reconciled Depreciation").fillna(_ligne(flux, "Depreciation And Amortization"))
    ebe = _ligne(cr, "EBITDA", "Normalized EBITDA").fillna(rex + dotations)
    frais_fin = _ligne(cr, "Interest Expense", "Interest Expense Non Operating").abs()
    rcai = _ligne(cr, "Pretax Income")
    impot = _ligne(cr, "Tax Provision")
    rn = _ligne(cr, "Net Income", "Net Income Common Stockholders")

    sig = pd.DataFrame({
        "Chiffre d'affaires (CA)": ca,
        "Coût des ventes": cout_ventes,
        "Marge brute": marge_brute,
        "EBE (EBITDA)": ebe,
        "Dotations aux amortissements": dotations,
        "Résultat d'exploitation (REX)": rex,
        "Frais financiers": frais_fin,
        "Résultat courant avant impôt (RCAI)": rcai,
        "Impôt sur les sociétés": impot,
        "Résultat net": rn,
    })

    # CAF : flux d'exploitation avant variation du BFR.
    # Yahoo : « Change In Working Capital » = impact trésorerie = − ΔBFR
    ocf = _ligne(flux, "Operating Cash Flow")
    var_bfr = -_ligne(flux, "Change In Working Capital")
    caf = (ocf + var_bfr).fillna(rn + dotations)

    marges = pd.DataFrame({
        "Taux de marge brute": div(marge_brute, ca),
        "Marge d'EBE": div(ebe, ca),
        "Marge opérationnelle (REX / CA)": div(rex, ca),
        "Marge nette": div(rn, ca),
        "CAF / CA": div(caf, ca),
        "Croissance du CA": ca.pct_change(),
    })

    # Effet ciseau : évolution des produits (CA) vs des charges d'exploitation (CA − REX)
    charges = ca - rex
    n = len(annees) - 1
    tcam_ca = (ca.iloc[-1] / ca.iloc[0]) ** (1 / n) - 1
    tcam_charges = (charges.iloc[-1] / charges.iloc[0]) ** (1 / n) - 1 if charges.iloc[0] > 0 else np.nan

    # Point mort. Hypothèse (comptes par fonction) : coût des ventes = charges VARIABLES,
    # frais commerciaux, généraux, R&D, amortissements = charges FIXES.
    cf = marge_brute - rex                       # charges fixes d'exploitation
    m = div(marge_brute, ca)                     # taux de marge sur coûts variables
    kcp = TAUX_SANS_RISQUE + beta * PRIME_RISQUE  # coût des capitaux propres (CAPM)
    cp = _ligne(bilan, "Stockholders Equity", "Common Stock Equity")
    pm = div(cf, m)
    pm_fin = div(cf + frais_fin.fillna(0), m)
    pm_total = div(cf + frais_fin.fillna(0) + kcp * cp / (1 - TAUX_IS), m)
    point_mort = pd.DataFrame({
        "Charges fixes (estimées)": cf,
        "Taux de marge sur coûts variables": m,
        "Point mort d'exploitation": pm,
        "Indice de sécurité (CA / point mort)": div(ca, pm),
        "Levier opérationnel (MCV / REX)": div(marge_brute, rex),
        "Point mort financier": pm_fin,
        "Point mort total": pm_total,
        "Position CA / point mort total": div(ca, pm_total) - 1,
    })
    lo_observe = div(rex.pct_change(), ca.pct_change())   # élasticité réelle REX / CA

    # ---------------- Partie 3 : bilan fonctionnel, BFR, investissements ----------------
    actif_nc = _ligne(bilan, "Total Non Current Assets")
    actif_c = _ligne(bilan, "Current Assets")
    passif_c = _ligne(bilan, "Current Liabilities")
    dette_ct = _ligne(bilan, "Current Debt And Capital Lease Obligation", "Current Debt").fillna(0)
    tresorerie = _ligne(bilan, "Cash Cash Equivalents And Short Term Investments",
                        "Cash And Cash Equivalents")
    capitaux_propres_tot = _ligne(bilan, "Total Equity Gross Minority Interest", "Stockholders Equity")
    passif_nc = _ligne(bilan, "Total Non Current Liabilities Net Minority Interest")
    stocks = _ligne(bilan, "Inventory").fillna(0)
    clients = _ligne(bilan, "Accounts Receivable", "Receivables").fillna(0)
    fournisseurs = _ligne(bilan, "Accounts Payable", "Payables").fillna(0)

    ressources_stables = capitaux_propres_tot + passif_nc
    emplois_stables = actif_nc
    fr = ressources_stables - emplois_stables
    bfr = (actif_c - tresorerie) - (passif_c - dette_ct)
    tn = tresorerie - dette_ct              # identité : TN = FR − BFR
    bfr_exploitation = stocks + clients - fournisseurs

    fonctionnel = pd.DataFrame({
        "Emplois stables (actif immobilisé)": emplois_stables,
        "Ressources stables (CP + dettes > 1 an)": ressources_stables,
        "Fonds de roulement (FR)": fr,
        "Besoin en fonds de roulement (BFR)": bfr,
        "Trésorerie nette (TN = FR − BFR)": tn,
        "BFR d'exploitation (stocks + clients − fournisseurs)": bfr_exploitation,
    })
    ratios_bfr = pd.DataFrame({
        "BFR normatif (jours de CA)": div(bfr, ca) * JOURS,
        "Délai clients (jours)": div(clients, ca) * JOURS,
        "Rotation des stocks (jours)": div(stocks, cout_ventes) * JOURS,
        "Délai fournisseurs (jours)": div(fournisseurs, cout_ventes) * JOURS,
        "Ratio de FR (RS / ES)": div(ressources_stables, emplois_stables),
        "Taux de couverture du BFR (FR / BFR)": div(fr, bfr),
    })
    ratios_bfr["Cycle de conversion (jours)"] = (ratios_bfr["Délai clients (jours)"]
                                                 + ratios_bfr["Rotation des stocks (jours)"]
                                                 - ratios_bfr["Délai fournisseurs (jours)"])

    immo_brutes = _ligne(bilan, "Gross PPE")
    immo_nettes = _ligne(bilan, "Net PPE")
    amort_cumules = _ligne(bilan, "Accumulated Depreciation").abs()
    # Certaines années, Yahoo donne des immobilisations « brutes » égales aux nettes
    # (amortissements cumulés manquants) : ces années sont écartées des ratios concernés.
    brutes_fiables = (amort_cumules > 0) & (immo_brutes > immo_nettes * 1.01)
    immo_brutes = immo_brutes.where(brutes_fiables)
    immo_nettes = immo_nettes.where(brutes_fiables)
    amort_cumules = amort_cumules.where(brutes_fiables)
    capex = -_ligne(flux, "Capital Expenditure")                 # positif = investissement
    acquisitions = -_ligne(flux, "Net Business Purchase And Sale")
    goodwill = _ligne(bilan, "Goodwill And Other Intangible Assets", "Goodwill")
    total_actif = _ligne(bilan, "Total Assets")
    investissements = pd.DataFrame({
        "Investissements (CAPEX)": capex,
        "Acquisitions d'entreprises (croissance externe)": acquisitions,
        "Vétusté (immo. nettes / brutes)": div(immo_nettes, immo_brutes),
        "Taux d'amortissement (amort. cumulés / brutes)": div(amort_cumules, immo_brutes),
        "Taux de renouvellement (CAPEX / immo. brutes)": div(capex, immo_brutes),
        "Poids des invest. de croissance (CAPEX / dotations)": div(capex, dotations),
        "Taux d'investissement (CAPEX / CA)": div(capex, ca),
        "Intensité capitalistique (immo. brutes / CA)": div(immo_brutes, ca),
        "Part de l'immatériel (goodwill + incorporels / actif)": div(goodwill, total_actif),
    })

    # ---------------- Partie 4 : flux, financement, solvabilité, liquidité ----------------
    impot_paye = impot.clip(lower=0).fillna(0)
    ftd = ebe - impot_paye - var_bfr.fillna(0) - capex.fillna(0)       # formule du cours
    fcf_yahoo = _ligne(flux, "Free Cash Flow")
    div_verses = -_ligne(flux, "Cash Dividends Paid", "Common Stock Dividend Paid")
    autofin = caf - div_verses.fillna(0)
    remboursements = -_ligne(flux, "Repayment Of Debt", "Long Term Debt Payments")
    dette_fin = _ligne(bilan, "Total Debt")
    dfn = _ligne(bilan, "Net Debt").fillna(dette_fin - tresorerie)
    dfn = (dette_fin - tresorerie).where(dette_fin.notna(), dfn)       # DFN = dettes fin. − trésorerie

    flux_tab = pd.DataFrame({
        "EBE": ebe,
        "− Impôt": -impot_paye,
        "− Variation du BFR": -var_bfr,
        "− Investissements (CAPEX)": -capex,
        "= Flux de trésorerie disponible (FTD)": ftd,
        "FCF publié (flux d'exploitation − CAPEX)": fcf_yahoo,
        "Capacité d'autofinancement (CAF)": caf,
        "Dividendes versés": div_verses,
        "Autofinancement (CAF − dividendes)": autofin,
        "Taux d'autofinancement (autofin. / CAPEX)": div(autofin, capex),
        "FTD / REX (transformation en trésorerie)": div(ftd, rex),
    })

    # Dividendes par action (somme des versements de chaque année civile)
    dv = d["dividendes"]
    dpa = pd.Series(np.nan, index=annees, dtype=float)
    if dv is not None and len(dv):
        par_an = dv.groupby(dv.index.year).sum()
        dpa = par_an.reindex(annees)
    bpa = _ligne(cr, "Diluted EPS", "Basic EPS")
    dividendes_tab = pd.DataFrame({
        "Dividende par action (DPA)": dpa,
        "Bénéfice par action (BPA)": bpa,
        "Taux de distribution (DPA / BPA)": div(dpa, bpa),
        "Variation de la politique (ΔDPA / ΔBPA)": div(dpa.diff(), bpa.diff()),
    })
    rendement_div = div(dpa.dropna().iloc[-1], cours) if (cours and dpa.notna().any()) else np.nan

    solvabilite = pd.DataFrame({
        "Dettes financières": dette_fin,
        "Trésorerie": tresorerie,
        "Dette financière nette (DFN)": dfn,
        "Capitaux propres": cp,
        "Levier (DFN / EBE)": div(dfn, ebe),
        "Couverture du service de la dette (DSCR)": div(ftd, remboursements.fillna(0) + frais_fin.fillna(0)),
        "Couverture des frais financiers (ICR = REX / FF)": div(rex, frais_fin),
        "Gearing (DFN / CP)": div(dfn, cp),
        "Indépendance financière (CP / dettes fin.)": div(cp, dette_fin),
    })
    liquidite = pd.DataFrame({
        "Liquidité générale": div(actif_c, passif_c),
        "Liquidité réduite": div(actif_c - stocks, passif_c),
        "Liquidité immédiate": div(tresorerie, passif_c),
    })

    # ---------------- Partie 5 : rentabilité ----------------
    actif_eco = cp + dfn            # = capitaux investis (Damodaran : dette + CP − cash)
    rex_net = rex * (1 - TAUX_IS)
    re = div(rex_net, actif_eco)
    i_net = div(frais_fin * (1 - TAUX_IS), dfn).where(dfn > 0)
    bras = div(dfn, cp)
    roe = div(rn, cp.shift(1))
    # La formule de l'effet de levier n'a de sens que si l'entreprise a une dette nette (DFN > 0)
    # et un coût de la dette connu
    effet_levier = ((re - i_net) * bras).where((dfn > 0) & i_net.notna())
    rcp_theorique = re + effet_levier
    rentabilite = pd.DataFrame({
        "Actif économique (CP + DFN)": actif_eco,
        "Rentabilité économique Re (ROIC)": re,
        "ROCE (REX / capitaux investis)": div(rex, actif_eco),
        "Marge économique (REX × (1 − IS) / CA)": div(rex_net, ca),
        "Rotation de l'actif (CA / actif éco.)": div(ca, actif_eco),
        "Coût net de la dette i": i_net,
        "Bras de levier (DFN / CP)": bras,
        "Effet de levier (Re − i) × D/CP": effet_levier,
        "Rcp théorique = Re + (Re − i) × D/CP": rcp_theorique,
        "ROE observé (RN / CP n−1)": roe,
        "ROC marginal": div(rex.diff() * (1 - TAUX_IS), actif_eco.shift(1).diff()),
    })

    return {
        "applicable": True, "ticker": ticker, "devise": info.get("financialCurrency") or info.get("currency") or "",
        "info": info, "brut": {"cr": cr, "bilan": bilan, "flux": flux},   # pour la partie 9
        "secteur": secteur, "industrie": info.get("industry") or "", "annees": annees,
        "sig": sig, "marges": marges, "caf": caf, "tcam_ca": tcam_ca, "tcam_charges": tcam_charges,
        "point_mort": point_mort, "lo_observe": lo_observe, "kcp": kcp,
        "fonctionnel": fonctionnel, "ratios_bfr": ratios_bfr, "investissements": investissements,
        "flux": flux_tab, "dividendes": dividendes_tab, "rendement_div": rendement_div,
        "solvabilite": solvabilite, "liquidite": liquidite, "rentabilite": rentabilite,
    }


# ---------------------------------------------------------------------------
# 3. Lectures normatives (seuils du cours)
# ---------------------------------------------------------------------------
def note_equivalente(levier: float) -> str:
    """Équivalent indicatif de notation S&P d'après le ratio DFN / EBE (tableau du cours)."""
    if pd.isna(levier):
        return "—"
    if levier <= 0:
        return "AAA à AA (trésorerie supérieure aux dettes)"
    for seuil, note in [(1.0, "AA"), (2.0, "A"), (3.5, "BBB"), (4.5, "BB"), (6.0, "B")]:
        if levier <= seuil:
            return note
    return "CCC ou moins"


# ---------------------------------------------------------------------------
# 4. Graphiques
# ---------------------------------------------------------------------------
def _m(s):
    return s / 1e6   # en millions


def graphique_profitabilite(a: dict, fichier: str) -> None:
    sig, marges = a["sig"], a["marges"]
    x = [str(y) for y in a["annees"]]
    fig, (ax1, ax3) = plt.subplots(1, 2, figsize=(12, 4.6))

    ax1.bar(x, _m(sig["Chiffre d'affaires (CA)"]), color="#2A3A5C", label="Chiffre d'affaires")
    ax1.set_ylabel(f"M {a['devise']}")
    ax2 = ax1.twinx()
    for col, c in [("Marge d'EBE", "#6EA8FF"), ("Marge opérationnelle (REX / CA)", "#3BC48F"),
                   ("Marge nette", "#FF6B5A")]:
        ax2.plot(x, marges[col] * 100, marker="o", color=c, label=col)
    ax2.set_ylabel("%")
    ax2.axhline(0, color="#8D94A5", lw=0.5)
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left")
    ax1.set_title("Chiffre d'affaires (barres) et taux de marge (courbes)")

    ca = sig["Chiffre d'affaires (CA)"]
    charges = ca - sig["Résultat d'exploitation (REX)"]
    ax3.plot(x, ca / ca.iloc[0] * 100, marker="o", lw=2, label="Produits (CA)")
    ax3.plot(x, charges / charges.iloc[0] * 100, marker="o", lw=2, label="Charges d'exploitation")
    ax3.fill_between(x, ca / ca.iloc[0] * 100, charges / charges.iloc[0] * 100, alpha=0.15, color="#8D94A5")
    ax3.set_title("Effet ciseau : produits vs charges (base 100)")
    ax3.legend(fontsize=8)
    ax3.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_point_mort(a: dict, fichier: str) -> None:
    """Schéma du cours : CA, coûts fixes, coûts totaux ; point mort à l'intersection."""
    pm = a["point_mort"].iloc[-1]
    ca = a["sig"]["Chiffre d'affaires (CA)"].iloc[-1]
    cf, m = pm["Charges fixes (estimées)"], pm["Taux de marge sur coûts variables"]
    if pd.isna(cf) or pd.isna(m) or m <= 0:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "Point mort non calculable", ha="center")
        ax.axis("off")
    else:
        fig, ax = plt.subplots(figsize=(9, 4.6))
        xmax = max(ca, pm["Point mort d'exploitation"]) * 1.3
        x = np.linspace(0, xmax, 100)
        ax.plot(_m(x), _m(x), color="#ECE8DF", lw=2, label="Chiffre d'affaires")
        ax.plot(_m(x), _m(np.full_like(x, cf)), "--", color="#8D94A5", label="Charges fixes")
        ax.plot(_m(x), _m(cf + (1 - m) * x), color="#FF6B5A", lw=2, label="Coûts totaux (fixes + variables)")
        ax.axvline(_m(pm["Point mort d'exploitation"]), color="#6EA8FF", ls=":",
                   label=f"Point mort = {_m(pm['Point mort d\'exploitation']):,.0f} M".replace(",", " "))
        ax.axvline(_m(ca), color="#3BC48F", lw=2, label=f"CA réel {a['annees'][-1]}")
        ax.fill_between(_m(x), _m(x), _m(cf + (1 - m) * x), where=x > pm["Point mort d'exploitation"],
                        color="#3BC48F", alpha=0.12, label="Zone de bénéfice")
        ax.fill_between(_m(x), _m(x), _m(cf + (1 - m) * x), where=x < pm["Point mort d'exploitation"],
                        color="#FF6B5A", alpha=0.10, label="Zone de perte")
        ax.set_xlabel(f"Chiffre d'affaires (M {a['devise']})")
        ax.set_ylabel(f"M {a['devise']}")
        ax.set_title(f"Point mort d'exploitation — exercice {a['annees'][-1]}")
        ax.legend(fontsize=8, loc="upper left")
        ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_structure(a: dict, fichier: str) -> None:
    f, r = a["fonctionnel"], a["ratios_bfr"]
    x = np.arange(len(a["annees"]))
    lab = [str(y) for y in a["annees"]]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    w = 0.27
    ax1.bar(x - w, _m(f["Fonds de roulement (FR)"]), w, label="FR", color="#6EA8FF")
    ax1.bar(x, _m(f["Besoin en fonds de roulement (BFR)"]), w, label="BFR", color="#E9B866")
    ax1.bar(x + w, _m(f["Trésorerie nette (TN = FR − BFR)"]), w, label="TN", color="#3BC48F")
    ax1.axhline(0, color="#ECE8DF", lw=0.6)
    ax1.set_xticks(x, lab)
    ax1.set_ylabel(f"M {a['devise']}")
    ax1.set_title("Équilibre financier : FR − BFR = TN")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.3, axis="y")

    for col, c in [("Délai clients (jours)", "#6EA8FF"), ("Rotation des stocks (jours)", "#E9B866"),
                   ("Délai fournisseurs (jours)", "#9AA8C7"), ("BFR normatif (jours de CA)", "#ECE8DF")]:
        ax2.plot(lab, r[col], marker="o", label=col, color=c, lw=2 if "BFR" in col else 1.2)
    ax2.axhline(0, color="#8D94A5", lw=0.5)
    ax2.set_title("Délais et BFR en jours")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_flux(a: dict, fichier: str) -> None:
    fl = a["flux"]
    an = a["annees"][-1]
    d = fl.loc[an]
    etapes = [("EBE", d["EBE"]), ("Impôt", d["− Impôt"]), ("Var. BFR", d["− Variation du BFR"]),
              ("CAPEX", d["− Investissements (CAPEX)"])]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    cumul = 0
    for i, (nom, v) in enumerate(etapes):
        v = 0 if pd.isna(v) else v
        bas = cumul if i else 0
        ax1.bar(nom, _m(v), bottom=_m(bas), color="#3BC48F" if v >= 0 else "#FF6B5A")
        cumul = bas + v
    ftd = d["= Flux de trésorerie disponible (FTD)"]
    ax1.bar("FTD", _m(ftd), color="#6EA8FF")
    ax1.axhline(0, color="#ECE8DF", lw=0.6)
    ax1.set_title(f"De l'EBE au flux de trésorerie disponible ({an})")
    ax1.set_ylabel(f"M {a['devise']}")
    ax1.grid(alpha=0.3, axis="y")

    x = np.arange(len(a["annees"]))
    w = 0.27
    ax2.bar(x - w, _m(fl["Capacité d'autofinancement (CAF)"]), w, label="CAF", color="#6EA8FF")
    ax2.bar(x, _m(-fl["− Investissements (CAPEX)"]), w, label="Investissements", color="#E9B866")
    ax2.bar(x + w, _m(fl["Dividendes versés"]), w, label="Dividendes", color="#9AA8C7")
    ax2.set_xticks(x, [str(y) for y in a["annees"]])
    ax2.set_title("Ce que l'entreprise génère (CAF) et ce qu'elle en fait")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


def graphique_rentabilite(a: dict, fichier: str) -> None:
    r = a["rentabilite"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

    # Décomposition marge × rotation avec courbes d'iso-rentabilité (style Vernimmen, vu en cours)
    rot = np.linspace(0.05, 4, 300)
    for niveau in [0.05, 0.10, 0.15, 0.25, 0.40]:
        ax1.plot(rot, niveau / rot * 100, color="#8D94A5", lw=0.7, ls="--")
        ax1.text(3.9, niveau / 3.9 * 100, f"Re {niveau:.0%}", fontsize=7, color="#8D94A5", va="bottom", ha="right")
    marge = r["Marge économique (REX × (1 − IS) / CA)"] * 100
    rotation = r["Rotation de l'actif (CA / actif éco.)"]
    ax1.plot(rotation, marge, color="#6EA8FF", lw=1)
    ax1.scatter(rotation, marge, color="#6EA8FF", zorder=3)
    for an, xx, yy in zip(a["annees"], rotation, marge):
        if pd.notna(xx) and pd.notna(yy):
            ax1.annotate(str(an), (xx, yy), fontsize=8, xytext=(4, 4), textcoords="offset points")
    ymax = max(40, (marge.max() if marge.notna().any() else 0) * 1.3)
    ax1.set_ylim(min(0, marge.min() * 1.2 if marge.notna().any() else 0), ymax)
    xmax = max(4, (rotation.max() if rotation.notna().any() else 0) * 1.2)
    ax1.set_xlim(0, xmax)
    ax1.set_xlabel("Rotation de l'actif (CA / actif économique)")
    ax1.set_ylabel("Marge économique après IS (%)")
    ax1.set_title("Rentabilité économique = marge × rotation")
    ax1.grid(alpha=0.3)

    x = np.arange(len(a["annees"]))
    w = 0.27
    ax2.bar(x - w, r["Rentabilité économique Re (ROIC)"] * 100, w, label="Re (ROIC)", color="#6EA8FF")
    ax2.bar(x, r["Coût net de la dette i"] * 100, w, label="Coût de la dette i", color="#E9B866")
    ax2.bar(x + w, r["ROE observé (RN / CP n−1)"] * 100, w, label="ROE", color="#3BC48F")
    ax2.axhline(0, color="#ECE8DF", lw=0.6)
    ax2.set_xticks(x, [str(y) for y in a["annees"]])
    ax2.set_ylabel("%")
    ax2.set_title("Effet de levier : Re > i  →  ROE > Re")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(fichier, dpi=120)
    plt.close(fig)


GRAPHIQUES = {
    "profitabilite": graphique_profitabilite,
    "point_mort": graphique_point_mort,
    "structure": graphique_structure,
    "flux": graphique_flux,
    "rentabilite": graphique_rentabilite,
}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "MC.PA"
    a = analyser(ticker)
    if not a["applicable"]:
        sys.exit(a["raison"])
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 10)

    def montrer(titre, df, pourcent=False, millions=False):
        print(f"\n--- {titre} ---")
        t = df.T
        if millions:
            t = (t / 1e6).round(0)
        elif pourcent:
            t = (t * 100).round(1)
        else:
            t = t.round(2)
        print(t.to_string())

    print(f"\n=== Partie 8 : analyse financière de {ticker} (en millions {a['devise']}) ===")
    montrer("SIG", a["sig"], millions=True)
    montrer("Marges (%)", a["marges"], pourcent=True)
    print(f"TCAM produits {a['tcam_ca']:.1%} / charges {a['tcam_charges']:.1%}")
    montrer("Point mort", a["point_mort"])
    montrer("Bilan fonctionnel", a["fonctionnel"], millions=True)
    montrer("BFR et délais", a["ratios_bfr"])
    montrer("Investissements", a["investissements"])
    montrer("Flux", a["flux"])
    montrer("Dividendes", a["dividendes"])
    montrer("Solvabilité", a["solvabilite"])
    montrer("Liquidité", a["liquidite"])
    montrer("Rentabilité", a["rentabilite"])
    for nom, f in GRAPHIQUES.items():
        f(a, f"{ticker}_p8_{nom}.png")
    print("\nGraphiques créés.")
