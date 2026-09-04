# scitech-librarian
<!-- source-digest: 5aa2524bea7c059a -->

[![Tests](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml/badge.svg)](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Dependencies: stdlib only](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](librarian.py)
[![Plays by the rules](https://img.shields.io/badge/APIs-documented%20%26%20ToS--compliant-blueviolet)](#respecte-les-règles)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) · [Português (Brasil)](README.pt-BR.md) · [Español](README.es.md) · [Deutsch](README.de.md) · **Français**

*Traduction du README anglais, qui fait référence ; les commandes, noms de fichiers, options et blocs de code sont conservés tels quels.*

**Une requête, toutes les bases de données savantes — et un répertoire de
recherche qui se souvient de chaque recherche, de chaque notice ajoutée à la
main, et rédige le rapport PRISMA de l'ensemble.**

Écrivez une requête structurée une seule fois ; scitech-librarian la traduit
dans la syntaxe native de huit bases de données bibliographiques (OpenAlex,
NASA ADS, arXiv, INSPIRE-HEP, Scopus, Semantic Scholar, Crossref, Web of
Science), les exécute toutes et archive l'exécution — notices brutes, RIS pour
Zotero, la chaîne de requête exacte envoyée à chaque backend, les nombres de
résultats — dans un répertoire horodaté que vous pouvez citer. Les exécutions
s'accumulent dans un **répertoire de recherche** : un dossier par projet qui
accueille aussi les notices obtenues hors de l'outil (exports Zotero, Mendeley
et Web of Science, le RIS d'un collègue, une liste de références) avec leur
provenance, conserve les indicateurs des revues année par année et produit un
**rapport de recherche bibliographique** — stratégie de recherche, résultats,
**diagramme de flux PRISMA 2020 et liste de contrôle PRISMA-S**, chronologie,
ce que chaque recherche a apporté, indicateurs des revues, suggestions — pour
une exécution ou pour le projet entier, filtré par date, source, base de
données, année, citations ou qualité de la revue, en Markdown, HTML, LaTeX,
PDF ou texte brut, à trois niveaux de détail. Un laboratoire tient un
répertoire par projet. Les bases de données sont de la **configuration, pas du
code**.

Bibliothèque standard uniquement, aucune installation : cinq scripts —
`librarian.py` (recherche), `project.py` (répertoire de recherche et
ingestion), `report.py` (rapports), `journals.py` (indicateurs des revues),
`wos_manual.py` (Web of Science à la main) — plus `render.py`, le moteur de
rendu partagé Markdown/HTML/LaTeX/PDF, et `i18n.py`, le catalogue des langues
du rapport. Documentation complète : [**Manuel utilisateur**](docs/USER_MANUAL.fr.md)
([HTML](docs/USER_MANUAL.fr.html) · [PDF](docs/USER_MANUAL.fr.pdf) ; original anglais :
[User Manual](docs/USER_MANUAL.md), [HTML](docs/USER_MANUAL.html) · [PDF](docs/USER_MANUAL.pdf)) ;
un [**parcours guidé**](docs/WALKTHROUGH.md) (en anglais) d'un projet réel,
du début jusqu'à PRISMA, met en œuvre chaque fonctionnalité ;
[JCR import](docs/JCR_IMPORT.md) couvre le facteur d'impact sous licence. Vous
travaillez avec un agent d'IA ? Donnez-lui [**AGENTS.md**](AGENTS.md) — les
instructions complètes orientées machine — et dites-lui *« lis AGENTS.md,
puis fais une vérification de nouveauté sur X »*.

```bash
python librarian.py --selftest                       # ping every backend; report what works
python librarian.py --counts-only                    # fast: hit counts for every query block
python librarian.py --pdfs                           # full run + legal open-access PDF lookup
python project.py ingest export.ris --name zotero --method citation   # records from outside
python report.py --project --since 2026-06-01 --diff # what the searches since June added
python journals.py fetch                             # venue metrics (OpenAlex, no key)
```

> **Les retours sont très appréciés.** Si une base de données se comporte
> mal, si un nombre semble faux, ou si vous avez écrit une entrée de
> `backends.json` pour une base de données que nous ne fournissons pas,
> merci d'[ouvrir un ticket](https://github.com/fabiocampolim-design/scitech-librarian/issues) —
> les entrées de configuration pour de nouvelles bases de données sont
> particulièrement bienvenues.

**Pourquoi cela existe.** Une recherche bibliographique que vous ne pouvez
pas rejouer est une affirmation que vous ne pouvez pas défendre. Les revues
systématiques et les vérifications de nouveauté (« personne n'a fait X »)
dépendent exactement des bases de données interrogées, avec exactement quelle
requête, exactement quel jour — et cette trace ne survit presque jamais. Cet
outil a été construit pour les vérifications de nouveauté d'un doctorat en
physique et conserve cette trace par construction : chaque exécution archive
ses requêtes, ses nombres et ses notices, de sorte que six mois plus tard la
recherche est reproductible et la dérive des nombres est visible.

## Respecte les règles

Cet outil est strict sur les conditions d'utilisation de chaque base de
données qu'il touche — non comme petits caractères, mais comme principe de
conception :

- **Uniquement des API publiques documentées.** Il ne fait jamais de
  scraping d'une interface web. Scraper Web of Science ou Scopus viole leurs
  conditions et peut faire suspendre l'accès de toute votre institution.
- **Web of Science sans licence d'API est un travail manuel, alors nous
  avons rendu le travail manuel petit** — `wos_manual.py` prépare chaque
  requête dans la grammaire propre de WoS, vous guide pour les coller dans
  l'interface officielle et ingère vos exports RIS dans le même schéma de
  notices. Coller, exporter, terminé.
- **Pas de Google Scholar.** Il n'a pas d'API, et le scraper viole ses
  conditions.
- **Limites de débit respectées** — pauses par backend (y compris les ≥3 s
  entre appels demandées par arXiv) et un courriel de contact dans le
  User-Agent, ce qui vous place aussi dans le « polite pool », plus rapide,
  d'OpenAlex/Crossref.
- **PDF uniquement via Unpaywall** — copies légales en libre accès, jamais
  de contournement de paywall.
- **Les droits d'accès sont honorés, pas contournés** — les résultats Scopus
  passent par l'abonnement de votre institution (réseau du campus ou VPN), et
  le README documente comment cet accès fonctionne réellement.

## Fonctionnalités

- **Une requête structurelle, huit grammaires natives.** `[[a, b], [c]]`
  signifie `(a OR b) AND c` ; la syntaxe de chaque backend —
  `TITLE-ABS-KEY(...)`, `TS=(...)`, `abs:"..."`, `and` en minuscules — est
  générée depuis la même définition, de sorte que les requêtes ne se
  désynchronisent jamais entre bases de données.
- **Les bases de données sont des données.** Chaque backend est une entrée
  JSON : grammaire de requête, point d'accès, en-tête d'authentification,
  style de pagination et chemins pointés dans la réponse. `--init-backends`
  écrit les valeurs par défaut dans `backends.json` ; modifiez-le pour
  ajouter, changer ou désactiver des bases de données sans toucher au code.
  Seuls les moteurs qui ont réellement besoin de code (le flux XML d'arXiv)
  utilisent un petit pilote.
- **Tout est archivé.** Chaque exécution écrit un répertoire horodaté avec
  les notices JSON brutes, le RIS par bloc, un ensemble dédoublonné en
  CSV/RIS/JSON/BibTeX/CSL-JSON, la chaîne de requête exacte envoyée à chaque
  backend, les nombres en JSON et un tableau markdown prêt à coller, les
  métadonnées de l'exécution et un journal complet. Les nombres sont aussi
  ajoutés à un fichier d'historique pour que la dérive dans le temps soit
  visible.
- **Un répertoire de recherche, pas un tas d'exécutions.** `project.py`
  indexe chaque exécution et chaque notice apportée de l'extérieur (RIS,
  BibTeX, CSV, JSON — Zotero, Mendeley, Web of Science, listes de
  références ; un dossier de dépôt pour les collaborateurs), conserve la
  provenance (qui, quand, d'où, méthode PRISMA), fusionne tout avec
  `found_by` / `first_seen` par notice, et `report.py --project` décrit le
  projet entier : ce que chaque recherche a apporté, quelle base de données
  a trouvé ce qu'aucune autre n'a trouvé, la dérive des nombres dans le
  temps, et un flux PRISMA avec les deux colonnes d'identification. Filtres
  par fenêtre de dates, différentiel (« nouveau depuis juin »), type de
  source, base de données, bloc, année de publication, citations, indicateur
  de revue. Un répertoire par projet ; un laboratoire en a plusieurs.
- **Indicateurs des revues, année par année.** `journals.py` récupère la
  citation moyenne sur 2 ans d'OpenAlex (sans clé) et CiteScore/SJR/SNIP de
  Scopus (avec clé), importe les CSV SCImago et les exports JCR sous licence,
  stocke les valeurs par année pour que la série se construise, et alimente
  une colonne d'indicateur, un tableau des revues par indicateur, un tableau
  d'évolution et `--min-metric` dans les rapports.
- **Journaux et audits.** Chaque script écrit un journal d'audit (invocation,
  versions, chaque avertissement) sous `<outdir>/logs/` ; la sortie console
  est réduite par défaut, `--verbose` / `--quiet` / `--log-dir` / `--outdir`
  sur tous ; `--help` liste chaque paramètre avec sa valeur par défaut.
- **Un rapport de recherche bibliographique, PRISMA inclus.** Chaque
  exécution se termine par `report.md` (ou HTML / LaTeX / PDF / texte brut) :
  la stratégie de recherche avec la chaîne exacte envoyée à chaque base de
  données, un résumé des résultats, un **diagramme de flux PRISMA 2020** dont
  les étapes automatisables sont remplies à partir de l'exécution, une liste
  de contrôle **PRISMA-S** pour la déclaration de la recherche, les
  meilleures notices par bloc, et des suggestions fondées sur des règles
  (resserrer ce bloc, relancer ce backend, augmenter le plafond, lire ces
  cinq résultats à la main). Trois niveaux — `simple`, `intermediate`,
  `full` — d'un résumé de deux pages à chaque notice avec son résumé et le
  journal complet. Voir [Rapports et PRISMA](#rapports-et-prisma).
- **Rapports en cinq langues.** `--lang pt-BR|es|de|fr` (par défaut `en`)
  écrit le texte propre du rapport — titres, étapes et diagramme PRISMA,
  liste de contrôle, explications, suggestions — en portugais du Brésil,
  espagnol, allemand ou français. Les notices, chaînes de requête, noms de
  blocs, noms de fichiers et journaux ne sont jamais traduits : un rapport
  reste une trace fidèle de la recherche dans chaque langue.
- **Résistant aux plantages grâce aux points de reprise.** Les nombres sont
  sauvegardés après *chaque* appel d'API et Ctrl-C est sûr — un blocage
  tardif dans une longue exécution ne perd rien.
- **Un filtre à déchets avec justificatifs.** OpenAlex indexe des dépôts non
  curatés ; sur une exécution de 5 146 notices, 15,3 % de ses notices
  venaient de Zenodo, SSRN, Figshare et consorts — contre 0 % pour ADS,
  Scopus, Semantic Scholar et INSPIRE. Sur une requête de nouveauté décisive,
  c'était toute la différence entre 16 résultats et 3. Filtré par défaut ;
  `--keep-junk` désactive.
- **Fonctionne sans aucune affiliation.** Cinq backends n'ont besoin ni de
  clé ni d'institution ; ADS n'a besoin que d'un jeton personnel gratuit.
  Pas de VPN, pas de réseau de campus, pas d'abonnement — cela ne compte que
  si vous ajoutez Scopus ou l'API WoS par-dessus.
- **La physique a une couverture de premier ordre.** NASA ADS et INSPIRE-HEP
  sont des backends qu'aucun outil comparable ne fournit ; pour la physique
  évaluée par les pairs, ADS est essentiellement complet.
- **Les vérifications de nouveauté comme flux de travail.** Concevez des
  blocs de sorte qu'un *petit* nombre soit le résultat informatif, exécutez
  les mêmes blocs dans le temps, surveillez les nombres — puis lisez chaque
  résultat à la main avant d'affirmer une lacune.
- **Testable hors ligne.** 305 vérifications s'exécutent sans réseau et sans
  clés (les backends sont exercés contre des réponses d'API enregistrées ; le
  répertoire de recherche, les analyseurs d'ingestion, le magasin des revues
  et le générateur de rapports contre des répertoires synthétiques) ; CI sur
  Linux, Windows et macOS, Python 3.9 et 3.13.

## Les bases de données : à quoi chacune sert vraiment

| Base de données | Clé nécessaire | Couverture | À utiliser pour | Attention à |
|---|---|---|---|---|
| **OpenAlex** | aucune | ~250 M d'œuvres, prépublications incluses | première passe, fonctionne toujours, sans institution | ~15 % de déchets non curatés — filtrés par défaut |
| **NASA ADS** | jeton gratuit | physique + astronomie évaluées complètes, arXiv intégré | **meilleure source unique pour la physique** | rien de grave |
| **arXiv** | aucune | prépublications, tous domaines | travaux tout neufs | s'étrangle sur les booléens imbriqués — voir Pièges |
| **INSPIRE-HEP** | aucune | HEP, QCD sur réseau, théorie des particules | littérature invisible pour les index généraux | champ disciplinaire étroit |
| **Scopus** | clé gratuite + institution | ~27–28 k revues curatées | nombres de qualité citation pour les articles | droits par IP ; nécessite le réseau du campus ou un VPN |
| **Semantic Scholar** | aucune | large, bon graphe de citations | recoupement | ~1 req/s sans clé |
| **Crossref** | aucune | métadonnées DOI de ~150 M d'éléments | résoudre des DOI | **pas de booléens** — nombres sans signification, exclu des exécutions par défaut |
| **Web of Science** | sous licence | ~21–22 k revues curatées | légitimité conventionnelle | API rarement sous licence — utiliser `wos_manual.py` |

**Si vous n'en configurez que deux :** OpenAlex (fonctionne immédiatement) et
NASA ADS (jeton gratuit en 30 secondes). Ajoutez Scopus si vous avez besoin de
nombres de qualité citation pour un article. **Vérification de réalité sur la
couverture :** Scopus indexe ~25–30 % de revues de plus que WoS et 80–85 % des
revues WoS sont aussi dans Scopus ; pour la physique ADS est essentiellement
complet — donc Scopus + ADS + arXiv est, en pratique, un sur-ensemble de WoS.

## Obtenir les clés

L'outil lit ses clés depuis l'environnement du processus. Deux voies les y
placent, et vous pouvez les mélanger :

- **Un fichier `.env`** — copiez `.env.example` vers `.env` et remplissez-le ;
  le script le lit automatiquement, aucune variable de shell à définir. Il est
  ignoré par git.
- **Des variables d'environnement** — exportez-les depuis votre shell,
  définissez-les dans la configuration de votre agent ou lanceur, ou
  fournissez-les comme secrets de CI. Elles ont la priorité : `.env` ne
  remplit que ce qui n'est pas déjà défini, donc si vous configurez les clés
  ainsi vous n'aurez jamais besoin d'un `.env`.

Dans les deux cas, `python librarian.py --list` montre quelles clés sont
arrivées et `--selftest` prouve qu'elles fonctionnent.

- **NASA ADS** — <https://ui.adsabs.harvard.edu/user/settings/token>.
  Connectez-vous, générez, collez. Le meilleur rendement par minute.
- **Scopus / Elsevier** — <https://dev.elsevier.com/apikey/manage>. Gratuit,
  instantané. La clé vous authentifie *vous* ; le droit d'accès vient de
  l'abonnement de votre institution, donc soyez sur le réseau du campus ou le
  VPN (un 401/403 signifie généralement un problème de réseau, pas une
  mauvaise clé). **Elsevier n'a pas de bouton de révocation** — une clé qui
  fuit est brûlée, pas désactivée. Demandez éventuellement à votre
  bibliothèque un InstToken, qui supprime la dépendance au VPN.
- **Semantic Scholar** — facultatif ; fonctionne sans clé à ~1 req/s.
- **Web of Science** — voir le compagnon manuel ci-dessous ; la grammaire
  restreinte de la clé Starter rend l'API rarement rentable.

**Pas d'institution ? L'essentiel fonctionne quand même.** Cinq des huit
backends (OpenAlex, arXiv, INSPIRE-HEP, Semantic Scholar, Crossref) n'ont
besoin d'aucune clé ni d'aucun accès institutionnel, et NASA ADS n'a besoin
que d'un jeton personnel gratuit — l'outil est donc pleinement utilisable
depuis n'importe quel portable, sans affiliation et sans VPN. Le droit
institutionnel ne compte que pour Scopus (et l'API WoS sous licence) : là, la
clé vous authentifie *vous*, mais les résultats passent par l'abonnement de
votre institution, généralement fondé sur l'IP — soyez sur le réseau
institutionnel, ou utilisez le VPN, le proxy ou l'authentification fédérée
que votre institution fournit, avant que l'API ne renvoie quoi que ce soit.
Le test est toujours le même : lancez `--selftest` et voyez si Scopus renvoie
un nombre plausible.

## Écrire des requêtes

Les requêtes vivent dans `queries.json` (copiez `queries.example.json` et
modifiez-le) :

```json
{
  "NOV": {
    "title": "my novelty check",
    "note":  "a SMALL number is the good outcome",
    "groups": [
      ["origami", "kirigami"],
      ["acoustic metamaterial", "phononic crystal"],
      ["topological pumping", "edge state"]
    ],
    "arxiv_groups": [0, 2]
  }
}
```

`groups` est une conjonction de disjonctions. `arxiv_groups` indique
facultativement quels groupes (deux au plus) vont à arXiv, qui se dégrade sur
les booléens profondément imbriqués. Le bloc le plus précieux est
généralement une intersection délibérée de deux littératures dont vous
soupçonnez qu'elles ne se parlent pas — un résultat proche de zéro est une
découverte, pas un échec, *si* vous lisez ensuite chaque résultat à la main.

## Ajouter une base de données (sans code)

```bash
python librarian.py --init-backends     # writes backends.json (next to .env) for editing
```

Une entrée de backend déclare la grammaire de requête, la requête HTTP et
l'emplacement des données dans la réponse :

```json
"europepmc": {
  "syntax":  {"term": "always"},
  "request": {"url": "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
              "params": {"query": "{q}", "format": "json", "pageSize": "{n}",
                         "cursorMark": "{cursor}"},
              "paging": {"style": "cursor", "next": "nextCursorMark", "start": "*"}},
  "parse":   {"total": "hitCount", "items": "resultList.result",
              "fields": {"title": "title", "year": "pubYear", "doi": "doi",
                         "journal": "journalTitle"}}
}
```

Styles de pagination : `cursor`, `page`, `offset`, `none`.
L'authentification est une variable d'environnement associée à un en-tête.
Les chemins de champs acceptent l'indexation `[0]`, l'application `[]` sur
des listes, les alternatives `a|b` et des transformations nommées.
`docs/FUTURE_BACKENDS.md` contient des points de départ vérifiés pour Europe
PMC, OpenAIRE, DOAJ, ERIC, EconBiz, Zenodo, ClinicalTrials.gov et CORE, chacun
revérifié contre l'API en direct, ainsi que le test booléen qu'un candidat doit
réussir avant de valoir la peine. Les entrées de `backends.json`
recouvrent les valeurs intégrées par nom ; `"disabled": true` en supprime
une.

## Web of Science, la situation honnête

La grammaire complète `TS=`/`NEAR` vit dans l'**Expanded API**, sous licence
séparée, que les accords de consortiums nationaux n'incluent généralement
pas ; le niveau gratuit **Starter** rejette les booléens complexes. Si votre
bibliothèque ne peut pas vous obtenir d'identifiants Expanded, WoS est un
travail manuel — et `wos_manual.py` le rend petit :

```bash
python wos_manual.py prep      # query files + CHECKLIST.md, in WoS grammar
python wos_manual.py walk      # copies each query to your clipboard in turn
python wos_manual.py ingest    # parses your RIS exports into the same schema
python wos_manual.py status    # what you have collected so far
```

La liste de contrôle encode les réglages de l'interface qui cassent
silencieusement les requêtes (Core Collection et non All Databases ; Advanced
et non Basic ; quelles éditions ; forme balisée `TS=(...)` contre forme nue —
coller une requête balisée dans un champ choisi par menu déroulant donne
*« Search Error: Invalid query »*). `ingest` fusionne les résultats manuels
avec les résultats automatisés, même schéma, même analyse.

## Comparaison

[findpapers](https://github.com/jonatasgrosman/findpapers) est l'outil le
plus proche : une requête booléenne sur huit bases de données (IEEE et PubMed
incluses), avec dédoublonnage, raffinement et téléchargement de PDF — un bon
choix pour les revues systématiques à la manière du génie logiciel sur
Python 3.11+. [litstudy](https://github.com/NLeSC/litstudy) analyse une
collection que vous avez déjà (bibliométrie, graphes de réseau, thèmes) dans
Jupyter. [paperscraper](https://github.com/jannisborn/paperscraper) est conçu
pour les sciences de la vie (PubMed + serveurs de prépublications) avec des
outils de facteur d'impact et de dumps.

Le créneau de cet outil : **l'instrument de recherche reproductible.** Un seul
fichier sans installation ; le seul avec NASA ADS et INSPIRE-HEP (physique) ;
des exécutions archivées et citables avec chaînes de requête exactes et
historique des nombres ; des bases de données en configuration utilisateur ;
et une position stricte « API documentées uniquement » (findpapers comme cet
outil utilisent l'API officielle WoS Starter ; paperscraper scrape Google
Scholar — nous refusons). Si vous avez besoin d'IEEE/PubMed aujourd'hui ou de
collecte de PDF dans l'outil, utilisez findpapers ; pour des graphes
bibliométriques, litstudy ; pour des recherches auditables et la couverture de
la physique, celui-ci.

## Pièges rencontrés, pour que vous les évitiez

(Le [Manuel utilisateur](docs/USER_MANUAL.fr.md) §12 liste chaque
fonctionnalité et chaque limitation connue en un seul endroit.)

- **arXiv se bloque sur les booléens profondément imbriqués** — ce n'est pas
  une erreur, il ne répond simplement jamais. Au plus deux groupes sont
  envoyés (`arxiv_groups` choisit lesquels), en HTTPS, avec un délai court,
  parce qu'une heuristique automatique « le plus sélectif » a mal choisi.
- **Les nombres ne sont pas comparables entre backends.** Les opérateurs de
  proximité sont abandonnés et la racinisation diffère. Découvrez ici ; citez
  WoS/Scopus dans l'article.
- **Le `cmd.exe` de Windows ne traite pas `#` comme un commentaire** — un
  `# note` collé en fin de ligne devient une erreur argparse. Utilisez
  PowerShell ou supprimez le commentaire.
- **Unpaywall est un appel HTTP par DOI** (~20 min pour 3 000). Restreignez
  avec `--pdf-blocks` ; les résultats sont mis en cache entre exécutions.

## Sortie

Chaque exécution écrit `lit/runs/<timestamp>/` :

```
report.md (html, tex, pdf, txt)  the literature-search report, see below
counts.json / counts.md          hit counts + a paste-ready markdown table
queries.json                     the EXACT query sent to each backend
blocks.json                      the structural query definitions used
meta.json                        run settings, backend endpoints, version, timing
records/<block>_<backend>.json   full records, raw
ris/<block>_<backend>.ris        per-block RIS for Zotero
all_records.{json,csv,ris}       deduped by DOI, sorted by citation count
all_records.{bib,csl.json}       the same set as BibTeX and CSL-JSON (Zotero, pandoc)
junk.json                        records removed by the venue filter (with receipts)
prisma.json                      manual PRISMA screening stages -- fill in, re-render
run.log                          everything printed, including errors
```

plus `lit/counts_history.csv`, complété à chaque exécution, et le répertoire
de recherche autour :

```
lit/
  project.json                  index: name, labels, exclusions, block aliases, defaults
  runs/<stamp>/                 automated searches (above)
  manual/<name>/                ingested sources: source.json (provenance), records.json, the original file
  inbox/                        drop RIS/BibTeX/CSV/JSON here; `project.py ingest --inbox`
  journals/metrics.json         venue metrics per year (journals.py)
  screening.json                project-wide PRISMA manual stages
  reports/<stamp>-<level>/      project reports (report.py --project)
  logs/                         one audit log per script invocation
```

## Le répertoire de recherche

```bash
python project.py init --name "Topological materials review"
python project.py ingest export.ris --name zotero-aug --block CD --method citation \
       --who "A. Colleague" --origin "Zotero group library"
python project.py ingest --inbox                 # everything dropped in lit/inbox/
python wos_manual.py ingest                      # Web of Science exports become manual sources
python project.py oa                             # open-access lookup over every member that lacks it
python project.py status
python report.py --project                       # everything merged
python report.py --project --since 2026-06-01 --diff --format pdf   # what is new since June
python report.py --project --backends ads scopus --min-metric 3 --metric scopus_citescore
```

Les notices externes arrivent de trois façons : la ligne de commande (avec
provenance complète), un dossier de dépôt (déposer et ingérer), ou la
routine Web of Science. Elles conservent le fichier d'origine, reçoivent le
schéma commun de notices, sont étiquetées `manual:<name>`, et leur `--method`
(database, citation, website, organisation, expert, other) les place dans le
flux PRISMA. Les sources manuelles apparaissent dans chaque tableau comme une
base de données de plus — y compris « trouvé ici seulement », ce qui vous
apprend ce que la liste de références de votre collègue contenait et que six
bases de données n'avaient pas.

## Rapports et PRISMA

Une recherche que vous ne pouvez pas déclarer est une recherche que vous ne
pouvez pas défendre, donc chaque exécution se termine par un rapport.
`--report-level` choisit le détail, `--report-format` les fichiers ;
`report.py` régénère n'importe quelle exécution archivée sans toucher au
réseau.

| Niveau | Ce que vous obtenez |
|---|---|
| `simple` (par défaut) | métadonnées de l'exécution ; sources (projet) ; stratégie de recherche (requête structurelle + la chaîne exacte envoyée à chaque backend) ; résumé des résultats ; chronologie (projet) ; flux PRISMA 2020 + liste PRISMA-S ; 10 meilleures notices par bloc ; suggestions |
| `intermediate` | + chaque notice unique ; la contribution marginale de chaque source (« trouvé ici seulement ») ; distributions par année / revue / auteur ; indicateurs des revues et leur évolution ; revues retirées par le filtre ; erreurs ; statistiques de libre accès ; dérive des nombres par rapport aux exécutions antérieures |
| `full` | + chaque notice avec résumé et liste d'auteurs complets, et les sources qui l'ont trouvée ; listes brutes par source avant dédoublonnage ; les notices filtrées ; configuration des points d'accès des backends ; fichiers de provenance du projet et des sources ; le journal complet de l'exécution ; environnement |

Formats : `md`, `html` (autonome, clair/sombre, imprimable), `tex`, `pdf`,
`txt`. Le PDF est compilé à partir du LaTeX avec xelatex / lualatex /
pdflatex si l'un d'eux est installé, sinon avec pandoc, sinon par un moteur
intégré sans dépendances — l'option n'échoue jamais, seule la typographie se
dégrade.

**Langues.** `report.py --lang` et `librarian.py --report-lang` acceptent `en`
(par défaut), `pt-BR`, `es`, `de` ou `fr` ; un répertoire de recherche peut
définir `"defaults": {"lang": "pt-BR"}` dans `project.json`. Seule
l'armature du rapport est traduite — titres, en-têtes de tableau, les étapes
PRISMA 2020 et le diagramme de flux dans chaque format, la liste PRISMA-S, le
texte explicatif, les suggestions, les séparateurs de milliers. Tout ce que
l'outil a trouvé ou reçu est reproduit tel quel : titres, résumés, auteurs,
revues, noms et notes des blocs, les chaînes de requête exactes, noms des
backends, options, noms de fichiers, sorties JSON et le journal de
l'exécution incorporé. `run.log`, les journaux d'audit et la console restent
en anglais quelle que soit la langue du rapport. Exemple :
[`samples/pt-BR/report.md`](samples/pt-BR/report.md).

**PRISMA.** Le rapport comporte un diagramme de flux
[PRISMA 2020](https://www.prisma-statement.org/) (SVG en HTML, TikZ en
LaTeX/PDF, ASCII en Markdown/texte). Les étapes qu'un outil peut connaître
sont remplies à partir des données — notices identifiées par base de données,
notices identifiées par d'autres méthodes (sources manuelles par méthode),
notices retirées par automatisation (le filtre de revues), doublons retirés,
notices restant à trier — et sont honnêtes sur la différence entre
*identifiées* (ce que chaque base de données déclare) et *récupérées* (ce qui
a été téléchargé dans la limite de `--limit`). Les étapes que seul un humain
peut connaître — triées, exclues, recherchées, évaluées, incluses, avec les
motifs d'exclusion, pour les deux colonnes — sont lues dans `prisma.json`
(une exécution) ou `screening.json` (répertoire de recherche) ; un modèle est
écrit au premier rapport, remplissez-le donc au fil du tri et relancez
`report.py`. Une liste de contrôle
[PRISMA-S](https://doi.org/10.1186/s13643-020-01542-z) pour la déclaration de
la recherche (les 16 items) est complétée automatiquement là où l'outil a les
données — bases de données, stratégies complètes, limites, filtres, dates,
totaux, méthode de dédoublonnage, mises à jour — et marque le reste « à
compléter ».

```bash
python librarian.py --report-level intermediate --report-format md html
python report.py lit/runs/20260815T095908 --level full --format pdf
python report.py --latest --format txt            # newest run, plain text
python librarian.py --no-report                   # search only
```

Filtres de rapport (les deux modes) : `--since/--until DATE`, `--latest`,
`--diff`, `--year-from/--year-to`, `--backends`, `--blocks`,
`--sources auto|manual|all`, `--records FILE…` (RIS/BibTeX/CSV/JSON
supplémentaires pour ce seul rapport), `--metric NAME --min-metric X`,
`--min-citations N`, `--oa-only`, `--top N`, `--sort cited|year|metric`. Les
filtres sont imprimés dans les métadonnées du rapport et dans l'item 9 de
PRISMA-S, pour qu'un rapport filtré ne soit jamais pris pour la recherche
entière.

## Indicateurs des revues

```bash
python journals.py fetch                                   # every journal seen in lit/: OpenAlex (+ Scopus with a key)
python journals.py import-scimago scimagojr_2024.csv --year 2024 --all
python journals.py import-csv jcr.csv --provider jcr_if --year 2023 --name-col "Journal name" --value-col JIF
python journals.py show --metric scopus_citescore
```

`lit/journals/metrics.json` conserve une entrée par revue (indexée par ISSN)
avec des valeurs **par année, jamais écrasées** — récupérez à nouveau l'an
prochain et le rapport montre la série. Fournisseurs : citation moyenne sur
2 ans et indice h d'OpenAlex (sans clé ; instantané par année de
récupération), CiteScore / SJR / SNIP de Scopus (clé ; historique complet),
SJR / indice H / quartile de SCImago (un téléchargement CSV par an, la voie
vers *toutes* les ~30 000 revues), et le Journal Impact Factor de Clarivate —
propriétaire, sans API gratuite, import uniquement depuis un export sous
licence. L'outil ne le scrapera pas.

### Rapports d'exemple

[`samples/`](samples/) contient une exécution réelle des quatre blocs
d'exemple de `queries.example.json` contre les trois bases de données **sous
licence CC0** (OpenAlex, arXiv, INSPIRE-HEP ; 2026-08-28 : 5 705 résultats
identifiés, 1 286 notices récupérées, 1 226 uniques) rendue à chaque niveau
et dans chaque format — `simple` fait 6 pages, `intermediate` 68, `full` 427.
Extraits des PDF :

| `simple`, p. 1 — métadonnées de l'exécution et stratégie de recherche | `simple`, p. 3 — flux PRISMA 2020 |
|---|---|
| [![](samples/img/simple_p1.png)](samples/simple/report.pdf) | [![](samples/img/simple_p3.png)](samples/simple/report.pdf) |

| `simple`, p. 2 — requête exacte par backend, nombres | `full` — notices avec résumés |
|---|---|
| [![](samples/img/simple_p2.png)](samples/simple/report.pdf) | [![](samples/img/full_records.png)](samples/full/report.pdf) |

Parcourir : [simple](samples/simple/report.md) ·
[intermediate](samples/intermediate/report.md) ·
[full](samples/full/report.md) (Markdown, rendu par GitHub), ou les `.html`,
`.tex`, `.pdf`, `.txt` à côté de chacun ;
[`samples/pt-BR/`](samples/pt-BR/) est le rapport `simple` de la même
exécution en portugais du Brésil (`--lang pt-BR`).

[`samples/project/`](samples/project/) est le même exemple sous forme de
**répertoire de recherche** : deux exécutions (une première passe OpenAlex
seul et l'exécution CC0 complète) plus la liste de références d'un collègue
ingérée comme source manuelle, avec la citation moyenne sur 2 ans d'OpenAlex
enregistrée pour 103 revues — `report.md/html/tex/pdf/txt` (simple),
`report_intermediate.md` et `report_diff.md` (`--since 2026-08-28 --diff`).

| `project`, p. 1 — sources et ce que chacune a apporté | `project`, p. 3 — PRISMA avec les deux colonnes d'identification |
|---|---|
| [![](samples/img/project_p1.png)](samples/project/report.pdf) | [![](samples/img/project_prisma.png)](samples/project/report.pdf) |

**Pourquoi seulement trois bases de données dans les exemples.** OpenAlex,
arXiv et INSPIRE publient leurs métadonnées sous CC0, donc leurs notices —
résumés compris — peuvent être redistribuées ici. Les données de Scopus, NASA
ADS et Semantic Scholar relèvent de leurs propres conditions d'API (Scopus :
pas de redistribution hors de votre institution ; Semantic Scholar : ODC-BY),
donc les rapports construits dessus sont pour votre propre répertoire de
recherche, pas pour un dépôt public. L'outil interroge les huit ; les
exemples en montrent trois.

## Référence des commandes

```
python librarian.py --selftest              ping every backend; report what works
python librarian.py                         all blocks, all configured backends
python librarian.py --counts-only           fast: hit counts, no record fetch
python librarian.py --blocks A CD           selected blocks
python librarian.py --skip arxiv            exclude a misbehaving backend
python librarian.py --pdfs --pdf-blocks A   legal OA-PDF lookup, restricted
python librarian.py --queries mine.json     use a different query file
python librarian.py --backends-file b.json  use a different backends config
python librarian.py --init-backends         write defaults to backends.json
python librarian.py --list                  blocks + backend readiness
python librarian.py --report-level full     simple | intermediate | full (default simple)
python librarian.py --report-format md pdf  any of md html tex pdf txt (default md)
python librarian.py --report-lang pt-BR     report language: en pt-BR es de fr (default en)
python librarian.py --no-report             skip the report
python librarian.py --outdir DIR            another research directory (all scripts)
python report.py <run dir> | --latest       re-render an archived run (--level, --format, --lang)
python report.py --project [filters]        the whole research directory
python project.py init|status|ingest|oa|exclude|include|label|alias
python journals.py fetch|import-scimago|import-jcr|import-csv|list|show
python wos_manual.py prep|walk|ingest|status
```

Chaque script : `--help` liste chaque paramètre avec sa valeur par défaut ;
`--outdir`, `--verbose`, `--quiet`, `--log-dir` sont communs à tous.

## Un flux de travail qui marche

1. Écrivez 5–10 blocs ; incluez au moins une requête croisée délibérée entre
   des littératures que vous soupçonnez déconnectées.
2. `--selftest`, puis `--counts-only` pour voir la forme de chaque champ.
3. Resserrez tout ce qui renvoie des milliers de résultats — un mot
   générique est généralement le coupable.
4. Exécution complète avec `--pdfs` ; importez le RIS dans Zotero. Lisez
   `report.md`.
5. **Lisez chaque résultat de vos petits blocs à la main** avant d'affirmer
   une lacune ; notez ce que vous avez trié et retenu dans `prisma.json` et
   régénérez le rapport — le diagramme de flux est alors prêt pour le
   matériel supplémentaire de l'article.
6. Fouillez les listes de références des PDF pour les travaux que tout le
   monde cite et que vous n'avez pas — cela attrape ce que la recherche par
   mots-clés manque, et cela a attrapé les deux références les plus
   importantes du projet pour lequel ceci a été construit.

Ou déléguez la boucle : exposez votre question de recherche à un agent d'IA
(Claude Code ou similaire) et demandez-lui de rédiger le `queries.json`, de
lancer les balayages et de parcourir avec vous les résultats archivés. Le
fichier de requête structuré, la configuration JSON et les répertoires
d'exécution horodatés sont délibérément faciles à écrire et à auditer par un
agent — cet outil a été construit dans exactement ce flux de travail.

## Feuille de route

- Plus de bases de données en configuration : Europe PMC, OpenAIRE, DOAJ,
  ERIC, EconBiz, Zenodo et ClinicalTrials.gov n'ont besoin d'aucune clé ; CORE
  en demande une gratuite (`docs/FUTURE_BACKENDS.md` contient les détails d'API
  revérifiés, le test booléen que chacun a réussi et ce que les offices de
  brevets exigeraient — les contributions d'entrées `backends.json`
  fonctionnelles sont très bienvenues).
- Téléchargement légal de PDF en libre accès à partir des liens Unpaywall
  déjà collectés.
- Envoi vers l'API web de Zotero (une exécution directement dans une
  collection).
- Boule de neige via les points d'accès de références d'OpenAlex/Semantic
  Scholar, et graphes de citations parmi les résultats d'une exécution.

## Tests

```bash
python tests/test_librarian.py
```

305 vérifications, bibliothèque standard uniquement, sans réseau et sans clés
— les backends s'exécutent contre des réponses d'API enregistrées ; les
analyseurs d'ingestion, la fusion du répertoire de recherche, le magasin des
revues et le générateur de rapports contre des répertoires synthétiques — de
sorte que la suite exerce hors ligne les vrais chemins d'analyse, de fusion et
de rendu. La CI l'exécute sur Linux, Windows et macOS sous Python 3.9 et 3.13.

## Skill Claude Code

`SKILL.md` à la racine du dépôt est un skill
[Claude Code](https://claude.com/claude-code) qui apprend à un agent à
exécuter scitech-librarian depuis votre clone — quel script fait quoi, le flux
des clés et des requêtes, et les pièges que tend chaque base de données.
Installez-le en copiant le fichier vers
`~/.claude/skills/literature-search/SKILL.md` ; l'agent trouve alors le clone
via `SCITECH_LIBRARIAN_HOME` (si définie) ou en cherchant `librarian.py`, et
ne copie jamais les scripts dans un projet. La suite de tests vérifie qu'une
copie installée est identique octet pour octet au fichier fourni, de sorte
que le skill ne peut pas dériver de la version qu'il décrit.

## Comment il a été construit

Dans Claude Code, pour un usage réel : la première version a été écrite lors
des séances de revue bibliographique d'un projet de physique de la matière
condensée (mi-août 2026, environ trois jours de travail jusqu'à la v2.2),
durcie en exécutant de vraies vérifications de nouveauté de doctorat —
balayages de 5 000 notices, le blocage d'arXiv, l'écart de déchets d'OpenAlex,
les erreurs de requête de l'interface WoS — industrialisée le 26 août 2026
(moteur de backends déclaratif, suite de tests hors ligne, CI) en une seule
séance, et dotée de son générateur de rapports PRISMA, du répertoire de
recherche, de l'ingestion, des indicateurs des revues et des manuels le
28 août 2026. En termes [CRediT](https://credit.niso.org/) :

| Rôle CRediT | Fabio | Claude |
|---|---|---|
| **Conceptualisation** | Une requête sur toutes les bases de données comme instrument reproductible ; la méthode des nombres comme vérification de nouveauté ; la position stricte sur les conditions d'utilisation (WoS manuel plutôt que scraping) ; le rapport PRISMA à trois niveaux ; le répertoire de recherche comme unité du laboratoire, sources manuelles avec provenance, indicateurs des revues suivis dans le temps | Le schéma de requête structurelle ; le moteur des bases de données en configuration ; le modèle de document du rapport et la chaîne de repli PDF ; la conception du répertoire comme index |
| **Méthodologie** | Discipline de conception des requêtes (« un petit nombre est la découverte — puis lire chaque résultat ») ; sélection des bases de données et stratégie d'accès institutionnel | Quantification des revues déchets ; la correction de limitation des groupes arXiv ; la conception point de reprise après chaque appel |
| **Logiciel** | — | Tout |
| **Validation** | Balayages de nouveauté en direct sur de vraies requêtes de recherche ; a repéré les pièges de grammaire WoS, le blocage d'arXiv, l'écart de nombres OpenAlex/Scopus | La suite hors ligne de 305 vérifications ; CI ; autotests en direct |
| **Investigation** | Le labyrinthe de l'accès institutionnel (CAPES/CAFe, VPN, obtention des clés) | Documentation des API de 8+ bases de données ; analyse du code des concurrents |
| **Rédaction** | Relecture et édition | Première version |
| **Ressources · Supervision · Administration du projet · Obtention de financements** | Tout | — |

## Licence

Apache License 2.0 — voir `LICENSE` et `NOTICE` (en anglais, qui font foi).
Vous pouvez l'utiliser, le modifier et le redistribuer, y compris
commercialement, à condition que la licence et l'avis l'accompagnent ; les
contributions sont acceptées aux mêmes conditions (section 5). Et respectez
les conditions d'utilisation de chaque base de données que vous interrogez ;
cet outil est construit pour en faire le chemin facile.

### Avertissement

Ce logiciel est fourni **en l'état** (« as is »), sans garantie ni condition
d'aucune sorte, expresse ou implicite, y compris, sans s'y limiter, toute
garantie de qualité marchande, d'adéquation à un usage particulier, de titre
ou de non-contrefaçon. En aucun cas l'auteur ne saurait être tenu responsable
de dommages de quelque nature que ce soit — directs, indirects, spéciaux,
accessoires ou consécutifs — ni de toute autre réclamation ou responsabilité,
contractuelle, délictuelle ou autre, découlant du logiciel ou de son
utilisation ou s'y rapportant, même s'il a été averti de la possibilité de
tels dommages (Apache License 2.0, sections 7 et 8). Vous seul êtes
responsable de son utilisation licite, des requêtes que vous exécutez et des
notices que vous conservez, et du respect des conditions d'utilisation et de
la licence de chaque base de données, API et jeu de données auxquels il
accède en votre nom.

Ceci est un projet indépendant. Il n'est ni affilié à, ni approuvé ou soutenu
par OpenAlex, NASA ADS, arXiv, INSPIRE-HEP, Elsevier (Scopus), Clarivate (Web
of Science, JCR), Semantic Scholar, Crossref, CORE, Unpaywall ou SCImago ;
leurs noms ne servent qu'à identifier les services interrogés.
