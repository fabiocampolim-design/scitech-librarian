#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Fabio Campolim
"""
i18n.py -- report languages for scitech-librarian.

The *scaffolding* of a report -- headings, table headers, PRISMA stage names,
checklist items, explanatory paragraphs, suggestions -- can be written in
English (default), Brazilian Portuguese, Spanish, German or French. What the
tool found or was given is never translated: record titles, abstracts,
authors, venues, block names and notes, the exact query strings, backend
names, command-line flags quoted in prose, file names, JSON dumps and the
run log. Console output and every log stay English so that runs made in
different languages are still greppable together.

    import i18n
    _ = i18n.translator("pt-BR")
    _("Search strategy")                     -> 'Estratégia de busca'
    _("Block {n}: {title}", n="A", title=t)  -> 'Bloco A: <t>'
    _.num(12345)                             -> '12.345'

The catalogue is keyed by the English string itself, so English output is
byte-identical with or without a translator, and a missing entry falls back
to English rather than failing. The test suite holds every key to all four
languages. Stdlib only; not a command-line tool.
"""

from __future__ import annotations

import time as _time

LANGS = {"en": "English", "pt-BR": "Português (Brasil)", "es": "Español",
         "de": "Deutsch", "fr": "Français"}
_ALIASES = {"pt": "pt-BR", "pt_br": "pt-BR", "pt-br": "pt-BR", "ptbr": "pt-BR",
            "en-us": "en", "en_us": "en", "en-gb": "en", "es-es": "es", "es_es": "es",
            "es-mx": "es", "de-de": "de", "de_de": "de", "fr-fr": "fr", "fr_fr": "fr",
            "fr-ca": "fr"}
_ORDER = ("pt-BR", "es", "de", "fr")
_THOUSANDS = {"en": ",", "pt-BR": ".", "es": " ", "de": ".", "fr": " "}


def normalize(lang) -> str:
    """'pt', 'PT-br', 'fr_FR', None -> a key of LANGS; ValueError otherwise."""
    if not lang:
        return "en"
    s = str(lang).strip()
    if s in LANGS:
        return s
    low = s.lower()
    for k in LANGS:
        if k.lower() == low:
            return k
    if low in _ALIASES:
        return _ALIASES[low]
    raise ValueError(f"unknown report language {lang!r}; choose from {', '.join(LANGS)}")


def html_lang(lang: str) -> str:
    return normalize(lang)


_MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"),
    "pt-BR": ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
              "setembro", "outubro", "novembro", "dezembro"),
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
           "septiembre", "octubre", "noviembre", "diciembre"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August",
           "September", "Oktober", "November", "Dezember"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
           "septembre", "octobre", "novembre", "décembre"),
}


def date(lang, ymd=None) -> str:
    """A date written out in the language ('31 de agosto de 2026'); today by
    default, or (year, month, day)."""
    lang = normalize(lang)
    if ymd is None:
        ymd = _time.localtime()[:3]
    y, m, d = ymd
    month = _MONTHS[lang][m - 1]
    if lang in ("pt-BR", "es"):
        return f"{d} de {month} de {y}"
    if lang == "de":
        return f"{d}. {month} {y}"
    return f"{d} {month} {y}"                      # en, fr


class Translator:
    """Callable: _(msgid, **kw) -> translated, formatted string."""

    def __init__(self, lang=None):
        self.lang = normalize(lang)

    def __call__(self, msgid: str, **kw) -> str:
        s = msgid
        if self.lang != "en":
            row = _C.get(msgid)
            if row:
                s = row[_ORDER.index(self.lang)] or msgid
        return s.format(**kw) if kw else s

    def num(self, v) -> str:
        """Integer with the language's thousands separator ('--' for None)."""
        if v is None:
            return "--"
        return f"{int(v):,}".replace(",", _THOUSANDS[self.lang])


def translator(lang=None) -> Translator:
    return Translator(lang)


def tr(lang, msgid: str, **kw) -> str:
    return Translator(lang)(msgid, **kw)


def missing(lang: str) -> list:
    """msgids without a translation in `lang` (the suite requires none)."""
    lang = normalize(lang)
    if lang == "en":
        return []
    i = _ORDER.index(lang)
    return [k for k, row in _C.items() if len(row) != len(_ORDER) or not row[i]]


# ---------------------------------------------------------------------------
# Catalogue: English msgid -> (pt-BR, es, de, fr). Placeholders in braces are
# formatted with str.format; keep them identical in every language.
# ---------------------------------------------------------------------------

_C = {
    # --- titles and metadata --------------------------------------------------
    "Literature search report -- {name}": (
        "Relatório de busca bibliográfica -- {name}",
        "Informe de búsqueda bibliográfica -- {name}",
        "Bericht zur Literaturrecherche -- {name}",
        "Rapport de recherche bibliographique -- {name}"),
    "Literature search report -- run {stamp}": (
        "Relatório de busca bibliográfica -- execução {stamp}",
        "Informe de búsqueda bibliográfica -- ejecución {stamp}",
        "Bericht zur Literaturrecherche -- Lauf {stamp}",
        "Rapport de recherche bibliographique -- exécution {stamp}"),
    "Generated by scitech-librarian {version} (report level: {level}). Every number below is "
    "reproducible from the archived {what} `{dir}`.": (
        "Gerado por scitech-librarian {version} (nível do relatório: {level}). Todos os números "
        "abaixo são reproduzíveis a partir do {what} arquivado `{dir}`.",
        "Generado por scitech-librarian {version} (nivel del informe: {level}). Todas las cifras "
        "siguientes son reproducibles a partir del {what} archivado `{dir}`.",
        "Erstellt von scitech-librarian {version} (Berichtsstufe: {level}). Jede Zahl unten ist aus "
        "dem archivierten {what} `{dir}` reproduzierbar.",
        "Généré par scitech-librarian {version} (niveau du rapport : {level}). Chaque nombre "
        "ci-dessous est reproductible à partir du {what} archivé `{dir}`."),
    "research directory": ("diretório de pesquisa", "directorio de investigación",
                           "Forschungsverzeichnis", "répertoire de recherche"),
    "run directory": ("diretório da execução", "directorio de la ejecución",
                      "Laufverzeichnis", "répertoire de l'exécution"),
    "counts only (no records fetched)": (
        "apenas contagens (nenhum registro baixado)", "solo recuentos (no se descargaron registros)",
        "nur Trefferzahlen (keine Datensätze abgerufen)", "décomptes seulement (aucune référence téléchargée)"),
    "full fetch, up to {limit} records per block and backend": (
        "coleta completa, até {limit} registros por bloco e backend",
        "descarga completa, hasta {limit} registros por bloque y backend",
        "vollständiger Abruf, bis zu {limit} Datensätze je Block und Backend",
        "téléchargement complet, jusqu'à {limit} références par bloc et backend"),
    "n/a": ("n/d", "n/d", "k. A.", "s. o."),
    "Search dates": ("Datas das buscas", "Fechas de las búsquedas", "Suchdaten", "Dates des recherches"),
    "Run started": ("Início da execução", "Inicio de la ejecución", "Laufbeginn", "Début de l'exécution"),
    "Project": ("Projeto", "Proyecto", "Projekt", "Projet"),
    "Description": ("Descrição", "Descripción", "Beschreibung", "Description"),
    "Sources": ("Fontes", "Fuentes", "Quellen", "Sources"),
    "{runs} automated run(s), {manual} manual source(s)": (
        "{runs} execução(ões) automatizada(s), {manual} fonte(s) manual(is)",
        "{runs} ejecución(es) automatizada(s), {manual} fuente(s) manual(es)",
        "{runs} automatisierte(r) Lauf/Läufe, {manual} manuelle Quelle(n)",
        "{runs} exécution(s) automatisée(s), {manual} source(s) manuelle(s)"),
    "Duration": ("Duração", "Duración", "Dauer", "Durée"),
    "Query file": ("Arquivo de consultas", "Archivo de consultas", "Abfragedatei", "Fichier de requêtes"),
    "Blocks": ("Blocos", "Bloques", "Blöcke", "Blocs"),
    "Backends / sources": ("Backends / fontes", "Backends / fuentes", "Backends / Quellen", "Backends / sources"),
    "Mode": ("Modo", "Modo", "Modus", "Mode"),
    "Non-curated venue filter": ("Filtro de veículos não curados", "Filtro de fuentes no curadas",
                                 "Filter für nicht kuratierte Quellen", "Filtre des supports non curatés"),
    "off (--keep-junk)": ("desligado (--keep-junk)", "desactivado (--keep-junk)",
                          "aus (--keep-junk)", "désactivé (--keep-junk)"),
    "on": ("ligado", "activado", "an", "activé"),
    "Open-access lookup": ("Consulta de acesso aberto", "Consulta de acceso abierto",
                           "Open-Access-Abfrage", "Recherche de libre accès"),
    "not run": ("não executada", "no ejecutada", "nicht ausgeführt", "non exécutée"),
    "Journal metrics": ("Métricas de periódicos", "Métricas de revistas",
                        "Zeitschriftenmetriken", "Indicateurs des revues"),
    "on file for {n} journals": ("registradas para {n} periódicos", "registradas para {n} revistas",
                                 "für {n} Zeitschriften hinterlegt", "enregistrés pour {n} revues"),
    "none (journals.py fetch)": ("nenhuma (journals.py fetch)", "ninguna (journals.py fetch)",
                                 "keine (journals.py fetch)", "aucun (journals.py fetch)"),
    "Filters": ("Filtros", "Filtros", "Filter", "Filtres"),
    "none": ("nenhum", "ninguno", "keine", "aucun"),
    "Interrupted": ("Interrompida", "Interrumpida", "Abgebrochen", "Interrompue"),
    "yes -- partial run": ("sim -- execução parcial", "sí -- ejecución parcial",
                           "ja -- unvollständiger Lauf", "oui -- exécution partielle"),
    "no": ("não", "no", "nein", "non"),
    "yes": ("sim", "sí", "ja", "oui"),
    "Item": ("Item", "Elemento", "Punkt", "Élément"),
    "Value": ("Valor", "Valor", "Wert", "Valeur"),

    # --- sources (project) ------------------------------------------------------
    "Every search that feeds this report, oldest first. 'New here' counts unique records that no "
    "earlier source had found -- what each search added.": (
        "Todas as buscas que alimentam este relatório, da mais antiga à mais recente. 'Novos aqui' "
        "conta os registros únicos que nenhuma fonte anterior havia encontrado -- o que cada busca "
        "acrescentou.",
        "Todas las búsquedas que alimentan este informe, de la más antigua a la más reciente. "
        "'Nuevos aquí' cuenta los registros únicos que ninguna fuente anterior había encontrado -- "
        "lo que aportó cada búsqueda.",
        "Jede Suche, die in diesen Bericht einfließt, älteste zuerst. 'Neu hier' zählt eindeutige "
        "Datensätze, die keine frühere Quelle gefunden hatte -- was jede Suche beigetragen hat.",
        "Chaque recherche alimentant ce rapport, de la plus ancienne à la plus récente. « Nouvelles "
        "ici » compte les références uniques qu'aucune source antérieure n'avait trouvées -- ce que "
        "chaque recherche a apporté."),
    "Source": ("Fonte", "Fuente", "Quelle", "Source"),
    "Kind": ("Tipo", "Tipo", "Art", "Type"),
    "Date": ("Data", "Fecha", "Datum", "Date"),
    "Method": ("Método", "Método", "Methode", "Méthode"),
    "Records": ("Registros", "Registros", "Datensätze", "Références"),
    "New here": ("Novos aqui", "Nuevos aquí", "Neu hier", "Nouvelles ici"),
    "Label / origin": ("Rótulo / origem", "Etiqueta / origen", "Bezeichnung / Herkunft", "Étiquette / origine"),

    # --- search strategy ----------------------------------------------------------
    "Search strategy": ("Estratégia de busca", "Estrategia de búsqueda", "Suchstrategie", "Stratégie de recherche"),
    "Each block is one structural query -- a conjunction of synonym groups, (a OR b) AND (c OR d) -- "
    "rendered into every backend's native grammar. The strings below are exactly what was sent "
    "(PRISMA-S item 8){tail}": (
        "Cada bloco é uma consulta estrutural -- uma conjunção de grupos de sinônimos, (a OR b) AND "
        "(c OR d) -- traduzida para a gramática nativa de cada backend. As cadeias abaixo são "
        "exatamente o que foi enviado (item 8 do PRISMA-S){tail}",
        "Cada bloque es una consulta estructural -- una conjunción de grupos de sinónimos, (a OR b) "
        "AND (c OR d) -- traducida a la gramática nativa de cada backend. Las cadenas siguientes son "
        "exactamente lo que se envió (ítem 8 de PRISMA-S){tail}",
        "Jeder Block ist eine strukturelle Abfrage -- eine Konjunktion von Synonymgruppen, (a OR b) "
        "AND (c OR d) -- in die native Grammatik jedes Backends übersetzt. Die Zeichenketten unten "
        "wurden genau so gesendet (PRISMA-S Punkt 8){tail}",
        "Chaque bloc est une requête structurelle -- une conjonction de groupes de synonymes, (a OR b) "
        "AND (c OR d) -- traduite dans la grammaire native de chaque backend. Les chaînes ci-dessous "
        "sont exactement ce qui a été envoyé (élément 8 de PRISMA-S){tail}"),
    ", from the most recent run of each block.": (
        ", da execução mais recente de cada bloco.", ", de la ejecución más reciente de cada bloque.",
        ", aus dem jeweils letzten Lauf jedes Blocks.", ", issues de l'exécution la plus récente de chaque bloc."),
    "Block {n}: {title}": ("Bloco {n}: {title}", "Bloque {n}: {title}", "Block {n}: {title}", "Bloc {n} : {title}"),
    "Purpose: {note}": ("Finalidade: {note}", "Propósito: {note}", "Zweck: {note}", "Objectif : {note}"),
    "arXiv receives groups {groups} only (nested-boolean limitation).": (
        "O arXiv recebe apenas os grupos {groups} (limitação de booleanos aninhados).",
        "arXiv recibe solo los grupos {groups} (limitación de booleanos anidados).",
        "arXiv erhält nur die Gruppen {groups} (Einschränkung bei verschachtelten Booleschen Ausdrücken).",
        "arXiv ne reçoit que les groupes {groups} (limitation des booléens imbriqués)."),
    "Backend": ("Backend", "Backend", "Backend", "Backend"),
    "Query string sent": ("Cadeia de consulta enviada", "Cadena de consulta enviada",
                          "Gesendete Abfrage", "Chaîne de requête envoyée"),

    # --- results summary ------------------------------------------------------------
    "Results summary": ("Resumo dos resultados", "Resumen de resultados", "Ergebnisübersicht", "Synthèse des résultats"),
    "Block": ("Bloco", "Bloque", "Block", "Bloc"),
    "Identified": ("Identificados", "Identificados", "Identifiziert", "Identifiées"),
    "Retrieved": ("Recuperados", "Recuperados", "Abgerufen", "Récupérées"),
    "Unique": ("Únicos", "Únicos", "Eindeutig", "Uniques"),
    "Total": ("Total", "Total", "Gesamt", "Total"),
    "Identified = database hit counts (not comparable across backends: proximity operators are "
    "dropped and stemming differs){proj}. Retrieved = records actually downloaded after the venue "
    "filter, capped by `--limit`. Unique = after DOI/title deduplication across all sources.": (
        "Identificados = contagens de acertos das bases (não comparáveis entre backends: operadores "
        "de proximidade são descartados e a radicalização difere){proj}. Recuperados = registros "
        "efetivamente baixados após o filtro de veículos, limitados por `--limit`. Únicos = após a "
        "deduplicação por DOI/título entre todas as fontes.",
        "Identificados = recuentos de aciertos de las bases (no comparables entre backends: se "
        "descartan los operadores de proximidad y la lematización difiere){proj}. Recuperados = "
        "registros realmente descargados tras el filtro de fuentes, limitados por `--limit`. Únicos = "
        "tras la deduplicación por DOI/título entre todas las fuentes.",
        "Identifiziert = Trefferzahlen der Datenbanken (zwischen Backends nicht vergleichbar: "
        "Abstandsoperatoren entfallen, Stemming unterscheidet sich){proj}. Abgerufen = nach dem "
        "Quellenfilter tatsächlich heruntergeladene Datensätze, begrenzt durch `--limit`. Eindeutig = "
        "nach DOI-/Titel-Deduplizierung über alle Quellen.",
        "Identifiées = nombres de résultats des bases (non comparables entre backends : les "
        "opérateurs de proximité sont abandonnés et la lemmatisation diffère){proj}. Récupérées = "
        "références réellement téléchargées après le filtre des supports, plafonnées par `--limit`. "
        "Uniques = après dédoublonnage par DOI/titre sur toutes les sources."),
    "; summed over runs, and for manual sources the number of records ingested": (
        "; somadas entre execuções e, para fontes manuais, o número de registros importados",
        "; sumadas entre ejecuciones y, para fuentes manuales, el número de registros importados",
        "; über Läufe summiert, bei manuellen Quellen die Zahl der importierten Datensätze",
        " ; sommées sur les exécutions et, pour les sources manuelles, le nombre de références importées"),
    "Failed calls: {calls}.": ("Chamadas com falha: {calls}.", "Llamadas fallidas: {calls}.",
                               "Fehlgeschlagene Aufrufe: {calls}.", "Appels en échec : {calls}."),

    # --- timeline -----------------------------------------------------------------------
    "Timeline": ("Linha do tempo", "Cronología", "Zeitverlauf", "Chronologie"),
    "Per-block hit totals in each automated run (sum over backends), oldest first; drift shows how "
    "the indexes -- or the queries -- changed.": (
        "Totais de acertos por bloco em cada execução automatizada (soma dos backends), da mais "
        "antiga à mais recente; a deriva mostra como os índices -- ou as consultas -- mudaram.",
        "Totales de aciertos por bloque en cada ejecución automatizada (suma de los backends), de la "
        "más antigua a la más reciente; la deriva muestra cómo cambiaron los índices -- o las consultas.",
        "Treffersummen je Block in jedem automatisierten Lauf (Summe über Backends), älteste zuerst; "
        "die Drift zeigt, wie sich die Indizes -- oder die Abfragen -- verändert haben.",
        "Totaux de résultats par bloc pour chaque exécution automatisée (somme des backends), de la "
        "plus ancienne à la plus récente ; la dérive montre comment les index -- ou les requêtes -- ont changé."),
    "When records entered the project": ("Quando os registros entraram no projeto",
                                         "Cuándo entraron los registros en el proyecto",
                                         "Wann Datensätze ins Projekt kamen",
                                         "Quand les références sont entrées dans le projet"),
    "Month": ("Mês", "Mes", "Monat", "Mois"),
    "Records first seen": ("Registros vistos pela primeira vez", "Registros vistos por primera vez",
                           "Erstmals gesehene Datensätze", "Références vues pour la première fois"),

    # --- PRISMA ---------------------------------------------------------------------------
    "PRISMA 2020 flow": ("Fluxo PRISMA 2020", "Flujo PRISMA 2020", "PRISMA-2020-Flussdiagramm", "Flux PRISMA 2020"),
    "Records identified from databases": (
        "Registros identificados em bases de dados", "Registros identificados en bases de datos",
        "Über Datenbanken identifizierte Datensätze", "Références identifiées dans les bases de données"),
    "Records identified via other methods": (
        "Registros identificados por outros métodos", "Registros identificados por otros métodos",
        "Über andere Methoden identifizierte Datensätze", "Références identifiées par d'autres méthodes"),
    "Records retrieved (downloaded / ingested)": (
        "Registros recuperados (baixados / importados)", "Registros recuperados (descargados / importados)",
        "Abgerufene Datensätze (heruntergeladen / importiert)", "Références récupérées (téléchargées / importées)"),
    "Removed before screening: automation (non-curated venues)": (
        "Removidos antes da triagem: automação (veículos não curados)",
        "Eliminados antes del cribado: automatización (fuentes no curadas)",
        "Vor der Sichtung entfernt: Automatisierung (nicht kuratierte Quellen)",
        "Retirées avant la sélection : automatisation (supports non curatés)"),
    "Removed before screening: duplicates": (
        "Removidos antes da triagem: duplicatas", "Eliminados antes del cribado: duplicados",
        "Vor der Sichtung entfernt: Duplikate", "Retirées avant la sélection : doublons"),
    "Records to screen (unique)": ("Registros a triar (únicos)", "Registros por cribar (únicos)",
                                   "Zu sichtende Datensätze (eindeutig)", "Références à sélectionner (uniques)"),
    "Records screened": ("Registros triados", "Registros cribados", "Gesichtete Datensätze", "Références examinées"),
    " (assumed = unique)": (" (assumido = únicos)", " (se asume = únicos)",
                            " (angenommen = eindeutig)", " (supposé = uniques)"),
    "Records excluded at screening": ("Registros excluídos na triagem", "Registros excluidos en el cribado",
                                      "Bei der Sichtung ausgeschlossene Datensätze",
                                      "Références exclues à la sélection"),
    "Reports sought for retrieval": ("Relatos buscados para recuperação", "Informes buscados para su recuperación",
                                     "Zur Beschaffung gesuchte Berichte", "Rapports recherchés pour récupération"),
    "Reports not retrieved": ("Relatos não recuperados", "Informes no recuperados",
                              "Nicht beschaffte Berichte", "Rapports non récupérés"),
    "Reports assessed for eligibility": ("Relatos avaliados quanto à elegibilidade",
                                         "Informes evaluados para elegibilidad",
                                         "Auf Eignung geprüfte Berichte", "Rapports évalués pour éligibilité"),
    "  excluded: {reason}": ("  excluídos: {reason}", "  excluidos: {reason}",
                             "  ausgeschlossen: {reason}", "  exclus : {reason}"),
    "Other methods: reports sought": ("Outros métodos: relatos buscados", "Otros métodos: informes buscados",
                                      "Andere Methoden: gesuchte Berichte", "Autres méthodes : rapports recherchés"),
    "Other methods: reports not retrieved": ("Outros métodos: relatos não recuperados",
                                             "Otros métodos: informes no recuperados",
                                             "Andere Methoden: nicht beschaffte Berichte",
                                             "Autres méthodes : rapports non récupérés"),
    "Other methods: reports assessed": ("Outros métodos: relatos avaliados", "Otros métodos: informes evaluados",
                                        "Andere Methoden: geprüfte Berichte", "Autres méthodes : rapports évalués"),
    "  other methods, excluded: {reason}": ("  outros métodos, excluídos: {reason}",
                                            "  otros métodos, excluidos: {reason}",
                                            "  andere Methoden, ausgeschlossen: {reason}",
                                            "  autres méthodes, exclus : {reason}"),
    "Studies included": ("Estudos incluídos", "Estudios incluidos", "Eingeschlossene Studien", "Études incluses"),
    "Reports of included studies": ("Relatos dos estudos incluídos", "Informes de los estudios incluidos",
                                    "Berichte eingeschlossener Studien", "Rapports des études incluses"),
    "Stage": ("Etapa", "Etapa", "Stufe", "Étape"),
    "Automation stages are computed from the data; '--' marks manual stages not yet recorded in "
    "{file}. Note that 'identified' counts hits reported by each database while 'retrieved' is what "
    "was downloaded within `--limit`, so the two differ on large blocks.": (
        "As etapas automáticas são calculadas a partir dos dados; '--' marca etapas manuais ainda não "
        "registradas em {file}. Note que 'identificados' conta os acertos informados por cada base, "
        "enquanto 'recuperados' é o que foi baixado dentro de `--limit`; por isso os dois diferem em "
        "blocos grandes.",
        "Las etapas automáticas se calculan a partir de los datos; '--' marca etapas manuales aún no "
        "registradas en {file}. Nótese que 'identificados' cuenta los aciertos informados por cada "
        "base, mientras que 'recuperados' es lo descargado dentro de `--limit`; por eso ambos difieren "
        "en bloques grandes.",
        "Automatische Stufen werden aus den Daten berechnet; '--' markiert manuelle Stufen, die noch "
        "nicht in {file} erfasst sind. 'Identifiziert' zählt die von jeder Datenbank gemeldeten "
        "Treffer, 'abgerufen' das innerhalb von `--limit` Heruntergeladene; bei großen Blöcken "
        "unterscheiden sich beide.",
        "Les étapes automatiques sont calculées à partir des données ; « -- » marque les étapes "
        "manuelles non encore renseignées dans {file}. « Identifiées » compte les résultats annoncés "
        "par chaque base, « récupérées » ce qui a été téléchargé dans la limite de `--limit` ; les "
        "deux diffèrent donc sur les gros blocs."),
    "PRISMA-S search-reporting checklist": ("Lista de verificação PRISMA-S para relato da busca",
                                            "Lista de verificación PRISMA-S para el informe de la búsqueda",
                                            "PRISMA-S-Checkliste zur Berichterstattung der Suche",
                                            "Liste de contrôle PRISMA-S pour le compte rendu de la recherche"),
    "Requirement": ("Requisito", "Requisito", "Anforderung", "Exigence"),
    "This search": ("Esta busca", "Esta búsqueda", "Diese Suche", "Cette recherche"),

    # PRISMA-S item names (Rethlefsen et al. 2021)
    "Database name": ("Nome da base de dados", "Nombre de la base de datos", "Datenbankname", "Nom de la base de données"),
    "Multi-database searching": ("Busca em múltiplas bases", "Búsqueda en múltiples bases",
                                 "Suche in mehreren Datenbanken", "Recherche multi-bases"),
    "Study registries": ("Registros de estudos", "Registros de estudios", "Studienregister", "Registres d'études"),
    "Online resources and browsing": ("Recursos on-line e navegação", "Recursos en línea y navegación",
                                      "Online-Ressourcen und Browsing", "Ressources en ligne et navigation"),
    "Citation searching": ("Busca por citações", "Búsqueda de citas", "Zitationssuche", "Recherche par citations"),
    "Contacts": ("Contatos", "Contactos", "Kontakte", "Contacts"),
    "Other methods": ("Outros métodos", "Otros métodos", "Andere Methoden", "Autres méthodes"),
    "Full search strategies": ("Estratégias de busca completas", "Estrategias de búsqueda completas",
                               "Vollständige Suchstrategien", "Stratégies de recherche complètes"),
    "Limits and restrictions": ("Limites e restrições", "Límites y restricciones",
                                "Limits und Einschränkungen", "Limites et restrictions"),
    "Search filters": ("Filtros de busca", "Filtros de búsqueda", "Suchfilter", "Filtres de recherche"),
    "Prior work": ("Trabalhos anteriores", "Trabajos previos", "Vorarbeiten", "Travaux antérieurs"),
    "Updates": ("Atualizações", "Actualizaciones", "Aktualisierungen", "Mises à jour"),
    "Dates of searches": ("Datas das buscas", "Fechas de las búsquedas", "Suchdaten", "Dates des recherches"),
    "Peer review": ("Revisão por pares", "Revisión por pares", "Begutachtung", "Relecture par les pairs"),
    "Total records": ("Total de registros", "Total de registros", "Gesamtzahl der Datensätze", "Total des références"),
    "Deduplication": ("Deduplicação", "Deduplicación", "Deduplizierung", "Dédoublonnage"),

    # PRISMA-S automatic values
    "{dbs} (documented public APIs)": ("{dbs} (APIs públicas documentadas)", "{dbs} (API públicas documentadas)",
                                       "{dbs} (dokumentierte öffentliche APIs)", "{dbs} (API publiques documentées)"),
    "; manual database exports: {names}": ("; exportações manuais de bases: {names}",
                                           "; exportaciones manuales de bases: {names}",
                                           "; manuelle Datenbankexporte: {names}",
                                           " ; exports manuels de bases : {names}"),
    "1 database, one structural query per block rendered into each native grammar; see Search strategy": (
        "1 base de dados, uma consulta estrutural por bloco traduzida para a gramática nativa; ver "
        "Estratégia de busca",
        "1 base de datos, una consulta estructural por bloque traducida a la gramática nativa; véase "
        "Estrategia de búsqueda",
        "1 Datenbank, eine strukturelle Abfrage je Block in die native Grammatik übersetzt; siehe "
        "Suchstrategie",
        "1 base de données, une requête structurelle par bloc traduite dans la grammaire native ; voir "
        "Stratégie de recherche"),
    "{n} databases, one structural query per block rendered into each native grammar; see Search strategy": (
        "{n} bases de dados, uma consulta estrutural por bloco traduzida para cada gramática nativa; "
        "ver Estratégia de busca",
        "{n} bases de datos, una consulta estructural por bloque traducida a cada gramática nativa; "
        "véase Estrategia de búsqueda",
        "{n} Datenbanken, eine strukturelle Abfrage je Block in jede native Grammatik übersetzt; siehe "
        "Suchstrategie",
        "{n} bases de données, une requête structurelle par bloc traduite dans chaque grammaire "
        "native ; voir Stratégie de recherche"),
    "none recorded": ("nenhum registrado", "ninguno registrado", "keine erfasst", "aucun enregistré"),
    "not performed": ("não realizada", "no realizada", "nicht durchgeführt", "non effectuée"),
    "reported verbatim per backend under Search strategy; archived in queries.json{tail}": (
        "relatadas literalmente por backend em Estratégia de busca; arquivadas em queries.json{tail}",
        "reportadas literalmente por backend en Estrategia de búsqueda; archivadas en queries.json{tail}",
        "je Backend wörtlich unter Suchstrategie wiedergegeben; archiviert in queries.json{tail}",
        "reproduites mot pour mot par backend sous Stratégie de recherche ; archivées dans queries.json{tail}"),
    " of each run": (" de cada execução", " de cada ejecución", " jedes Laufs", " de chaque exécution"),
    "counts only, no records": ("apenas contagens, sem registros", "solo recuentos, sin registros",
                                "nur Trefferzahlen, keine Datensätze", "décomptes seulement, aucune référence"),
    "record download capped at {limit} per block and backend, most-cited first": (
        "download de registros limitado a {limit} por bloco e backend, mais citados primeiro",
        "descarga de registros limitada a {limit} por bloque y backend, los más citados primero",
        "Datensatzabruf auf {limit} je Block und Backend begrenzt, meistzitierte zuerst",
        "téléchargement des références plafonné à {limit} par bloc et backend, les plus citées d'abord"),
    "; no date, language or document-type limits applied": (
        "; sem limites de data, idioma ou tipo de documento",
        "; sin límites de fecha, idioma ni tipo de documento",
        "; keine Einschränkung nach Datum, Sprache oder Dokumenttyp",
        " ; aucune limite de date, de langue ou de type de document"),
    "; report filters: {filters}": ("; filtros do relatório: {filters}", "; filtros del informe: {filters}",
                                    "; Berichtsfilter: {filters}", " ; filtres du rapport : {filters}"),
    "venue filter {filt}": ("filtro de veículos {filt}", "filtro de fuentes {filt}",
                            "Quellenfilter {filt}", "filtre des supports {filt}"),
    "off": ("desligado", "desactivado", "aus", "désactivé"),
    "on: records from non-curated repositories (Zenodo, Figshare, SSRN...) removed": (
        "ligado: registros de repositórios não curados (Zenodo, Figshare, SSRN...) removidos",
        "activado: registros de repositorios no curados (Zenodo, Figshare, SSRN...) eliminados",
        "an: Datensätze aus nicht kuratierten Repositorien (Zenodo, Figshare, SSRN...) entfernt",
        "activé : références des dépôts non curatés (Zenodo, Figshare, SSRN...) retirées"),
    "{n} earlier run(s) archived; counts tracked in counts_history.csv": (
        "{n} execução(ões) anterior(es) arquivada(s); contagens acompanhadas em counts_history.csv",
        "{n} ejecución(es) anterior(es) archivada(s); recuentos registrados en counts_history.csv",
        "{n} frühere(r) Lauf/Läufe archiviert; Trefferzahlen in counts_history.csv verfolgt",
        "{n} exécution(s) antérieure(s) archivée(s) ; décomptes suivis dans counts_history.csv"),
    "{n} run(s) combined; see Timeline": ("{n} execução(ões) combinada(s); ver Linha do tempo",
                                          "{n} ejecución(es) combinada(s); véase Cronología",
                                          "{n} Lauf/Läufe zusammengeführt; siehe Zeitverlauf",
                                          "{n} exécution(s) combinée(s) ; voir Chronologie"),
    "first run of these blocks": ("primeira execução destes blocos", "primera ejecución de estos bloques",
                                  "erster Lauf dieser Blöcke", "première exécution de ces blocs"),
    "searched on {date}": ("buscado em {date}", "búsqueda realizada el {date}",
                           "gesucht am {date}", "recherche effectuée le {date}"),
    "{n} identified from databases": ("{n} identificados em bases de dados", "{n} identificados en bases de datos",
                                      "{n} über Datenbanken identifiziert", "{n} identifiées dans les bases de données"),
    ", {n} via other methods": (", {n} por outros métodos", ", {n} por otros métodos",
                                ", {n} über andere Methoden", ", {n} par d'autres méthodes"),
    "; {r} retrieved; {u} unique": ("; {r} recuperados; {u} únicos", "; {r} recuperados; {u} únicos",
                                    "; {r} abgerufen; {u} eindeutig", " ; {r} récupérées ; {u} uniques"),
    "exact DOI match, else first 90 characters of the lower-cased title; {n} duplicates removed": (
        "DOI idêntico ou, na falta, os 90 primeiros caracteres do título em minúsculas; {n} duplicatas "
        "removidas",
        "DOI idéntico o, en su defecto, los 90 primeros caracteres del título en minúsculas; {n} "
        "duplicados eliminados",
        "exakte DOI-Übereinstimmung, sonst die ersten 90 Zeichen des kleingeschriebenen Titels; {n} "
        "Duplikate entfernt",
        "DOI identique, sinon les 90 premiers caractères du titre en minuscules ; {n} doublons retirés"),
    "not applicable": ("não se aplica", "no aplicable", "nicht zutreffend", "sans objet"),
    "to be completed": ("a preencher", "por completar", "noch auszufüllen", "à compléter"),

    # --- records ------------------------------------------------------------------------------
    "Top {n} records per block": ("{n} principais registros por bloco", "{n} registros principales por bloque",
                                  "Top {n} Datensätze je Block", "{n} premières références par bloc"),
    "Deduplicated across sources, sorted by {sort}.{tail}": (
        "Deduplicados entre fontes, ordenados por {sort}.{tail}",
        "Deduplicados entre fuentes, ordenados por {sort}.{tail}",
        "Über Quellen dedupliziert, sortiert nach {sort}.{tail}",
        "Dédoublonnées entre sources, triées par {sort}.{tail}"),
    " The complete set is in all_records.csv / .ris of each run.": (
        " O conjunto completo está em all_records.csv / .ris de cada execução.",
        " El conjunto completo está en all_records.csv / .ris de cada ejecución.",
        " Der vollständige Satz liegt in all_records.csv / .ris jedes Laufs.",
        " L'ensemble complet se trouve dans all_records.csv / .ris de chaque exécution."),
    " The complete set is in all_records.csv / .ris.": (
        " O conjunto completo está em all_records.csv / .ris.",
        " El conjunto completo está en all_records.csv / .ris.",
        " Der vollständige Satz liegt in all_records.csv / .ris.",
        " L'ensemble complet se trouve dans all_records.csv / .ris."),
    "Block {n} ({k} unique)": ("Bloco {n} ({k} únicos)", "Bloque {n} ({k} únicos)",
                               "Block {n} ({k} eindeutig)", "Bloc {n} ({k} uniques)"),
    "(no authors)": ("(sem autores)", "(sin autores)", "(keine Autoren)", "(sans auteurs)"),
    "Cited by {k}.": ("Citado por {k}.", "Citado por {k}.", "Zitiert von {k}.", "Cité par {k}."),
    " Found by: {who}.": (" Encontrado por: {who}.", " Encontrado por: {who}.",
                          " Gefunden von: {who}.", " Trouvé par : {who}."),
    " OA: {yn}": (" AA: {yn}", " AA: {yn}", " OA: {yn}", " LA : {yn}"),
    "Abstract: ": ("Resumo: ", "Resumen: ", "Abstract: ", "Résumé : "),
    "Title": ("Título", "Título", "Titel", "Titre"),
    "Authors": ("Autores", "Autores", "Autoren", "Auteurs"),
    "Year": ("Ano", "Año", "Jahr", "Année"),
    "Venue": ("Veículo", "Revista", "Zeitschrift", "Revue"),
    "Cited": ("Citações", "Citas", "Zitiert", "Citations"),
    "DOI": ("DOI", "DOI", "DOI", "DOI"),

    # --- intermediate analyses ------------------------------------------------------------------
    "Source overlap": ("Sobreposição entre fontes", "Solapamiento entre fuentes",
                       "Überschneidung der Quellen", "Recouvrement entre sources"),
    "Found only here": ("Só encontrados aqui", "Solo encontrados aquí", "Nur hier gefunden", "Trouvées ici seulement"),
    "Filtered venues": ("Veículos filtrados", "Fuentes filtradas", "Gefilterte Quellen", "Supports filtrés"),
    "'Found only here' counts unique records no other source returned -- a measure of each database's "
    "marginal contribution.": (
        "'Só encontrados aqui' conta os registros únicos que nenhuma outra fonte retornou -- uma medida "
        "da contribuição marginal de cada base.",
        "'Solo encontrados aquí' cuenta los registros únicos que ninguna otra fuente devolvió -- una "
        "medida de la contribución marginal de cada base.",
        "'Nur hier gefunden' zählt eindeutige Datensätze, die keine andere Quelle geliefert hat -- ein "
        "Maß für den Grenzbeitrag jeder Datenbank.",
        "« Trouvées ici seulement » compte les références uniques qu'aucune autre source n'a "
        "renvoyées -- une mesure de la contribution marginale de chaque base."),
    "Distributions": ("Distribuições", "Distribuciones", "Verteilungen", "Distributions"),
    "Publication year": ("Ano de publicação", "Año de publicación", "Erscheinungsjahr", "Année de publication"),
    "Top venues": ("Principais veículos", "Revistas principales", "Häufigste Zeitschriften", "Principales revues"),
    "Most frequent authors": ("Autores mais frequentes", "Autores más frecuentes",
                              "Häufigste Autorinnen und Autoren", "Auteurs les plus fréquents"),
    "Author": ("Autor", "Autor", "Autor/in", "Auteur"),
    "Open access": ("Acesso aberto", "Acceso abierto", "Open Access", "Libre accès"),
    "{oa} of {n} records with a DOI have a legal open-access copy per Unpaywall ({pct}%).": (
        "{oa} de {n} registros com DOI têm uma cópia legal em acesso aberto segundo o Unpaywall ({pct}%).",
        "{oa} de {n} registros con DOI tienen una copia legal en acceso abierto según Unpaywall ({pct}%).",
        "{oa} von {n} Datensätzen mit DOI haben laut Unpaywall eine legale Open-Access-Kopie ({pct}%).",
        "{oa} des {n} références avec DOI ont une copie légale en libre accès selon Unpaywall ({pct}%)."),
    "Metric: {label} ({metric}), from {dir}/journals/metrics.json (journals.py). Values are kept per "
    "year; OpenAlex figures are snapshots taken in the fetch year (the API serves only current values); "
    "the evolution table shows every year on file for venues that appear in this record set.": (
        "Métrica: {label} ({metric}), de {dir}/journals/metrics.json (journals.py). Os valores são "
        "guardados por ano; os do OpenAlex são instantâneos do ano da coleta (a API só fornece valores "
        "atuais); a tabela de evolução mostra todos os anos registrados para os veículos deste conjunto.",
        "Métrica: {label} ({metric}), de {dir}/journals/metrics.json (journals.py). Los valores se "
        "guardan por año; los de OpenAlex son instantáneas del año de la descarga (la API solo sirve "
        "valores actuales); la tabla de evolución muestra todos los años registrados para las revistas "
        "de este conjunto.",
        "Metrik: {label} ({metric}), aus {dir}/journals/metrics.json (journals.py). Werte werden je "
        "Jahr gehalten; OpenAlex-Werte sind Momentaufnahmen des Abrufjahrs (die API liefert nur "
        "aktuelle Werte); die Verlaufstabelle zeigt jedes hinterlegte Jahr für Zeitschriften dieses "
        "Datensatzes.",
        "Indicateur : {label} ({metric}), issu de {dir}/journals/metrics.json (journals.py). Les "
        "valeurs sont conservées par année ; celles d'OpenAlex sont des instantanés de l'année de "
        "collecte (l'API ne sert que les valeurs courantes) ; la table d'évolution montre chaque année "
        "enregistrée pour les revues de cet ensemble."),
    "Venues in this set by {label}": ("Veículos deste conjunto por {label}", "Revistas de este conjunto por {label}",
                                      "Zeitschriften dieses Satzes nach {label}", "Revues de cet ensemble par {label}"),
    "Q": ("Q", "Q", "Q", "Q"),
    "{label}: evolution": ("{label}: evolução", "{label}: evolución", "{label}: Verlauf", "{label} : évolution"),
    "Years": ("Anos", "Años", "Jahre", "Années"),
    "Filtered non-curated venues": ("Veículos não curados filtrados", "Fuentes no curadas filtradas",
                                    "Gefilterte nicht kuratierte Quellen", "Supports non curatés filtrés"),
    "Records removed": ("Registros removidos", "Registros eliminados", "Entfernte Datensätze", "Références retirées"),
    "Count history": ("Histórico de contagens", "Historial de recuentos", "Verlauf der Trefferzahlen", "Historique des décomptes"),
    "Per-block totals across archived runs (counts_history.csv); drift shows how the indexes -- or "
    "your queries -- changed.": (
        "Totais por bloco nas execuções arquivadas (counts_history.csv); a deriva mostra como os "
        "índices -- ou as suas consultas -- mudaram.",
        "Totales por bloque en las ejecuciones archivadas (counts_history.csv); la deriva muestra cómo "
        "cambiaron los índices -- o sus consultas.",
        "Summen je Block über archivierte Läufe (counts_history.csv); die Drift zeigt, wie sich die "
        "Indizes -- oder Ihre Abfragen -- verändert haben.",
        "Totaux par bloc sur les exécutions archivées (counts_history.csv) ; la dérive montre comment "
        "les index -- ou vos requêtes -- ont changé."),
    "Errors": ("Erros", "Errores", "Fehler", "Erreurs"),

    # --- full dumps ------------------------------------------------------------------------------
    "Per-source raw results (before deduplication)": (
        "Resultados brutos por fonte (antes da deduplicação)", "Resultados brutos por fuente (antes de la deduplicación)",
        "Rohergebnisse je Quelle (vor der Deduplizierung)", "Résultats bruts par source (avant dédoublonnage)"),
    "{stem} ({n} records)": ("{stem} ({n} registros)", "{stem} ({n} registros)",
                             "{stem} ({n} Datensätze)", "{stem} ({n} références)"),
    "Filtered records": ("Registros filtrados", "Registros filtrados", "Gefilterte Datensätze", "Références filtrées"),
    "Backend configuration": ("Configuração dos backends", "Configuración de los backends",
                              "Backend-Konfiguration", "Configuration des backends"),
    "Endpoint": ("Endpoint", "Endpoint", "Endpunkt", "Point d'accès"),
    "Auth": ("Autenticação", "Autenticación", "Auth", "Auth"),
    "Paging": ("Paginação", "Paginación", "Paginierung", "Pagination"),
    "Run log": ("Registro de execução", "Registro de ejecución", "Laufprotokoll", "Journal d'exécution"),
    "Environment": ("Ambiente", "Entorno", "Umgebung", "Environnement"),
    "Python": ("Python", "Python", "Python", "Python"),
    "Platform": ("Plataforma", "Plataforma", "Plattform", "Plateforme"),
    "Tool version": ("Versão da ferramenta", "Versión de la herramienta", "Werkzeugversion", "Version de l'outil"),
    "Report generated": ("Relatório gerado em", "Informe generado el", "Bericht erstellt am", "Rapport généré le"),

    # --- suggestions ------------------------------------------------------------------------------
    "Suggestions": ("Sugestões", "Sugerencias", "Empfehlungen", "Suggestions"),
    "{n} backend call(s) failed ({bad}); rerun those with `--backends {flags}` or exclude them with "
    "`--skip` so the counts table is complete.": (
        "{n} chamada(s) a backend falharam ({bad}); repita-as com `--backends {flags}` ou exclua-as "
        "com `--skip` para que a tabela de contagens fique completa.",
        "{n} llamada(s) a backend fallaron ({bad}); repítalas con `--backends {flags}` o exclúyalas "
        "con `--skip` para que la tabla de recuentos esté completa.",
        "{n} Backend-Aufruf(e) fehlgeschlagen ({bad}); mit `--backends {flags}` wiederholen oder mit "
        "`--skip` ausschließen, damit die Trefferzahlentabelle vollständig ist.",
        "{n} appel(s) de backend en échec ({bad}) ; relancez-les avec `--backends {flags}` ou "
        "excluez-les avec `--skip` pour que la table des décomptes soit complète."),
    "Block {n}: {big} hits -- a generic term is probably driving this; tighten a group or add a more "
    "specific one before reading.": (
        "Bloco {n}: {big} acertos -- provavelmente um termo genérico está por trás disso; restrinja um "
        "grupo ou acrescente um mais específico antes de ler.",
        "Bloque {n}: {big} aciertos -- probablemente un término genérico lo explica; restrinja un grupo "
        "o añada uno más específico antes de leer.",
        "Block {n}: {big} Treffer -- wahrscheinlich treibt ein allgemeiner Begriff das an; eine Gruppe "
        "enger fassen oder eine spezifischere hinzufügen, bevor Sie lesen.",
        "Bloc {n} : {big} résultats -- un terme générique en est probablement la cause ; resserrez un "
        "groupe ou ajoutez-en un plus précis avant de lire."),
    "Block {n}: zero hits on every backend. Either the intersection is genuinely empty (a finding -- "
    "check the synonyms first) or one group is too narrow; try dropping one group and rerunning.": (
        "Bloco {n}: zero acertos em todos os backends. Ou a interseção é realmente vazia (um achado "
        "-- verifique os sinônimos primeiro) ou um grupo é estreito demais; tente remover um grupo e "
        "executar de novo.",
        "Bloque {n}: cero aciertos en todos los backends. O la intersección está realmente vacía (un "
        "hallazgo -- revise primero los sinónimos) o un grupo es demasiado estrecho; pruebe a quitar "
        "un grupo y volver a ejecutar.",
        "Block {n}: null Treffer bei jedem Backend. Entweder ist die Schnittmenge wirklich leer (ein "
        "Befund -- zuerst die Synonyme prüfen) oder eine Gruppe ist zu eng; eine Gruppe weglassen und "
        "erneut ausführen.",
        "Bloc {n} : zéro résultat sur tous les backends. Soit l'intersection est réellement vide (un "
        "constat -- vérifiez d'abord les synonymes), soit un groupe est trop étroit ; essayez de "
        "retirer un groupe et de relancer."),
    "Block {n}: only {tot} hit(s) in total -- novelty-check territory. Read every record by hand "
    "before claiming a gap, and quote the Scopus / Web of Science count in the paper.": (
        "Bloco {n}: apenas {tot} acerto(s) no total -- território de verificação de novidade. Leia cada "
        "registro à mão antes de afirmar uma lacuna e cite a contagem do Scopus / Web of Science no artigo.",
        "Bloque {n}: solo {tot} acierto(s) en total -- territorio de comprobación de novedad. Lea cada "
        "registro a mano antes de afirmar un vacío y cite el recuento de Scopus / Web of Science en el "
        "artículo.",
        "Block {n}: nur {tot} Treffer insgesamt -- Neuheitsprüfung. Jeden Datensatz von Hand lesen, "
        "bevor eine Lücke behauptet wird, und die Scopus-/Web-of-Science-Zahl im Artikel angeben.",
        "Bloc {n} : seulement {tot} résultat(s) au total -- territoire de vérification de nouveauté. "
        "Lisez chaque référence à la main avant d'affirmer une lacune, et citez le décompte Scopus / "
        "Web of Science dans l'article."),
    "Block {n}: counts differ >20x across backends ({lo} to {hi}); grammar and coverage diverge, so "
    "do not compare these numbers -- discover here, quote one source.": (
        "Bloco {n}: as contagens diferem >20x entre backends ({lo} a {hi}); gramática e cobertura "
        "divergem, portanto não compare esses números -- descubra aqui, cite uma única fonte.",
        "Bloque {n}: los recuentos difieren >20x entre backends ({lo} a {hi}); la gramática y la "
        "cobertura divergen, así que no compare estas cifras -- descubra aquí, cite una sola fuente.",
        "Block {n}: Trefferzahlen unterscheiden sich >20x zwischen Backends ({lo} bis {hi}); Grammatik "
        "und Abdeckung weichen ab, diese Zahlen also nicht vergleichen -- hier entdecken, eine Quelle "
        "zitieren.",
        "Bloc {n} : les décomptes diffèrent de plus de 20x entre backends ({lo} à {hi}) ; grammaire et "
        "couverture divergent, ne comparez donc pas ces nombres -- explorez ici, citez une seule source."),
    "This was a counts-only run: no records were fetched, so the record sections and the "
    "deduplicated set are empty. Rerun without `--counts-only` for records, RIS and PRISMA numbers.": (
        "Esta execução foi apenas de contagens: nenhum registro foi baixado, então as seções de "
        "registros e o conjunto deduplicado estão vazios. Execute de novo sem `--counts-only` para "
        "obter registros, RIS e números do PRISMA.",
        "Esta ejecución fue solo de recuentos: no se descargaron registros, así que las secciones de "
        "registros y el conjunto deduplicado están vacíos. Vuelva a ejecutar sin `--counts-only` para "
        "obtener registros, RIS y cifras PRISMA.",
        "Dies war ein reiner Zähllauf: keine Datensätze abgerufen, daher sind die Datensatzabschnitte "
        "und der deduplizierte Satz leer. Ohne `--counts-only` erneut ausführen für Datensätze, RIS und "
        "PRISMA-Zahlen.",
        "Cette exécution ne comptait que les résultats : aucune référence téléchargée, les sections de "
        "références et l'ensemble dédoublonné sont donc vides. Relancez sans `--counts-only` pour les "
        "références, le RIS et les nombres PRISMA."),
    "{n} block/backend pair(s) hit the `--limit` cap ({limit}); raise it (largest total {worst}) if "
    "you need the complete record set rather than the most-cited slice.": (
        "{n} par(es) bloco/backend atingiram o limite `--limit` ({limit}); aumente-o (maior total "
        "{worst}) se precisar do conjunto completo de registros em vez da fatia mais citada.",
        "{n} par(es) bloque/backend alcanzaron el tope `--limit` ({limit}); auméntelo (mayor total "
        "{worst}) si necesita el conjunto completo de registros y no solo los más citados.",
        "{n} Block/Backend-Paar(e) haben die `--limit`-Grenze ({limit}) erreicht; erhöhen (größte "
        "Summe {worst}), wenn Sie den vollständigen Datensatz statt der meistzitierten Auswahl brauchen.",
        "{n} paire(s) bloc/backend ont atteint le plafond `--limit` ({limit}) ; augmentez-le (plus "
        "grand total {worst}) s'il vous faut l'ensemble complet plutôt que la tranche la plus citée."),
    "{b}: {k} of {tot} records ({pct}%) came from non-curated venues and were filtered; its raw count "
    "overstates the curated literature by about that much.": (
        "{b}: {k} de {tot} registros ({pct}%) vieram de veículos não curados e foram filtrados; sua "
        "contagem bruta superestima a literatura curada mais ou menos nessa proporção.",
        "{b}: {k} de {tot} registros ({pct}%) procedían de fuentes no curadas y se filtraron; su "
        "recuento bruto sobreestima la literatura curada aproximadamente en esa proporción.",
        "{b}: {k} von {tot} Datensätzen ({pct}%) stammten aus nicht kuratierten Quellen und wurden "
        "gefiltert; die Rohzahl überschätzt die kuratierte Literatur etwa in diesem Maß.",
        "{b} : {k} des {tot} références ({pct}%) provenaient de supports non curatés et ont été "
        "filtrées ; son décompte brut surestime d'autant la littérature curatée."),
    "No citation-grade backend (Scopus, Web of Science, NASA ADS) was in this search; add ADS (free "
    "token) or Scopus before quoting counts.": (
        "Nenhum backend de nível de citação (Scopus, Web of Science, NASA ADS) participou desta busca; "
        "acrescente o ADS (token gratuito) ou o Scopus antes de citar contagens.",
        "Ningún backend de nivel de citas (Scopus, Web of Science, NASA ADS) participó en esta "
        "búsqueda; añada ADS (token gratuito) o Scopus antes de citar recuentos.",
        "Kein zitationsfähiges Backend (Scopus, Web of Science, NASA ADS) war Teil dieser Suche; ADS "
        "(kostenloses Token) oder Scopus hinzufügen, bevor Zahlen zitiert werden.",
        "Aucun backend de niveau citation (Scopus, Web of Science, NASA ADS) n'a participé à cette "
        "recherche ; ajoutez ADS (jeton gratuit) ou Scopus avant de citer des décomptes."),
    "Open-access status was not looked up; rerun with `--pdfs` (optionally `--pdf-blocks`) to "
    "collect legal OA PDF links via Unpaywall.": (
        "O status de acesso aberto não foi consultado; execute de novo com `--pdfs` (opcionalmente "
        "`--pdf-blocks`) para coletar links legais de PDF em AA via Unpaywall.",
        "No se consultó el estado de acceso abierto; vuelva a ejecutar con `--pdfs` (opcionalmente "
        "`--pdf-blocks`) para recopilar enlaces legales a PDF en AA vía Unpaywall.",
        "Der Open-Access-Status wurde nicht abgefragt; mit `--pdfs` (optional `--pdf-blocks`) erneut "
        "ausführen, um legale OA-PDF-Links über Unpaywall zu sammeln.",
        "Le statut de libre accès n'a pas été consulté ; relancez avec `--pdfs` (éventuellement "
        "`--pdf-blocks`) pour collecter des liens PDF légaux en LA via Unpaywall."),
    "The PRISMA flow's manual stages are empty: fill in {file} (screened / excluded / assessed / "
    "included) and rerun report.py to complete the diagram.": (
        "As etapas manuais do fluxo PRISMA estão vazias: preencha {file} (triados / excluídos / "
        "avaliados / incluídos) e execute report.py de novo para completar o diagrama.",
        "Las etapas manuales del flujo PRISMA están vacías: rellene {file} (cribados / excluidos / "
        "evaluados / incluidos) y vuelva a ejecutar report.py para completar el diagrama.",
        "Die manuellen Stufen des PRISMA-Flusses sind leer: {file} ausfüllen (gesichtet / "
        "ausgeschlossen / geprüft / eingeschlossen) und report.py erneut ausführen, um das Diagramm zu "
        "vervollständigen.",
        "Les étapes manuelles du flux PRISMA sont vides : renseignez {file} (examinées / exclues / "
        "évaluées / incluses) et relancez report.py pour compléter le diagramme."),
    "No journal metrics on file; run `python journals.py fetch` (OpenAlex, no key) to add "
    "impact-factor-like figures and enable `--min-metric`.": (
        "Nenhuma métrica de periódico registrada; execute `python journals.py fetch` (OpenAlex, sem "
        "chave) para acrescentar indicadores do tipo fator de impacto e habilitar `--min-metric`.",
        "No hay métricas de revistas registradas; ejecute `python journals.py fetch` (OpenAlex, sin "
        "clave) para añadir indicadores tipo factor de impacto y habilitar `--min-metric`.",
        "Keine Zeitschriftenmetriken hinterlegt; `python journals.py fetch` (OpenAlex, ohne Schlüssel) "
        "ausführen, um impact-factor-ähnliche Kennzahlen zu ergänzen und `--min-metric` zu aktivieren.",
        "Aucun indicateur de revue enregistré ; lancez `python journals.py fetch` (OpenAlex, sans clé) "
        "pour ajouter des indicateurs de type facteur d'impact et activer `--min-metric`."),
    "Runs {a} and {b} sent identical query strings; PRISMA 'identified' sums both. If one was a "
    "reconnaissance of the same search, hide it with `python project.py exclude {a}` so hits are not "
    "counted twice.": (
        "As execuções {a} e {b} enviaram cadeias de consulta idênticas; o 'identificados' do PRISMA "
        "soma as duas. Se uma foi um reconhecimento da mesma busca, oculte-a com `python project.py "
        "exclude {a}` para que os acertos não sejam contados duas vezes.",
        "Las ejecuciones {a} y {b} enviaron cadenas de consulta idénticas; el 'identificados' de PRISMA "
        "suma ambas. Si una fue un reconocimiento de la misma búsqueda, ocúltela con `python "
        "project.py exclude {a}` para que los aciertos no se cuenten dos veces.",
        "Die Läufe {a} und {b} haben identische Abfragen gesendet; PRISMA 'identifiziert' summiert "
        "beide. War einer eine Erkundung derselben Suche, mit `python project.py exclude {a}` "
        "ausblenden, damit Treffer nicht doppelt zählen.",
        "Les exécutions {a} et {b} ont envoyé des chaînes de requête identiques ; le « identifiées » "
        "de PRISMA additionne les deux. Si l'une était une reconnaissance de la même recherche, "
        "masquez-la avec `python project.py exclude {a}` pour ne pas compter les résultats deux fois."),
    "Every source is an automated run. Records you obtained by hand -- a Zotero export, a reference "
    "list, a Web of Science session -- go in with `python project.py ingest FILE --method "
    "citation|database|...` and then appear in the PRISMA flow's other-methods column.": (
        "Todas as fontes são execuções automatizadas. Registros obtidos à mão -- uma exportação do "
        "Zotero, uma lista de referências, uma sessão no Web of Science -- entram com `python "
        "project.py ingest FILE --method citation|database|...` e passam a aparecer na coluna de "
        "outros métodos do fluxo PRISMA.",
        "Todas las fuentes son ejecuciones automatizadas. Los registros obtenidos a mano -- una "
        "exportación de Zotero, una lista de referencias, una sesión en Web of Science -- entran con "
        "`python project.py ingest FILE --method citation|database|...` y aparecen luego en la columna "
        "de otros métodos del flujo PRISMA.",
        "Jede Quelle ist ein automatisierter Lauf. Von Hand beschaffte Datensätze -- ein Zotero-Export, "
        "ein Literaturverzeichnis, eine Web-of-Science-Sitzung -- kommen mit `python project.py ingest "
        "FILE --method citation|database|...` hinein und erscheinen dann in der Spalte 'andere "
        "Methoden' des PRISMA-Flusses.",
        "Toutes les sources sont des exécutions automatisées. Les références obtenues à la main -- un "
        "export Zotero, une liste de références, une session Web of Science -- entrent avec `python "
        "project.py ingest FILE --method citation|database|...` et apparaissent ensuite dans la "
        "colonne « autres méthodes » du flux PRISMA."),
    "Block {n}: total hits changed from {prev} (run {when}) to {now}; count drift is expected as "
    "indexes grow, but a large jump usually means the query changed -- diff queries.json between "
    "the runs.": (
        "Bloco {n}: o total de acertos passou de {prev} (execução {when}) para {now}; alguma deriva é "
        "esperada à medida que os índices crescem, mas um salto grande geralmente significa que a "
        "consulta mudou -- compare o queries.json das duas execuções.",
        "Bloque {n}: el total de aciertos pasó de {prev} (ejecución {when}) a {now}; cierta deriva es "
        "esperable a medida que crecen los índices, pero un salto grande suele significar que la "
        "consulta cambió -- compare queries.json entre las ejecuciones.",
        "Block {n}: Treffersumme von {prev} (Lauf {when}) auf {now} geändert; Drift ist zu erwarten, "
        "wenn Indizes wachsen, ein großer Sprung bedeutet aber meist eine geänderte Abfrage -- "
        "queries.json der Läufe vergleichen.",
        "Bloc {n} : le total de résultats est passé de {prev} (exécution {when}) à {now} ; une dérive "
        "est attendue à mesure que les index grossissent, mais un grand saut signifie généralement "
        "que la requête a changé -- comparez queries.json entre les exécutions."),
    "Nothing flagged: counts are in a sensible range on every backend and every call succeeded. "
    "Next step is reading the small blocks by hand.": (
        "Nada a sinalizar: as contagens estão em uma faixa razoável em todos os backends e todas as "
        "chamadas tiveram sucesso. O próximo passo é ler os blocos pequenos à mão.",
        "Nada que señalar: los recuentos están en un rango razonable en todos los backends y todas "
        "las llamadas tuvieron éxito. El siguiente paso es leer los bloques pequeños a mano.",
        "Nichts auffällig: Trefferzahlen liegen bei jedem Backend in einem sinnvollen Bereich und jeder "
        "Aufruf war erfolgreich. Nächster Schritt: die kleinen Blöcke von Hand lesen.",
        "Rien à signaler : les décomptes sont dans une plage raisonnable sur chaque backend et chaque "
        "appel a réussi. Prochaine étape : lire les petits blocs à la main."),

    # --- PRISMA flow diagram (render.py) --------------------------------------------------------------
    "(n = {n})": ("(n = {n})", "(n = {n})", "(n = {n})", "(n = {n})"),
    "Records removed before screening:": ("Registros removidos antes da triagem:",
                                          "Registros eliminados antes del cribado:",
                                          "Vor der Sichtung entfernte Datensätze:",
                                          "Références retirées avant la sélection :"),
    "automation tools (venue filter) (n = {n})": ("ferramentas de automação (filtro de veículos) (n = {n})",
                                                  "herramientas de automatización (filtro de fuentes) (n = {n})",
                                                  "Automatisierungswerkzeuge (Quellenfilter) (n = {n})",
                                                  "outils d'automatisation (filtre des supports) (n = {n})"),
    "duplicates removed (n = {n})": ("duplicatas removidas (n = {n})", "duplicados eliminados (n = {n})",
                                     "Duplikate entfernt (n = {n})", "doublons retirés (n = {n})"),
    "Records screened (n = {n})": ("Registros triados (n = {n})", "Registros cribados (n = {n})",
                                   "Gesichtete Datensätze (n = {n})", "Références examinées (n = {n})"),
    "Records excluded (n = {n})": ("Registros excluídos (n = {n})", "Registros excluidos (n = {n})",
                                   "Ausgeschlossene Datensätze (n = {n})", "Références exclues (n = {n})"),
    "Reports sought for retrieval (n = {n})": ("Relatos buscados para recuperação (n = {n})",
                                               "Informes buscados para su recuperación (n = {n})",
                                               "Zur Beschaffung gesuchte Berichte (n = {n})",
                                               "Rapports recherchés pour récupération (n = {n})"),
    "Reports not retrieved (n = {n})": ("Relatos não recuperados (n = {n})", "Informes no recuperados (n = {n})",
                                        "Nicht beschaffte Berichte (n = {n})", "Rapports non récupérés (n = {n})"),
    "Reports assessed for eligibility (n = {n})": ("Relatos avaliados quanto à elegibilidade (n = {n})",
                                                   "Informes evaluados para elegibilidad (n = {n})",
                                                   "Auf Eignung geprüfte Berichte (n = {n})",
                                                   "Rapports évalués pour éligibilité (n = {n})"),
    "Reports excluded:": ("Relatos excluídos:", "Informes excluidos:", "Ausgeschlossene Berichte:", "Rapports exclus :"),
    "Studies included in review (n = {n})": ("Estudos incluídos na revisão (n = {n})",
                                             "Estudios incluidos en la revisión (n = {n})",
                                             "In die Übersichtsarbeit eingeschlossene Studien (n = {n})",
                                             "Études incluses dans la revue (n = {n})"),
    "Reports of included studies (n = {n})": ("Relatos dos estudos incluídos (n = {n})",
                                              "Informes de los estudios incluidos (n = {n})",
                                              "Berichte eingeschlossener Studien (n = {n})",
                                              "Rapports des études incluses (n = {n})"),
    "not retrieved (n = {n})": ("não recuperados (n = {n})", "no recuperados (n = {n})",
                                "nicht beschafft (n = {n})", "non récupérés (n = {n})"),
    "excluded: {r} (n = {n})": ("excluídos: {r} (n = {n})", "excluidos: {r} (n = {n})",
                                "ausgeschlossen: {r} (n = {n})", "exclus : {r} (n = {n})"),
    "IDENTIFICATION": ("IDENTIFICAÇÃO", "IDENTIFICACIÓN", "IDENTIFIKATION", "IDENTIFICATION"),
    "IDENTIFICATION VIA OTHER METHODS": ("IDENTIFICAÇÃO POR OUTROS MÉTODOS", "IDENTIFICACIÓN POR OTROS MÉTODOS",
                                         "IDENTIFIKATION ÜBER ANDERE METHODEN", "IDENTIFICATION PAR D'AUTRES MÉTHODES"),
    "SCREENING": ("TRIAGEM", "CRIBADO", "SICHTUNG", "SÉLECTION"),
    "INCLUDED": ("INCLUÍDOS", "INCLUIDOS", "EINGESCHLOSSEN", "INCLUS"),
    "Identification": ("Identificação", "Identificación", "Identifikation", "Identification"),
    "Screening": ("Triagem", "Cribado", "Sichtung", "Sélection"),
    "Included": ("Incluídos", "Incluidos", "Eingeschlossen", "Inclus"),
}
