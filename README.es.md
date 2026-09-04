# scitech-librarian
<!-- source-digest: b9a5751826afc198 -->

[![Tests](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml/badge.svg)](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Dependencies: stdlib only](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](librarian.py)
[![Plays by the rules](https://img.shields.io/badge/APIs-documented%20%26%20ToS--compliant-blueviolet)](#juega-según-las-reglas)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) · [Português (Brasil)](README.pt-BR.md) · **Español** · [Deutsch](README.de.md) · [Français](README.fr.md)

*Traducción del README en inglés, que es la referencia; los comandos, nombres de archivo, opciones y bloques de código se conservan como en el original.*

**Una consulta, todas las bases de datos académicas — y un directorio de
investigación que recuerda cada búsqueda, cada registro que aportaste a mano,
y escribe el informe PRISMA de todo ello.**

Escribe una consulta estructurada una sola vez; scitech-librarian la traduce a
la sintaxis nativa de ocho bases de datos bibliográficas (OpenAlex, NASA ADS,
arXiv, INSPIRE-HEP, Scopus, Semantic Scholar, Crossref, Web of Science), las
ejecuta todas y archiva la ejecución — registros en bruto, RIS para Zotero, la
cadena de consulta exacta enviada a cada backend, recuentos de resultados — en
un directorio con marca de tiempo que puedes citar. Las ejecuciones se
acumulan en un **directorio de investigación**: una carpeta por proyecto que
también admite registros obtenidos fuera de la herramienta (exportaciones de
Zotero, Mendeley y Web of Science, el RIS de un colega, una lista de
referencias) con su procedencia, conserva métricas de revistas año a año y
produce un **informe de búsqueda bibliográfica** — estrategia de búsqueda,
resultados, **flujo PRISMA 2020 y lista de verificación PRISMA-S**, línea de
tiempo, qué aportó cada búsqueda, métricas de las revistas, sugerencias — para
una ejecución o para todo el proyecto, filtrado por fecha, fuente, base de
datos, año, citas o calidad de la revista, en Markdown, HTML, LaTeX, PDF o
texto plano, con tres niveles de detalle. Un laboratorio mantiene un directorio
por proyecto. Las bases de datos son **configuración, no código**.

Solo biblioteca estándar, sin paso de instalación: cinco scripts —
`librarian.py` (búsqueda), `project.py` (directorio de investigación e
ingesta), `report.py` (informes), `journals.py` (métricas de revistas),
`wos_manual.py` (Web of Science a mano) — más `render.py`, el renderizador
compartido de Markdown/HTML/LaTeX/PDF, e `i18n.py`, el catálogo de idiomas del
informe. Documentación completa: [**Manual del usuario**](docs/USER_MANUAL.es.md)
([HTML](docs/USER_MANUAL.es.html) · [PDF](docs/USER_MANUAL.es.pdf); original en inglés:
[User Manual](docs/USER_MANUAL.md), [HTML](docs/USER_MANUAL.html) · [PDF](docs/USER_MANUAL.pdf));
un [**recorrido**](docs/WALKTHROUGH.md) (en inglés) de un proyecto real, de
principio a PRISMA, ejercita todas las funciones; [JCR import](docs/JCR_IMPORT.md)
cubre el factor de impacto con licencia. ¿Trabajas con un agente de IA?
Entrégale [**AGENTS.md**](AGENTS.md) — las instrucciones completas orientadas
a la máquina — y dile *"lee AGENTS.md y luego haz una comprobación de novedad
sobre X"*.

```bash
python librarian.py --selftest                       # ping every backend; report what works
python librarian.py --counts-only                    # fast: hit counts for every query block
python librarian.py --pdfs                           # full run + legal open-access PDF lookup
python project.py ingest export.ris --name zotero --method citation   # records from outside
python report.py --project --since 2026-06-01 --diff # what the searches since June added
python journals.py fetch                             # venue metrics (OpenAlex, no key)
```

> **Los comentarios son muy bienvenidos.** Si una base de datos se comporta
> mal, un recuento parece erróneo, o has escrito una entrada de
> `backends.json` para una base de datos que no distribuimos, por favor
> [abre una incidencia](https://github.com/fabiocampolim-design/scitech-librarian/issues) —
> las entradas de configuración para nuevas bases de datos son especialmente
> bienvenidas.

**Por qué existe esto.** Una búsqueda bibliográfica que no puedes repetir es
una afirmación que no puedes defender. Las revisiones sistemáticas y las
comprobaciones de novedad ("nadie ha hecho X") dependen de exactamente qué
bases de datos consultaste, con exactamente qué consulta, exactamente qué día
— y ese registro casi nunca sobrevive. Esta herramienta se construyó para las
comprobaciones de novedad de un doctorado en física y conserva ese registro
por construcción: cada ejecución archiva sus consultas, recuentos y registros,
de modo que seis meses después la búsqueda es reproducible y la deriva de los
recuentos es visible.

## Juega según las reglas

Esta herramienta es estricta con los términos de servicio de cada base de
datos que toca — no como letra pequeña, sino como principio de diseño:

- **Solo APIs públicas documentadas.** Nunca hace scraping de una interfaz
  web. Hacer scraping de Web of Science o Scopus infringe sus términos y puede
  suspender el acceso de toda tu institución.
- **Web of Science sin licencia de API es un trabajo manual, así que hicimos
  pequeño el trabajo manual** — `wos_manual.py` prepara cada consulta en la
  gramática propia de WoS, te guía al pegarlas en la interfaz oficial e
  ingiere tus exportaciones RIS de vuelta en el mismo esquema de registros.
  Pegar, exportar, listo.
- **Sin Google Scholar.** No tiene API, y hacerle scraping viola sus términos.
- **Límites de tasa respetados** — pausas por backend (incluidos los ≥3 s
  entre llamadas que pide arXiv) y un correo de contacto en el User-Agent, que
  además te coloca en el "polite pool", más rápido, de OpenAlex/Crossref.
- **PDF solo vía Unpaywall** — copias legales de acceso abierto, nunca elusión
  de muros de pago.
- **Los derechos de acceso se respetan, no se eluden** — los resultados de
  Scopus llegan a través de la suscripción de tu institución (red del campus
  o VPN), y el README documenta cómo funciona realmente ese acceso.

## Funciones

- **Una consulta estructural, ocho gramáticas nativas.** `[[a, b], [c]]`
  significa `(a OR b) AND c`; la sintaxis de cada backend —
  `TITLE-ABS-KEY(...)`, `TS=(...)`, `abs:"..."`, `and` en minúsculas — se
  genera a partir de la misma definición, así que las consultas nunca se
  desincronizan entre bases de datos.
- **Las bases de datos son datos.** Cada backend es una entrada JSON:
  gramática de consulta, endpoint, cabecera de autenticación, estilo de
  paginación y rutas con puntos dentro de la respuesta. `--init-backends`
  escribe los valores por defecto en `backends.json`; edítalo para añadir,
  cambiar o desactivar bases de datos sin tocar código. Solo los motores que
  realmente necesitan código (el feed XML de arXiv) usan un pequeño driver.
- **Todo se archiva.** Cada ejecución escribe un directorio con marca de
  tiempo con registros JSON en bruto, RIS por bloque, un combinado
  desduplicado en CSV/RIS/JSON/BibTeX/CSL-JSON, la cadena de consulta exacta
  enviada a cada backend, recuentos en JSON y una tabla markdown lista para
  pegar, metadatos de la ejecución y un log completo. Los recuentos también
  se añaden a un archivo de historial para que la deriva a lo largo del
  tiempo sea visible.
- **Un directorio de investigación, no un montón de ejecuciones.**
  `project.py` indexa cada ejecución y cada registro que aportas desde fuera
  (RIS, BibTeX, CSV, JSON — Zotero, Mendeley, Web of Science, listas de
  referencias; una carpeta de entrada para colaboradores), conserva la
  procedencia (quién, cuándo, de dónde, método PRISMA), fusiona todo con
  `found_by` / `first_seen` por registro, y `report.py --project` describe
  el proyecto entero: qué aportó cada búsqueda, qué base de datos encontró lo
  que ninguna otra encontró, deriva de los recuentos a lo largo del tiempo,
  y un flujo PRISMA con ambas columnas de identificación. Filtros por
  ventana de fechas, diferencial ("nuevo desde junio"), tipo de fuente, base
  de datos, bloque, año de publicación, citas, métrica de la revista. Un
  directorio por proyecto; un laboratorio tiene varios.
- **Métricas de revistas, año a año.** `journals.py` obtiene la citación
  media a 2 años de OpenAlex (sin clave) y CiteScore/SJR/SNIP de Scopus (con
  clave), importa CSV de SCImago y exportaciones JCR con licencia, guarda los
  valores por año para que la serie se acumule, y alimenta una columna de
  métrica, una tabla de revistas por métrica, una tabla de evolución y
  `--min-metric` en los informes.
- **Logs y auditorías.** Cada script escribe un log de auditoría
  (invocación, versiones, cada aviso) en `<outdir>/logs/`; la salida por
  consola es pequeña por defecto, `--verbose` / `--quiet` / `--log-dir` /
  `--outdir` en todos ellos; `--help` lista cada parámetro con su valor por
  defecto.
- **Un informe de búsqueda bibliográfica, PRISMA incluido.** Cada ejecución
  termina con `report.md` (o HTML / LaTeX / PDF / texto plano): la
  estrategia de búsqueda con la cadena exacta enviada a cada base de datos,
  un resumen de resultados, un **diagrama de flujo PRISMA 2020** cuyas etapas
  automatizables se rellenan desde la ejecución, una lista de verificación
  **PRISMA-S** para el informe de la búsqueda, los mejores registros por
  bloque y sugerencias basadas en reglas (ajusta este bloque, repite ese
  backend, sube el límite, lee estos cinco resultados a mano). Tres niveles —
  `simple`, `intermediate`, `full` — desde un resumen de dos páginas hasta
  cada registro con su resumen y el log completo. Véase
  [Informes y PRISMA](#informes-y-prisma).
- **Informes en cinco idiomas.** `--lang pt-BR|es|de|fr` (por defecto `en`)
  escribe el texto propio del informe — títulos, etapas y diagrama PRISMA,
  lista de verificación, explicaciones, sugerencias — en portugués de Brasil,
  español, alemán o francés. Los registros, las cadenas de consulta, los
  nombres de bloque, los nombres de archivo y los logs nunca se traducen: un
  informe sigue siendo un registro fiel de la búsqueda en cualquier idioma.
- **A prueba de fallos mediante puntos de control.** Los recuentos se guardan
  tras *cada* llamada a la API y Ctrl-C es seguro — un bloqueo al final de
  una ejecución larga no pierde nada.
- **Un filtro de basura con justificantes.** OpenAlex indexa repositorios no
  curados; en una ejecución de 5.146 registros, el 15,3 % de sus registros
  venían de Zenodo, SSRN, Figshare y similares — frente al 0 % de ADS,
  Scopus, Semantic Scholar e INSPIRE. En una consulta decisiva de novedad esa
  fue toda la diferencia entre 16 resultados y 3. Filtrado por defecto;
  `--keep-junk` lo desactiva.
- **Funciona sin ninguna afiliación.** Cinco backends no necesitan clave ni
  institución; ADS solo necesita un token personal gratuito. Sin VPN, sin
  red del campus, sin suscripción — eso solo importa si añades Scopus o la
  API de WoS encima.
- **La física tiene cobertura de primera clase.** NASA ADS e INSPIRE-HEP son
  backends que ninguna herramienta comparable ofrece; para física arbitrada,
  ADS es esencialmente completo.
- **Comprobaciones de novedad como flujo de trabajo.** Diseña bloques de modo
  que un número *pequeño* sea el resultado informativo, ejecuta los mismos
  bloques a lo largo del tiempo, observa los recuentos — y luego lee cada
  resultado a mano antes de afirmar una laguna.
- **Comprobable sin conexión.** 301 comprobaciones se ejecutan sin red y sin
  claves (los backends se ejercitan contra respuestas de API grabadas; el
  directorio de investigación, los analizadores de ingesta, el almacén de
  revistas y el generador de informes contra directorios sintéticos); CI en
  Linux, Windows y macOS, Python 3.9 y 3.13.

## Las bases de datos: para qué sirve realmente cada una

| Base de datos | Clave necesaria | Cobertura | Úsala para | Cuidado con |
|---|---|---|---|---|
| **OpenAlex** | ninguna | ~250 M de obras, incl. preprints | primera pasada, siempre funciona, sin institución | ~15 % de basura no curada — filtrada por defecto |
| **NASA ADS** | token gratuito | física + astronomía arbitradas completas, arXiv integrado | **mejor fuente única para física** | nada grave |
| **arXiv** | ninguna | preprints, todos los campos | trabajos recién publicados | se atraganta con booleanos anidados — véase Trampas |
| **INSPIRE-HEP** | ninguna | HEP, QCD en red, teoría de partículas | literatura invisible para los índices generales | ámbito temático estrecho |
| **Scopus** | clave gratuita + institución | ~27–28 k revistas curadas | recuentos con calidad de cita para artículos | derechos por IP; requiere red del campus o VPN |
| **Semantic Scholar** | ninguna | amplio, buen grafo de citas | contraste | ~1 req/s sin clave |
| **Crossref** | ninguna | metadatos DOI de ~150 M de ítems | resolver DOI | **sin soporte booleano** — recuentos sin sentido, excluido de las ejecuciones por defecto |
| **Web of Science** | con licencia | ~21–22 k revistas curadas | legitimidad convencional | API normalmente sin licencia — usa `wos_manual.py` |

**Si solo configuras dos:** OpenAlex (funciona al instante) y NASA ADS (token
gratuito en 30 segundos). Añade Scopus si necesitas recuentos con calidad de
cita para un artículo. **Comprobación de realidad de la cobertura:** Scopus
indexa un 25–30 % más de revistas que WoS y el 80–85 % de las revistas de WoS
están también en Scopus; para física ADS es esencialmente completo — así que
Scopus + ADS + arXiv es, en la práctica, un superconjunto de WoS.

## Obtener las claves

La herramienta lee sus claves del entorno del proceso. Dos rutas las llevan
allí, y puedes mezclarlas:

- **Un archivo `.env`** — copia `.env.example` a `.env` y rellénalo; el script
  lo lee automáticamente, sin variables de shell que definir. Está ignorado
  por git.
- **Variables de entorno** — expórtalas desde tu shell, defínelas en la
  configuración de tu agente o lanzador, o suminístralas como secretos de CI.
  Tienen precedencia: `.env` sólo rellena lo que no esté ya definido, así que
  si configuras las claves así nunca necesitarás un `.env`.

En cualquier caso, `python librarian.py --list` muestra qué claves llegaron y
`--selftest` demuestra que funcionan.

- **NASA ADS** — <https://ui.adsabs.harvard.edu/user/settings/token>. Inicia
  sesión, genera, pega. El mayor valor por minuto invertido.
- **Scopus / Elsevier** — <https://dev.elsevier.com/apikey/manage>. Gratuita,
  instantánea. La clave te autentica *a ti*; el derecho de acceso viene de la
  suscripción de tu institución, así que conéctate a la red del campus o a la
  VPN (un 401/403 suele indicar un problema de red, no una clave incorrecta).
  **Elsevier no tiene botón de revocación** — una clave filtrada está quemada,
  no desactivada. Opcionalmente pide a tu biblioteca un InstToken, que elimina
  la dependencia de la VPN.
- **Semantic Scholar** — opcional; funciona sin clave a ~1 req/s.
- **Web of Science** — véase el complemento manual más abajo; la gramática
  restringida de la clave Starter hace que la API rara vez valga la pena.

**¿Sin institución? La mayor parte sigue funcionando.** Cinco de los ocho
backends (OpenAlex, arXiv, INSPIRE-HEP, Semantic Scholar, Crossref) no
necesitan clave ni acceso institucional alguno, y NASA ADS solo necesita un
token personal gratuito — así que la herramienta es plenamente utilizable
desde cualquier portátil, sin afiliación y sin VPN. El derecho institucional
solo importa para Scopus (y la API de WoS con licencia): ahí la clave te
autentica *a ti*, pero los resultados fluyen por la suscripción de tu
institución, que suele ser por IP — conéctate a la red institucional, o usa
la VPN, el proxy o el inicio de sesión federado que tu institución ofrezca,
antes de que la API devuelva algo. La prueba es siempre la misma: ejecuta
`--selftest` y mira si Scopus devuelve un número plausible.

## Escribir consultas

Las consultas viven en `queries.json` (copia `queries.example.json` y edítalo):

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

`groups` es una conjunción de disyunciones. `arxiv_groups` indica
opcionalmente qué grupos (dos como máximo) van a arXiv, que se degrada con
booleanos profundamente anidados. El bloque más valioso suele ser una
intersección deliberada de dos literaturas que sospechas que no se hablan —
un resultado cercano a cero es un hallazgo, no un fallo, *si* después lees
cada resultado a mano.

## Añadir una base de datos (sin código)

```bash
python librarian.py --init-backends     # writes backends.json (next to .env) for editing
```

Una entrada de backend declara la gramática de consulta, la petición y dónde
viven los datos en la respuesta:

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

Estilos de paginación: `cursor`, `page`, `offset`, `none`. La autenticación es
una variable de entorno asignada a una cabecera. Las rutas de campo admiten
indexación `[0]`, mapeo `[]` sobre listas, alternativas `a|b` y
transformaciones con nombre. `docs/FUTURE_BACKENDS.md` tiene puntos de partida
verificados para Europe PMC, CORE, DOAJ, OpenAIRE, DBLP y PubMed. Las entradas
de `backends.json` se superponen a los valores por defecto integrados por
nombre; `"disabled": true` elimina una.

## Web of Science, la situación honesta

La gramática completa `TS=`/`NEAR` vive en la **Expanded API**, con licencia
aparte, que los acuerdos de los consorcios nacionales normalmente no incluyen;
el nivel gratuito **Starter** rechaza los booleanos complejos. Si tu biblioteca
no puede conseguirte credenciales Expanded, WoS es un trabajo manual — y
`wos_manual.py` lo hace pequeño:

```bash
python wos_manual.py prep      # query files + CHECKLIST.md, in WoS grammar
python wos_manual.py walk      # copies each query to your clipboard in turn
python wos_manual.py ingest    # parses your RIS exports into the same schema
python wos_manual.py status    # what you have collected so far
```

La lista de verificación codifica los ajustes de la interfaz que rompen
consultas silenciosamente (Core Collection y no All Databases; Advanced y no
Basic; qué ediciones; forma etiquetada `TS=(...)` frente a forma desnuda —
pegar una consulta etiquetada en un campo elegido por desplegable da *"Search
Error: Invalid query"*). `ingest` fusiona los resultados manuales con los
automatizados, mismo esquema, mismo análisis.

## Cómo se compara

[findpapers](https://github.com/jonatasgrosman/findpapers) es la herramienta
más cercana: una consulta booleana en ocho bases de datos (IEEE y PubMed
incluidas), con desduplicación, refinamiento y descarga de PDF — una buena
opción para revisiones sistemáticas al estilo de la ingeniería de software en
Python 3.11+. [litstudy](https://github.com/NLeSC/litstudy) analiza una
colección que ya tienes (bibliometría, grafos de red, temas) en Jupyter.
[paperscraper](https://github.com/jannisborn/paperscraper) está hecho para
ciencias de la vida (PubMed + servidores de preprints) con herramientas de
factor de impacto y de volcados.

El nicho de esta herramienta: **el instrumento de búsqueda reproducible.** Un
solo archivo sin instalación; la única con NASA ADS e INSPIRE-HEP (física);
ejecuciones archivadas y citables con cadenas de consulta exactas e historial
de recuentos; bases de datos como configuración del usuario; y una postura
estricta de solo APIs documentadas (tanto findpapers como esta herramienta
usan la API oficial WoS Starter; paperscraper hace scraping de Google Scholar
— nosotros nos negamos). Si necesitas IEEE/PubMed hoy o recolección de PDF
dentro de la herramienta, usa findpapers; si necesitas grafos bibliométricos,
litstudy; para búsquedas auditables y cobertura de física, esta.

## Trampas en las que caímos, para que tú no caigas

(El [Manual del usuario](docs/USER_MANUAL.es.md) §12 lista todas las funciones
y todas las limitaciones conocidas en un solo lugar.)

- **arXiv se cuelga con booleanos profundamente anidados** — no es un error,
  simplemente nunca responde. Se envían como máximo dos grupos
  (`arxiv_groups` elige cuáles), por HTTPS, con un tiempo de espera corto,
  porque una heurística automática de "más selectivo" eligió mal.
- **Los recuentos no son comparables entre backends.** Los operadores de
  proximidad se descartan y el stemming difiere. Descubre aquí; cita
  WoS/Scopus en el artículo.
- **El `cmd.exe` de Windows no trata `#` como comentario** — un `# nota`
  pegado al final se convierte en un error de argparse. Usa PowerShell o
  quita el comentario.
- **Unpaywall es una llamada HTTP por DOI** (~20 min para 3.000). Restringe
  con `--pdf-blocks`; los resultados se guardan en caché entre ejecuciones.

## Salida

Cada ejecución escribe `lit/runs/<timestamp>/`:

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

más `lit/counts_history.csv`, ampliado en cada ejecución, y el directorio de
investigación a su alrededor:

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

## El directorio de investigación

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

Los registros externos llegan de tres maneras: por la línea de comandos (con
procedencia completa), por una carpeta de entrada (suelta e ingiere), o por la
rutina de Web of Science. Conservan el archivo original, reciben el esquema
común de registros, se etiquetan `manual:<name>`, y su `--method` (database,
citation, website, organisation, expert, other) los sitúa en el flujo PRISMA.
Las fuentes manuales aparecen en todas las tablas como una base de datos más —
incluida "encontrado solo aquí", que es como descubres qué tenía la lista de
referencias de tu colega que seis bases de datos no tenían.

## Informes y PRISMA

Una búsqueda que no puedes informar es una búsqueda que no puedes defender,
así que cada ejecución termina con un informe. `--report-level` elige el
detalle, `--report-format` los archivos; `report.py` vuelve a renderizar
cualquier ejecución archivada sin tocar la red.

| Nivel | Qué obtienes |
|---|---|
| `simple` (por defecto) | metadatos de la ejecución; fuentes (proyecto); estrategia de búsqueda (consulta estructural + la cadena exacta enviada a cada backend); resumen de resultados; línea de tiempo (proyecto); flujo PRISMA 2020 + lista PRISMA-S; 10 mejores registros por bloque; sugerencias |
| `intermediate` | + cada registro único; la contribución marginal de cada fuente ("encontrado solo aquí"); distribuciones por año / revista / autor; métricas de revistas y su evolución; revistas eliminadas por el filtro; errores; estadísticas de acceso abierto; deriva de recuentos frente a ejecuciones anteriores |
| `full` | + cada registro con resumen y lista de autores completos, y qué fuentes lo encontraron; listas en bruto por fuente antes de la desduplicación; los registros filtrados; configuración de endpoints de los backends; archivos de procedencia del proyecto y de las fuentes; el log completo de la ejecución; entorno |

Formatos: `md`, `html` (autocontenido, claro/oscuro, imprimible), `tex`,
`pdf`, `txt`. El PDF se compila desde el LaTeX con xelatex / lualatex /
pdflatex si hay alguno instalado, si no con pandoc, si no con un escritor
integrado sin dependencias — la opción nunca falla, solo se degrada la
tipografía.

**Idiomas.** `report.py --lang` y `librarian.py --report-lang` aceptan `en`
(por defecto), `pt-BR`, `es`, `de` o `fr`; un directorio de investigación
puede fijar `"defaults": {"lang": "pt-BR"}` en `project.json`. Solo se traduce
el armazón del informe — títulos, cabeceras de tabla, las etapas PRISMA 2020 y
el diagrama de flujo en todos los formatos, la lista PRISMA-S, el texto
explicativo, las sugerencias, los separadores de millares. Todo lo que la
herramienta encontró o recibió se reproduce tal cual: títulos, resúmenes,
autores, revistas, nombres y notas de bloque, las cadenas de consulta exactas,
nombres de backend, opciones, nombres de archivo, volcados JSON y el log de la
ejecución incrustado. `run.log`, los logs de auditoría y la consola permanecen
en inglés sea cual sea el idioma del informe. Ejemplo:
[`samples/pt-BR/report.md`](samples/pt-BR/report.md).

**PRISMA.** El informe lleva un diagrama de flujo
[PRISMA 2020](https://www.prisma-statement.org/) (SVG en HTML, TikZ en
LaTeX/PDF, ASCII en Markdown/texto). Las etapas que una herramienta puede
conocer se rellenan desde los datos — registros identificados por base de
datos, registros identificados por otros métodos (fuentes manuales por
método), registros eliminados por automatización (el filtro de revistas),
duplicados eliminados, registros pendientes de cribar — y son honestas sobre
la diferencia entre *identificados* (lo que informa cada base de datos) y
*recuperados* (lo que se descargó dentro de `--limit`). Las etapas que solo
un humano puede conocer — cribados, excluidos, buscados, evaluados,
incluidos, con motivos de exclusión, para ambas columnas — se leen de
`prisma.json` (una ejecución) o `screening.json` (directorio de
investigación); se escribe una plantilla en el primer informe, así que
rellénala a medida que cribas y vuelve a ejecutar `report.py`. Una lista de
verificación [PRISMA-S](https://doi.org/10.1186/s13643-020-01542-z) para el
informe de la búsqueda (los 16 ítems) se completa automáticamente donde la
herramienta tiene los datos — bases de datos, estrategias completas, límites,
filtros, fechas, totales, método de desduplicación, actualizaciones — y marca
el resto como "por completar".

```bash
python librarian.py --report-level intermediate --report-format md html
python report.py lit/runs/20260815T095908 --level full --format pdf
python report.py --latest --format txt            # newest run, plain text
python librarian.py --no-report                   # search only
```

Filtros de informe (ambos modos): `--since/--until DATE`, `--latest`,
`--diff`, `--year-from/--year-to`, `--backends`, `--blocks`,
`--sources auto|manual|all`, `--records FILE…` (RIS/BibTeX/CSV/JSON extra
solo para este informe), `--metric NAME --min-metric X`, `--min-citations N`,
`--oa-only`, `--top N`, `--sort cited|year|metric`. Los filtros se imprimen en
los metadatos del informe y en el ítem 9 de PRISMA-S, para que un informe
filtrado nunca se confunda con la búsqueda completa.

## Métricas de revistas

```bash
python journals.py fetch                                   # every journal seen in lit/: OpenAlex (+ Scopus with a key)
python journals.py import-scimago scimagojr_2024.csv --year 2024 --all
python journals.py import-csv jcr.csv --provider jcr_if --year 2023 --name-col "Journal name" --value-col JIF
python journals.py show --metric scopus_citescore
```

`lit/journals/metrics.json` mantiene una entrada por revista (indexada por
ISSN) con valores **por año, nunca sobrescritos** — vuelve a obtenerlos el año
que viene y el informe muestra la serie. Proveedores: citación media a 2 años
e índice h de OpenAlex (sin clave; instantánea por año de obtención),
CiteScore / SJR / SNIP de Scopus (clave; historial completo), SJR / índice H /
cuartil de SCImago (una descarga CSV por año, la vía a *todas* las ~30.000
revistas), y el Journal Impact Factor de Clarivate — propietario, sin API
gratuita, solo importación desde una exportación con licencia. La herramienta
no le hará scraping.

### Informes de ejemplo

[`samples/`](samples/) contiene una ejecución real de los cuatro bloques de
ejemplo de `queries.example.json` contra las tres bases de datos **con
licencia CC0** (OpenAlex, arXiv, INSPIRE-HEP; 2026-08-28: 5.705 resultados
identificados, 1.286 registros recuperados, 1.226 únicos) renderizada en
todos los niveles y todos los formatos — `simple` tiene 6 páginas,
`intermediate` 68, `full` 427. Extractos de los PDF:

| `simple`, p. 1 — metadatos de la ejecución y estrategia de búsqueda | `simple`, p. 3 — flujo PRISMA 2020 |
|---|---|
| [![](samples/img/simple_p1.png)](samples/simple/report.pdf) | [![](samples/img/simple_p3.png)](samples/simple/report.pdf) |

| `simple`, p. 2 — consulta exacta por backend, recuentos | `full` — registros con resúmenes |
|---|---|
| [![](samples/img/simple_p2.png)](samples/simple/report.pdf) | [![](samples/img/full_records.png)](samples/full/report.pdf) |

Explora: [simple](samples/simple/report.md) ·
[intermediate](samples/intermediate/report.md) ·
[full](samples/full/report.md) (Markdown, renderizado por GitHub), o el
`.html`, `.tex`, `.pdf`, `.txt` junto a cada uno;
[`samples/pt-BR/`](samples/pt-BR/) es el informe `simple` de la misma
ejecución en portugués de Brasil (`--lang pt-BR`).

[`samples/project/`](samples/project/) es el mismo ejemplo como **directorio
de investigación**: dos ejecuciones (una primera pasada solo con OpenAlex y la
ejecución CC0 completa) más la lista de referencias de un colega ingerida como
fuente manual, con la citación media a 2 años de OpenAlex registrada para 103
revistas — `report.md/html/tex/pdf/txt` (simple), `report_intermediate.md` y
`report_diff.md` (`--since 2026-08-28 --diff`).

| `project`, p. 1 — fuentes y qué aportó cada una | `project`, p. 3 — PRISMA con ambas columnas de identificación |
|---|---|
| [![](samples/img/project_p1.png)](samples/project/report.pdf) | [![](samples/img/project_prisma.png)](samples/project/report.pdf) |

**Por qué solo tres bases de datos en los ejemplos.** OpenAlex, arXiv e
INSPIRE publican sus metadatos bajo CC0, así que sus registros — resúmenes
incluidos — pueden redistribuirse aquí. Los datos de Scopus, NASA ADS y
Semantic Scholar vienen bajo sus propios términos de API (Scopus: sin
redistribución fuera de tu institución; Semantic Scholar: ODC-BY), así que los
informes construidos sobre ellos son para tu propio directorio de
investigación, no para un repositorio público. La herramienta ejecuta las
ocho; los ejemplos muestran tres.

## Referencia de comandos

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

Todos los scripts: `--help` lista cada parámetro con su valor por defecto;
`--outdir`, `--verbose`, `--quiet`, `--log-dir` son comunes a todos.

## Un flujo de trabajo que funciona

1. Escribe 5–10 bloques; incluye al menos una consulta cruzada deliberada
   entre literaturas que sospechas desconectadas.
2. `--selftest`, luego `--counts-only` para ver la forma de cada campo.
3. Ajusta todo lo que devuelva miles de resultados — una palabra genérica
   suele ser la culpable.
4. Ejecución completa con `--pdfs`; importa el RIS en Zotero. Lee `report.md`.
5. **Lee cada resultado de tus bloques pequeños a mano** antes de afirmar una
   laguna; anota lo que cribaste y conservaste en `prisma.json` y vuelve a
   renderizar el informe — el diagrama de flujo queda entonces listo para el
   material suplementario del artículo.
6. Explora las listas de referencias de los PDF en busca de trabajos que
   todos citan y tú no tienes — eso atrapa lo que la búsqueda por palabras
   clave pasa por alto, y atrapó las dos referencias más importantes del
   proyecto para el que se construyó esto.

O delega el ciclo: plantea tu pregunta de investigación a un agente de IA
(Claude Code o similar) y pídele que redacte el `queries.json`, ejecute los
barridos y recorra contigo los resultados archivados. El archivo de consulta
estructurado, la configuración JSON y los directorios de ejecución con marca
de tiempo son deliberadamente fáciles de escribir y auditar por un agente —
esta herramienta se construyó dentro de exactamente ese flujo de trabajo.

## Hoja de ruta

- Más bases de datos como configuración: Europe PMC, CORE, DOAJ, OpenAIRE,
  DBLP, PubMed (`docs/FUTURE_BACKENDS.md` tiene los detalles de API
  verificados — las contribuciones de entradas de `backends.json` que
  funcionen son muy bienvenidas).
- Descarga legal de PDF de acceso abierto desde los enlaces de Unpaywall ya
  recopilados.
- Envío a la API web de Zotero (una ejecución directa a una colección).
- Bola de nieve mediante los endpoints de referencias de OpenAlex/Semantic
  Scholar, y grafos de citas entre los resultados de una ejecución.

## Pruebas

```bash
python tests/test_librarian.py
```

301 comprobaciones, solo biblioteca estándar, sin red y sin claves — los
backends se ejecutan contra respuestas de API grabadas; los analizadores de
ingesta, la fusión del directorio de investigación, el almacén de revistas y
el generador de informes contra directorios sintéticos — de modo que la suite
ejercita sin conexión las rutas reales de análisis, fusión y renderizado. La
CI la ejecuta en Linux, Windows y macOS bajo Python 3.9 y 3.13.

## Skill para Claude Code

`SKILL.md` en la raíz del repositorio es una skill de
[Claude Code](https://claude.com/claude-code) que enseña a un agente a ejecutar
scitech-librarian desde tu clon — qué script hace qué, el flujo de claves y
consultas, y las trampas que tiende cada base de datos. Instálala copiando el
archivo a `~/.claude/skills/literature-search/SKILL.md`; el agente localiza
entonces el clon mediante `SCITECH_LIBRARIAN_HOME` (si está definida) o
buscando `librarian.py`, y nunca copia los scripts dentro de un proyecto. La
suite de pruebas comprueba que una copia instalada es idéntica byte a byte al
archivo distribuido, de modo que la skill no puede alejarse de la versión que
describe.

## Cómo se construyó

En Claude Code, para uso real: la primera versión se escribió en las sesiones
de revisión bibliográfica de un proyecto de física de la materia condensada
(mediados de agosto de 2026, unos tres días de trabajo hasta la v2.2), se
endureció ejecutando comprobaciones de novedad reales de doctorado — barridos
de 5.000 registros, el cuelgue de arXiv, la discrepancia de basura de
OpenAlex, errores de consulta en la interfaz de WoS — se productizó el 26 de
agosto de 2026 (motor declarativo de backends, suite de pruebas sin conexión,
CI) en una sola sesión, y recibió su generador de informes PRISMA, el
directorio de investigación, la ingesta, las métricas de revistas y los
manuales el 28 de agosto de 2026. En términos de
[CRediT](https://credit.niso.org/):

| Rol CRediT | Fabio | Claude |
|---|---|---|
| **Conceptualización** | Una consulta en todas las bases de datos como instrumento reproducible; el método de recuentos como comprobación de novedad; la postura estricta sobre los términos de servicio (WoS manual en vez de scraping); el informe PRISMA de tres niveles; el directorio de investigación como unidad del laboratorio, fuentes manuales con procedencia, métricas de revistas seguidas en el tiempo | El esquema de consulta estructural; el motor de bases de datos como configuración; el modelo de documento del informe y la cadena de respaldo del PDF; el diseño del directorio como índice |
| **Metodología** | Disciplina de diseño de consultas ("un número pequeño es el hallazgo — luego lee cada resultado"); selección de bases de datos y estrategia de acceso institucional | Cuantificación de revistas basura; la corrección de limitación de grupos de arXiv; el diseño de punto de control tras cada llamada |
| **Software** | — | Todo |
| **Validación** | Barridos de novedad en vivo sobre consultas de investigación reales; detectó las trampas de la gramática de WoS, el cuelgue de arXiv, la discrepancia de recuentos OpenAlex/Scopus | La suite sin conexión de 301 comprobaciones; CI; autopruebas en vivo |
| **Investigación** | El laberinto del acceso institucional (CAPES/CAFe, VPN, obtención de claves) | Documentación de API de 8+ bases de datos; análisis del código de la competencia |
| **Redacción** | Revisión y edición | Borrador original |
| **Recursos · Supervisión · Administración del proyecto · Obtención de financiación** | Todo | — |

## Licencia

Apache License 2.0 — véanse `LICENSE` y `NOTICE` (en inglés, que prevalecen).
Puedes usarlo, modificarlo y redistribuirlo, también comercialmente, siempre
que la licencia y el aviso lo acompañen; las contribuciones se aceptan en los
mismos términos (sección 5). Y respeta los términos de servicio de cada base
de datos que consultes; esta herramienta está hecha para que ese sea el camino
fácil.

### Exención de responsabilidad

Este software se proporciona **tal cual** ("as is"), sin garantías ni
condiciones de ningún tipo, expresas o implícitas, incluida, sin limitación,
cualquier garantía de comerciabilidad, idoneidad para un fin determinado,
titularidad o no infracción. En ningún caso el autor será responsable de daños
de ninguna naturaleza — directos, indirectos, especiales, incidentales o
consecuentes — ni de ninguna otra reclamación o responsabilidad, ya sea
contractual, extracontractual o de otro tipo, que surja de, se origine en o se
relacione con el software o su uso, incluso si se ha advertido de la
posibilidad de tales daños (Apache License 2.0, secciones 7 y 8). Tú eres el
único responsable de usarlo legalmente, de las consultas que ejecutas y de los
registros que conservas, y de cumplir los términos de servicio y la licencia de
cada base de datos, API y conjunto de datos a los que accede en tu nombre.

Este es un proyecto independiente. No está afiliado, respaldado ni apoyado por
OpenAlex, NASA ADS, arXiv, INSPIRE-HEP, Elsevier (Scopus), Clarivate (Web of
Science, JCR), Semantic Scholar, Crossref, CORE, Unpaywall ni SCImago; sus
nombres se usan únicamente para identificar los servicios que consulta.
