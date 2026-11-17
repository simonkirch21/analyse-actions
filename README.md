# Analyse Actions

Application Mac d'analyse boursière pour débutants et étudiants en finance, écrite en Python.
On tape le nom d'une action (Euronext ou S&P 500) et on obtient un rapport complet et expliqué :
performance, CAPM, risque (VaR), analyse technique, Monte Carlo, options, analyse financière des
comptes, valorisation (DCF, multiples), scores d'Altman et de Piotroski. S'y ajoutent un tableau de
bord des marchés, un mode portefeuille (Markowitz), des portefeuilles fictifs, un simulateur
d'investissement mensuel, un filtre d'actions, la macroéconomie, la courbe des taux et les options cotées.

> **Avertissement.** Outil pédagogique réalisé dans le cadre d'un Master 1 Finance. Les données
> proviennent de sources publiques gratuites (Yahoo Finance, FRED, BCE…) et peuvent être inexactes
> ou retardées. Rien dans cette application ne constitue un conseil en investissement.

## Installation

**Le plus simple (Mac) :** télécharge `Analyse-Actions.dmg` dans la page
[Releases](https://github.com/simonkirch21/analyse-actions/releases/latest) du dépôt, ouvre-le et glisse l'application dans le dossier Applications.
Au premier lancement : clic droit sur l'application → Ouvrir (elle n'est pas signée par Apple).

**Depuis le code (Python 3.11 ou plus récent) :**

```bash
git clone https://github.com/simonkirch21/analyse-actions.git
cd analyse-actions
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py              # ouvre la fenêtre de l'application
.venv/bin/python app.py --serveur    # ou dans le navigateur : http://localhost:5055
```

## Application Mac

L'application **Analyse Actions** se trouve dans `~/Applications` (dossier Applications
de ton compte) : ouvre-la depuis le Launchpad, Spotlight (Cmd+Espace) ou le Finder.

- **Accueil = tableau de bord des marchés** : 9 indices (CAC 40, Euro Stoxx 50, DAX, FTSE 100, S&P 500,
  Nasdaq, Dow Jones, Nikkei, VIX) et 4 repères (pétrole, or, euro/dollar, taux US 10 ans), avec un grand
  graphique interactif (1 mois à tout l'historique) ; valeurs phares ; plus fortes hausses / baisses du
  jour et actions les plus volatiles (S&P 500 + 100 valeurs d'Euronext) ; actualité économique
  (Le Monde, France 24, La Tribune, Investing). Bouton « + » sur chaque action pour l'ajouter au portefeuille.
- Chaque rapport commence par les **actualités récentes de l'entreprise** (presse française et internationale).
- Tape le début d'un nom ou d'un ticker : les suggestions s'affichent
  (≈ 2 100 actions : toutes les places Euronext et le S&P 500).
- ↑ ↓ pour choisir, Entrée pour lancer l'analyse ; filtres Tous / Euronext / S&P 500 ; choix de la période.
- Raccourci Cmd+K pour revenir à la recherche.
- **Comparer deux actions** : bouton en haut de la fenêtre, puis deux champs de recherche ; tous les
  indicateurs côte à côte, graphiques superposés et conclusion automatique (analyse comparative du cours).
- **Mon portefeuille** : troisième bouton en haut. Ajoute des actions avec la recherche ou avec le
  bouton « + Portefeuille » d'un rapport, indique les montants, puis « Analyser le portefeuille » :
  performance en euros (devises converties), comparaison au MSCI World, corrélations, gain de
  diversification, contribution de chaque action au risque, frontière efficiente de Markowitz.
  Le portefeuille est enregistré dans `~/Library/Application Support/Analyse Actions/utilisateur/`.
- **Suivi & agenda** : liste de suivi (bouton « ☆ Suivre » d'un rapport) avec alertes (baisse du jour,
  plancher, plafond) envoyées en notification macOS toutes les 15 minutes tant que l'app est ouverte ;
  agenda des résultats et dividendes des actions suivies et du portefeuille.
- **Simulateur** : investissement mensuel sur un indice ou une action depuis une date, comparé à
  « tout investir au début » et à un livret ; rendement annuel (TRI), pire moment, graphique.
- **Filtre d'actions** : ~1 350 entreprises (S&P 500 + Euronext) filtrées par PER, rendement, ROE, marge,
  dette nette / EBE, croissance, secteur ; profils prêts à l'emploi ; comparer deux résultats en un clic.
- **Concurrents** : chaque rapport propose 4 entreprises comparables (même industrie, taille proche),
  avec un bouton « Comparer ».
- **Portefeuille** : date et prix d'achat par ligne → suivi réel (plus-values, dividendes reçus, impôt
  estimé en compte-titres ou PEA) ; test du rééquilibrage annuel.
- **Économie** : inflation, taux directeurs (BCE, Fed), taux d'emprunt à 10 ans (France, Allemagne,
  États-Unis), chômage, croissance du PIB, avec historiques et lecture automatique (taux réel, spread…).
- **Bourse fictive** : portefeuilles avec un capital virtuel, ordres d'achat et de vente au cours réel,
  frais de courtage, dividendes versés automatiquement, comparaison au CAC 40 et au MSCI World,
  classement des portefeuilles. Un portefeuille peut démarrer dans le passé pour tester une stratégie.
- **Barre de commandes (⌘K)** : `LVMH`, `G LVMH` (graphique), `COMP MC.PA KER.PA`, `CARTE SP`, `ECO`, `TAUX`,
  `CAL`, `FX`, `OPT AAPL`, `PF`, `SUIVRE AAPL`, `ACHAT 10 AIR.PA`, `VENTE 5 AIR.PA`, `SIM ^FCHI`, `ACCUEIL`…
- **Graphique interactif** : bougies, ligne ou zone, volumes, moyennes mobiles 20/50/200, Bollinger, RSI,
  zoom à la molette, déplacement à la souris, comparaison de jusqu'à 5 actions en %.
- **Carte du marché** : CAC 40, Euronext 100 ou S&P 500 ; taille = capitalisation, couleur = variation du jour.
- **Devises & matières premières** : change, pétrole, gaz, métaux, céréales, café, cryptomonnaies.
- **Économie** : + courbe des taux (États-Unis, zone euro) avec détection d'inversion, et calendrier économique
  (événements de la semaine et de la suivante, résultats d'entreprises).
- **Options cotées** (actions américaines) : chaîne complète, volatilité implicite, sourire de volatilité,
  comparaison au prix Black-Scholes.
- **Rapports** : nouvelle section « Qui détient l'action ? » (dirigeants, fonds, transactions des dirigeants).
- **Accueil personnalisable** : blocs à afficher ou masquer et à réordonner (bouton « Personnaliser l'accueil »).
- **Thème** : sombre « salle des marchés » partout (site, rapports, graphiques) ; les PDF restent clairs pour l'impression.
- **Exports** : boutons « PDF » (rapport complet) et « Excel » (tous les chiffres, une feuille par partie,
  comptes bruts inclus) au-dessus de chaque rapport ; le Mac demande où enregistrer le fichier.

| Fichier | Rôle |
|---|---|
| `app.py` | serveur local (Flask) + fenêtre Mac (pywebview) |
| `interface/index.html` | l'interface (recherche, suggestions, progression, rapport) |
| `construire_liste.py` | télécharge la liste Euronext (site officiel) et S&P 500 (Wikipédia) → `data/actions.json` |
| `creer_app.py` | crée l'application `.app` et installe le code dans `~/Library/Application Support/Analyse Actions` |

Après une modification du code, ou pour rafraîchir la liste des actions :

```bash
cd ~/Desktop/"claude code /analyse-action"
.venv/bin/python construire_liste.py   # (facultatif) mettre à jour la liste
.venv/bin/python creer_app.py          # réinstaller l'application
```

Pourquoi une copie du code ? macOS interdit aux applications lancées depuis le Finder de lire
le Bureau sans autorisation : l'application utilise donc sa propre copie, hors du Bureau.
Les rapports de l'application sont enregistrés dans
`~/Library/Application Support/Analyse Actions/rapports`, et les erreurs éventuelles dans `app.log`.

Pour tester l'interface dans un navigateur : `.venv/bin/python app.py --navigateur`.

## Utilisation en ligne de commande

```bash
cd ~/Desktop/"claude code /analyse-action"
.venv/bin/python analyse_complete.py AAPL
```

Options :

| Option | Exemple | Effet |
|---|---|---|
| `--indice` | `--indice ^STOXX50E` | indice de référence (sinon choisi selon la place) |
| `--periode` | `--periode 10y` | `1y`, `2y`, `5y` (défaut), `10y`, `max` |
| `--sans-ouvrir` | | ne pas ouvrir le navigateur |

Le rapport est enregistré dans `rapports/TICKER_date.html`.

Tickers Yahoo Finance : `AAPL` (Apple), `MC.PA` (LVMH), `TTE.PA` (TotalEnergies),
`AIR.PA` (Airbus), `SAP.DE` (SAP), `^FCHI` (CAC 40), `^GSPC` (S&P 500).

## Structure

Chaque partie peut aussi être lancée seule (`.venv/bin/python partieN_xxx.py AAPL`).

| Fichier | Contenu | Notions |
|---|---|---|
| `partie1_donnees.py` | Téléchargement, rendements | prix ajustés, rendements simples / log |
| `partie2_performance.py` | Performance | CAGR, volatilité, Sharpe, Sortino, drawdown, Calmar |
| `partie3_marche.py` | Comparaison au marché | CAPM, bêta, alpha (test t), R², tracking error, information ratio, Treynor |
| `partie4_risque.py` | Risque de perte | VaR / CVaR (historique, normale, Cornish-Fisher, Monte Carlo Student), Jarque-Bera, tests de Kupiec et Christoffersen |
| `partie5_technique.py` | Analyse technique | MM50/200, RSI, Bollinger, MACD, backtest de 3 stratégies avec frais |
| `partie6_simulation.py` | Simulation et options | GBM, Black-Scholes + grecques, Monte Carlo risque-neutre, arbre binomial (option américaine) |
| `partie8_analyse_financiere.py` | Analyse financière des comptes (plan du cours de M1) | SIG, CAF, marges, effet ciseau, point mort d'exploitation / financier / total, indice de sécurité, levier opérationnel ; bilan fonctionnel (FR, BFR, TN), BFR normatif, délais, vétusté, politique d'investissement ; FTD, autofinancement, dividendes, levier DFN/EBE (+ équivalent de notation), DSCR, ICR, gearing, liquidité ; ROIC, ROCE, marge × rotation, ROE, effet de levier / massue, ROC marginal |
| `partie9_valorisation.py` | Valorisation et scores | multiples (PER, VE/EBE, P/B, rendement du FCF), CMPC, DCF + table de sensibilité, consensus des analystes, Z-score d'Altman, F-score de Piotroski |
| `interpretation_valorisation.py` | Explications de la partie 9 | dont le calculateur DCF interactif (curseurs) |
| `comparaison.py` | Comparaison de deux entreprises | `.venv/bin/python comparaison.py MC.PA KER.PA` |
| `portefeuille.py` | Portefeuille | `.venv/bin/python portefeuille.py MC.PA:2000 AAPL:1500 TTE.PA:1000` |
| `marche.py` | Tableau de bord | indices, valeurs phares, palmarès (mis en cache) |
| `actualites.py` | Actualités | flux RSS de la presse économique, Google Actualités et Yahoo Finance par entreprise |
| `simulateur.py` | Investissement mensuel | TRI (XIRR), comparaison au placement unique et au livret |
| `base_fondamentale.py` | Ratios de ~1 350 entreprises | filtre d'actions et concurrents (mise à jour quotidienne) |
| `suivi.py` | Liste de suivi | agenda, alertes et notifications macOS |
| `chemins.py` | Emplacements des fichiers | application autonome (lecture seule) vs données de l'utilisateur |
| `lanceur.py` | Démarrage de l'app autonome | écran de chargement immédiat |
| `macro.py` | Économie | séries FRED (Eurostat, BCE, Fed, OCDE), cache de 6 heures |
| `fictifs.py` | Bourse fictive | ordres, PRU, plus-values, dividendes, historique de valeur |
| `taux.py` | Courbe des taux | FRED (États-Unis) et BCE (zone euro) |
| `calendrier.py` | Calendrier économique | flux public Forex Factory + Yahoo Finance |
| `options_cotees.py` | Options cotées | chaîne Yahoo Finance, volatilité implicite |
| `interface/pro.js`, `pro.css` | Outils « pro » de l'interface | commandes, graphique, carte, marchés, options, accueil |
| `export.py` | Exports | PDF (xhtml2pdf) et classeur Excel (openpyxl) |
| `interpretation_financiere.py` | Explications de la partie 8 | notions, lecture des chiffres, repères normatifs et sectoriels (Banque de France 2022) |
| `analyse_complete.py` | Assemblage | rapport HTML |
| `interpretation.py` | Explications pour débutants | résumé en langage courant, « C'est quoi ? », lecture de chaque graphique, interprétation des chiffres, pastilles de niveau, lexique |

## Hypothèses et limites

- Taux sans risque fixe à 3 % (`TAUX_SANS_RISQUE` dans `partie2_performance.py`).
- Les indices Yahoo (`^FCHI`, `^GSPC`) sont des indices de prix, sans dividendes, alors que
  les actions sont en dividendes réinvestis : l'alpha est légèrement surestimé.
- Les options sont pricées sans dividende, avec la volatilité historique sur 1 an.
- Les projections Monte Carlo reposent sur la dérive passée : ce sont des illustrations, pas des prévisions.
- Analyse financière : comptes IFRS « par fonction » de Yahoo Finance (4 à 5 exercices). La valeur
  ajoutée, la production de l'exercice et les charges de personnel (présentation PCG « par nature »)
  ne sont pas disponibles. Point mort : coût des ventes supposé variable, autres charges fixes.
  Impôt normatif 25 %. Pas de notation ESG (non fournie par Yahoo). Banques et assurances exclues.
- DCF : flux de départ = moyenne des 3 derniers flux de trésorerie disponibles ; croissance = croissance
  passée du CA (bornée entre 0 et 12 %) ; croissance à l'infini 2 % ; prime de risque 5,5 %.
  C'est un ordre de grandeur : le calculateur interactif permet de tester d'autres hypothèses.
- Z-score d'Altman : version d'origine pour l'industrie, Z'' pour les services ; calibré sur des
  entreprises américaines, à interpréter avec prudence.
- Projet pédagogique : ce n'est pas un conseil d'investissement.

## Réinstaller l'environnement

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Partager l'application avec d'autres Mac

```bash
.venv/bin/python construire_dmg.py
```

Crée `distribution/Analyse-Actions.dmg` (environ 85 Mo) : une application **autonome** qui embarque
Python et toutes les bibliothèques. À envoyer par AirDrop, WeTransfer, Google Drive…
Le fichier `LISEZ-MOI.txt` inclus explique l'installation (l'application n'étant pas signée par Apple,
macOS demande une autorisation au premier lancement).

- Mac à puce Apple uniquement (M1 et suivants), macOS 12 ou plus récent.
- Les données de chaque utilisateur restent sur son Mac (`~/Library/Application Support/Analyse Actions`).
- Après une modification du code, relancer `construire_dmg.py` pour produire une nouvelle version.
