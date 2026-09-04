# scitech-librarian
<!-- source-digest: 44343a37e1c07e63 -->

[![Tests](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml/badge.svg)](https://github.com/fabiocampolim-design/scitech-librarian/actions/workflows/tests.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Dependencies: stdlib only](https://img.shields.io/badge/dependencies-stdlib%20only-brightgreen)](librarian.py)
[![Plays by the rules](https://img.shields.io/badge/APIs-documented%20%26%20ToS--compliant-blueviolet)](#joga-pelas-regras)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

[English](README.md) · **Português (Brasil)** · [Español](README.es.md) · [Deutsch](README.de.md) · [Français](README.fr.md)

*Tradução do README em inglês, que é a referência; comandos, nomes de arquivos, opções e blocos de código ficam como no original.*

**Uma consulta, todas as bases acadêmicas — e um diretório de pesquisa que
lembra cada busca, cada registro que você trouxe à mão, e escreve o relatório
PRISMA de tudo isso.**

Escreva uma consulta estruturada uma vez; o scitech-librarian a traduz para a
sintaxe nativa de nove bases bibliográficas (OpenAlex, NASA ADS, arXiv,
INSPIRE-HEP, Scopus, Semantic Scholar, Crossref, CORE, Web of Science), executa todas
e arquiva a rodada — registros brutos, RIS para o Zotero, a string de consulta
exata enviada a cada backend, contagens de resultados — em um diretório com
carimbo de data e hora que você pode citar. As rodadas se acumulam em um
**diretório de pesquisa**: uma pasta por projeto que também recebe registros
obtidos fora da ferramenta (exportações do Zotero, Mendeley e Web of Science, o
RIS de um colega, uma lista de referências) com sua proveniência, mantém
métricas de periódicos ano a ano e produz um **relatório de busca
bibliográfica** — estratégia de busca, resultados, **fluxo PRISMA 2020 e
checklist PRISMA-S**, linha do tempo, o que cada busca acrescentou, métricas
de veículos, sugestões — para uma rodada ou para o projeto inteiro, filtrado
por data, fonte, base, ano, citações ou qualidade do veículo, em Markdown,
HTML, LaTeX, PDF ou texto puro, em três níveis de detalhe. Um laboratório
mantém um diretório por projeto. As bases são **configuração, não código**.

Somente a biblioteca padrão, sem etapa de instalação: cinco scripts —
`librarian.py` (busca), `project.py` (diretório de pesquisa e ingestão),
`report.py` (relatórios), `journals.py` (métricas de veículos), `wos_manual.py`
(Web of Science à mão) — mais `render.py`, o renderizador compartilhado de
Markdown/HTML/LaTeX/PDF, e `i18n.py`, o catálogo de idiomas do relatório.
Documentação completa: [**Manual do Usuário**](docs/USER_MANUAL.pt-BR.md)
([HTML](docs/USER_MANUAL.pt-BR.html) · [PDF](docs/USER_MANUAL.pt-BR.pdf); original em inglês:
[User Manual](docs/USER_MANUAL.md), [HTML](docs/USER_MANUAL.html) · [PDF](docs/USER_MANUAL.pdf));
um [**passo a passo**](docs/WALKTHROUGH.md) (em inglês) de um projeto real, do
início ao PRISMA, exercita todos os recursos; [JCR import](docs/JCR_IMPORT.md)
cobre o Fator de Impacto licenciado. Trabalhando com um agente de IA? Entregue
a ele o [**AGENTS.md**](AGENTS.md) — as instruções completas orientadas à
máquina — e diga *"leia o AGENTS.md e depois faça uma verificação de novidade
sobre X"*.

```bash
python librarian.py --selftest                       # ping every backend; report what works
python librarian.py --counts-only                    # fast: hit counts for every query block
python librarian.py --pdfs                           # full run + legal open-access PDF lookup
python project.py ingest export.ris --name zotero --method citation   # records from outside
python report.py --project --since 2026-06-01 --diff # what the searches since June added
python journals.py fetch                             # venue metrics (OpenAlex, no key)
```

> **Comentários são muito bem-vindos.** Se uma base se comportar mal, uma
> contagem parecer errada, ou você tiver escrito uma entrada de `backends.json`
> para uma base que não distribuímos, por favor
> [abra uma issue](https://github.com/fabiocampolim-design/scitech-librarian/issues) —
> entradas de configuração para novas bases são especialmente bem-vindas.

**Por que isto existe.** Uma busca bibliográfica que não se pode repetir é uma
afirmação que não se pode defender. Revisões sistemáticas e verificações de
novidade ("ninguém fez X") dependem de exatamente quais bases você consultou,
com exatamente qual consulta, em exatamente qual dia — e esse registro quase
nunca sobrevive. Esta ferramenta foi construída para as verificações de
novidade de um doutorado em física e mantém esse registro por construção: cada
rodada arquiva suas consultas, contagens e registros, de modo que seis meses
depois a busca é reprodutível e a deriva das contagens fica visível.

## Joga pelas regras

Esta ferramenta é rigorosa com os termos de serviço de cada base que toca —
não como letra miúda, mas como princípio de projeto:

- **Somente APIs públicas documentadas.** Nunca raspa uma interface web.
  Raspar a Web of Science ou a Scopus viola seus termos e pode suspender o
  acesso da sua instituição inteira.
- **Web of Science sem licença de API é trabalho manual, então tornamos o
  trabalho manual pequeno** — `wos_manual.py` prepara cada consulta na
  gramática da própria WoS, conduz você ao colá-las na interface oficial e
  ingere suas exportações RIS de volta no mesmo esquema de registros. Colar,
  exportar, pronto.
- **Sem Google Scholar.** Não tem API, e raspá-lo viola seus termos.
- **Limites de taxa respeitados** — pausas por backend (incluindo os ≥3 s
  entre chamadas pedidos pelo arXiv) e um e-mail de contato no User-Agent, o
  que também coloca você no "polite pool", mais rápido, do OpenAlex/Crossref.
- **PDFs somente via Unpaywall** — cópias legais de acesso aberto, nunca
  contorno de paywall.
- **Direitos de acesso são honrados, não contornados** — os resultados da
  Scopus chegam pela assinatura da sua instituição (rede do campus ou VPN), e
  o README documenta como esse acesso realmente funciona.

## Recursos

- **Uma consulta estrutural, nove gramáticas nativas.** `[[a, b], [c]]`
  significa `(a OR b) AND c`; a sintaxe de cada backend — `TITLE-ABS-KEY(...)`,
  `TS=(...)`, `abs:"..."`, `and` em minúsculas — é gerada da mesma definição,
  de modo que as consultas nunca ficam dessincronizadas entre as bases.
- **Bases são dados.** Cada backend é uma entrada JSON: gramática de consulta,
  endpoint, cabeçalho de autenticação, estilo de paginação e caminhos com
  ponto dentro da resposta. `--init-backends` grava os padrões em
  `backends.json`; edite-o para adicionar, alterar ou desativar bases sem
  tocar em código. Só motores que realmente precisam de código (o feed XML do
  arXiv) usam um pequeno driver.
- **Tudo é arquivado.** Cada rodada grava um diretório com carimbo de tempo
  com registros JSON brutos, RIS por bloco, um combinado deduplicado em
  CSV/RIS/JSON/BibTeX/CSL-JSON, a string de consulta exata enviada a cada
  backend, contagens em JSON e uma tabela markdown pronta para colar,
  metadados da rodada e um log completo. As contagens também são anexadas a
  um arquivo de histórico, para que a deriva ao longo do tempo fique visível.
- **Um diretório de pesquisa, não uma pilha de rodadas.** `project.py` indexa
  cada rodada e cada registro que você traz de fora (RIS, BibTeX, CSV, JSON —
  Zotero, Mendeley, Web of Science, listas de referências; uma pasta de
  entrada para colaboradores), mantém a proveniência (quem, quando, de onde,
  método PRISMA), mescla tudo com `found_by` / `first_seen` por registro, e
  `report.py --project` descreve o projeto inteiro: o que cada busca
  acrescentou, qual base encontrou o que nenhuma outra encontrou, deriva das
  contagens ao longo do tempo, e um fluxo PRISMA com as duas colunas de
  identificação. Filtros por janela de datas, diferencial ("novo desde
  junho"), tipo de fonte, base, bloco, ano de publicação, citações, métrica do
  veículo. Um diretório por projeto; um laboratório tem vários.
- **Métricas de periódicos, ano a ano.** `journals.py` busca a citação média
  em 2 anos do OpenAlex (sem chave) e CiteScore/SJR/SNIP da Scopus (com
  chave), importa CSVs do SCImago e exportações licenciadas do JCR, armazena
  os valores por ano para que a série se acumule, e alimenta uma coluna de
  métrica, uma tabela de veículos por métrica, uma tabela de evolução e
  `--min-metric` nos relatórios.
- **Logs e auditorias.** Cada script grava um log de auditoria (invocação,
  versões, cada aviso) em `<outdir>/logs/`; a saída no console é pequena por
  padrão, `--verbose` / `--quiet` / `--log-dir` / `--outdir` em todos eles;
  `--help` lista cada parâmetro com seu padrão.
- **Um relatório de busca bibliográfica, PRISMA incluído.** Cada rodada termina
  com `report.md` (ou HTML / LaTeX / PDF / texto puro): a estratégia de busca
  com a string exata enviada a cada base, um resumo dos resultados, um
  **diagrama de fluxo PRISMA 2020** cujas etapas automatizáveis são
  preenchidas a partir da rodada, um checklist de relato de busca
  **PRISMA-S**, os principais registros por bloco, e sugestões baseadas em
  regras (aperte este bloco, repita aquele backend, aumente o limite, leia
  estes cinco resultados à mão). Três níveis — `simple`, `intermediate`,
  `full` — de um resumo de duas páginas a cada registro com seu resumo e o
  log completo. Veja [Relatórios e PRISMA](#relatórios-e-prisma).
- **Relatórios em cinco idiomas.** `--lang pt-BR|es|de|fr` (padrão `en`)
  escreve o texto próprio do relatório — títulos, etapas e diagrama PRISMA,
  checklist, explicações, sugestões — em português do Brasil, espanhol, alemão
  ou francês. Registros, strings de consulta, nomes de blocos, nomes de
  arquivos e logs nunca são traduzidos: um relatório continua sendo um
  registro fiel da busca em qualquer idioma.
- **À prova de falhas por checkpoints.** As contagens são salvas após *cada*
  chamada de API e Ctrl-C é seguro — um travamento no fim de uma rodada longa
  não perde nada.
- **Um filtro de lixo com comprovantes.** O OpenAlex indexa repositórios não
  curados; em uma rodada de 5.146 registros, 15,3 % dos seus registros vieram
  de Zenodo, SSRN, Figshare e afins — contra 0 % para ADS, Scopus, Semantic
  Scholar e INSPIRE. Em uma consulta decisiva de novidade essa foi toda a
  diferença entre 16 resultados e 3. Filtrado por padrão; `--keep-junk`
  desativa.
- **Funciona sem nenhuma afiliação.** Seis backends não precisam de chave nem
  de instituição; o ADS precisa apenas de um token pessoal gratuito. Sem VPN,
  sem rede do campus, sem assinatura — isso só importa se você acrescentar a
  Scopus ou a API da WoS.
- **A física tem cobertura de primeira classe.** NASA ADS e INSPIRE-HEP são
  backends que nenhuma ferramenta comparável oferece; para física
  arbitrada, o ADS é essencialmente completo.
- **Verificações de novidade como fluxo de trabalho.** Projete blocos de modo
  que um número *pequeno* seja o resultado informativo, rode os mesmos blocos
  ao longo do tempo, observe as contagens — e leia cada resultado à mão antes
  de afirmar uma lacuna.
- **Testável offline.** 325 verificações rodam sem rede e sem chaves (os
  backends são exercitados contra respostas de API gravadas; o diretório de
  pesquisa, os parsers de ingestão, o armazém de periódicos e o gerador de
  relatórios contra diretórios sintéticos); CI em Linux, Windows e macOS,
  Python 3.9 e 3.13.

## As bases: para que cada uma realmente serve

| Base | Chave necessária | Cobertura | Use para | Cuidado com |
|---|---|---|---|---|
| **OpenAlex** | nenhuma | ~250 mi de obras, incl. preprints | primeira passada, sempre funciona, sem instituição | ~15 % de lixo não curado — filtrado por padrão |
| **NASA ADS** | token gratuito | física + astronomia arbitradas completas, arXiv incorporado | **melhor fonte única para física** | nada sério |
| **arXiv** | nenhuma | preprints, todas as áreas | trabalhos novíssimos | engasga com booleanos aninhados — veja Armadilhas |
| **INSPIRE-HEP** | nenhuma | HEP, QCD na rede, teoria de partículas | literatura invisível aos índices gerais | escopo de área estreito |
| **Scopus** | chave gratuita + instituição | ~27–28 mil periódicos curados | contagens com grau de citação para artigos | direitos por IP; precisa da rede do campus ou VPN |
| **Semantic Scholar** | nenhuma | amplo, bom grafo de citações | verificação cruzada | ~1 req/s sem chave |
| **Crossref** | nenhuma | metadados de DOI de ~150 mi de itens | resolver DOIs | **sem suporte a booleanos** — contagens sem sentido, excluído das rodadas padrão |
| **CORE** | nenhuma (a chave aumenta o limite de taxa) | ~300 mi de saídas de acesso aberto de ~10 mil repositórios | teses, relatórios técnicos, depósitos institucionais — literatura cinzenta que nenhum índice de periódicos guarda | muitos registros não têm DOI nem periódico |
| **Web of Science** | licenciada | ~21–22 mil periódicos curados | legitimidade convencional | API normalmente não licenciada — use `wos_manual.py` |

**Se você configurar apenas duas:** OpenAlex (funciona na hora) e NASA ADS
(token gratuito em 30 segundos). Acrescente a Scopus se precisar de contagens
com grau de citação para um artigo. **Checagem de realidade da cobertura:** a
Scopus indexa ~25–30 % mais periódicos que a WoS e 80–85 % dos periódicos da
WoS também estão na Scopus; para física o ADS é essencialmente completo — então
Scopus + ADS + arXiv é, na prática, um superconjunto da WoS.

## Obtendo as chaves

A ferramenta lê suas chaves do ambiente do processo. Dois caminhos as colocam
lá, e você pode misturá-los:

- **Um arquivo `.env`** — copie `.env.example` para `.env` e preencha; o script
  o lê automaticamente, sem variáveis de shell para definir. Ele é ignorado
  pelo git.
- **Variáveis de ambiente** — exporte-as do seu shell, defina-as na
  configuração do seu agente ou lançador, ou forneça-as como segredos de CI.
  Elas têm precedência: o `.env` só preenche o que ainda não estiver definido,
  então, se você configurar as chaves assim, nunca precisará de um `.env`.

De qualquer forma, `python librarian.py --list` mostra quais chaves chegaram e
`--selftest` prova que elas funcionam.

- **NASA ADS** — <https://ui.adsabs.harvard.edu/user/settings/token>. Entre,
  gere, cole. Maior valor por minuto gasto.
- **Scopus / Elsevier** — <https://dev.elsevier.com/apikey/manage>. Gratuita,
  instantânea. A chave autentica *você*; o direito de acesso vem da assinatura
  da sua instituição, então esteja na rede do campus ou na VPN (um 401/403
  normalmente indica problema de rede, não chave ruim). **A Elsevier não tem
  botão de revogação** — uma chave vazada está queimada, não desativada.
  Opcionalmente peça à sua biblioteca um InstToken, que elimina a dependência
  da VPN.
- **Semantic Scholar** — opcional; funciona sem chave a ~1 req/s.
- **Web of Science** — veja o companheiro manual abaixo; a gramática restrita
  da chave Starter raramente faz a API valer a pena.

**Sem instituição? A maior parte ainda funciona.** Seis dos nove backends
(OpenAlex, arXiv, INSPIRE-HEP, Semantic Scholar, Crossref, CORE) não precisam de
chave nem de acesso institucional, e o NASA ADS precisa apenas de um token
pessoal gratuito — então a ferramenta é totalmente usável de qualquer laptop,
sem afiliação e sem VPN. O direito institucional importa apenas para a Scopus
(e a API licenciada da WoS): ali a chave autentica *você*, mas os resultados
fluem pela assinatura da sua instituição, que normalmente é por IP — esteja
na rede institucional, ou use a VPN, o proxy ou o login federado que sua
instituição oferece, antes que a API retorne qualquer coisa. O teste é sempre
o mesmo: rode `--selftest` e veja se a Scopus retorna um número plausível.

## Escrevendo consultas

As consultas vivem em `queries.json` (copie `queries.example.json` e edite):

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

`groups` é uma conjunção de disjunções. `arxiv_groups` opcionalmente indica
quais grupos (no máximo dois) vão para o arXiv, que degrada com booleanos
profundamente aninhados. O bloco mais valioso costuma ser uma interseção
deliberada de duas literaturas que você suspeita não conversarem entre si — um
resultado próximo de zero é um achado, não uma falha, *se* você então ler cada
resultado à mão.

## Adicionando uma base (sem código)

```bash
python librarian.py --init-backends     # writes backends.json (next to .env) for editing
```

Uma entrada de backend declara a gramática de consulta, a requisição e onde os
dados vivem na resposta:

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

Estilos de paginação: `cursor`, `page`, `offset`, `none`. A autenticação é uma
variável de ambiente mapeada para um cabeçalho. Os caminhos de campo aceitam
indexação `[0]`, mapeamento `[]` sobre listas, alternativas `a|b` e
transformações nomeadas. `docs/FUTURE_BACKENDS.md` tem pontos de partida
verificados para Europe PMC, OpenAIRE, DOAJ, ERIC, EconBiz, Zenodo,
ClinicalTrials.gov, cada um reverificado contra a API ao vivo, junto
com o teste booleano que um candidato precisa passar antes de valer a pena
adicioná-lo. As entradas
em `backends.json` sobrepõem os padrões embutidos pelo nome;
`"disabled": true` remove uma.

## Web of Science, a situação honesta

A gramática completa `TS=`/`NEAR` vive na **Expanded API**, licenciada
separadamente, que os acordos de consórcios nacionais normalmente não incluem;
o nível gratuito **Starter** rejeita booleanos complexos. Se a sua biblioteca
não consegue credenciais Expanded, a WoS é trabalho manual — e `wos_manual.py`
o torna pequeno:

```bash
python wos_manual.py prep      # query files + CHECKLIST.md, in WoS grammar
python wos_manual.py walk      # copies each query to your clipboard in turn
python wos_manual.py ingest    # parses your RIS exports into the same schema
python wos_manual.py status    # what you have collected so far
```

O checklist codifica as configurações da interface que quebram consultas
silenciosamente (Core Collection e não All Databases; Advanced e não Basic;
quais edições; forma marcada `TS=(...)` versus forma nua — colar uma consulta
marcada em um campo escolhido por menu dá *"Search Error: Invalid query"*).
`ingest` mescla os resultados manuais com os automatizados, mesmo esquema,
mesma análise.

## Como se compara

[findpapers](https://github.com/jonatasgrosman/findpapers) é a ferramenta mais
próxima: uma consulta booleana em nove bases (IEEE e PubMed incluídas), com
deduplicação, refinamento e download de PDFs — uma boa escolha para revisões
sistemáticas ao estilo da engenharia de software em Python 3.11+.
[litstudy](https://github.com/NLeSC/litstudy) analisa uma coleção que você já
tem (bibliometria, grafos de rede, tópicos) no Jupyter.
[paperscraper](https://github.com/jannisborn/paperscraper) é feito para
ciências da vida (PubMed + servidores de preprints) com ferramentas de fator
de impacto e de dumps.

O nicho desta ferramenta: **o instrumento de busca reprodutível.** Arquivo
único sem instalação; a única com NASA ADS e INSPIRE-HEP (física); rodadas
arquivadas e citáveis com strings de consulta exatas e histórico de contagens;
bases como configuração do usuário; e uma postura estrita de somente APIs
documentadas (tanto o findpapers quanto esta ferramenta usam a API oficial WoS
Starter; o paperscraper raspa o Google Scholar — nós recusamos). Se você
precisa de IEEE/PubMed hoje ou de coleta de PDFs dentro da ferramenta, use o
findpapers; se precisa de grafos bibliométricos, o litstudy; para buscas
auditáveis e cobertura de física, esta.

## Armadilhas em que caímos, para que você não caia

(O [Manual do Usuário](docs/USER_MANUAL.pt-BR.md) §12 lista todos os recursos e
todas as limitações conhecidas em um só lugar.)

- **O arXiv trava com booleanos profundamente aninhados** — não é um erro, ele
  simplesmente nunca retorna. No máximo dois grupos são enviados
  (`arxiv_groups` escolhe quais), por HTTPS, com timeout curto, porque uma
  heurística automática de "mais seletivo" escolheu errado.
- **As contagens não são comparáveis entre backends.** Operadores de
  proximidade são descartados e o stemming difere. Descubra aqui; cite
  WoS/Scopus no artigo.
- **O `cmd.exe` do Windows não trata `#` como comentário** — um `# nota`
  colado no fim vira um erro do argparse. Use o PowerShell ou remova o
  comentário.
- **O Unpaywall é uma chamada HTTP por DOI** (~20 min para 3.000). Restrinja
  com `--pdf-blocks`; os resultados ficam em cache entre rodadas.

## Saída

Cada rodada grava `lit/runs/<timestamp>/`:

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

mais `lit/counts_history.csv`, anexado a cada rodada, e o diretório de
pesquisa ao redor:

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

## O diretório de pesquisa

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

Registros de fora chegam de três maneiras: pela linha de comando (com
proveniência completa), por uma pasta de entrada (solte e ingira), ou pela
rotina da Web of Science. Eles mantêm o arquivo original, recebem o esquema
comum de registros, são marcados `manual:<name>`, e seu `--method` (database,
citation, website, organisation, expert, other) os posiciona no fluxo PRISMA.
As fontes manuais aparecem em todas as tabelas como mais uma base — inclusive
em "encontrado só aqui", que é como você descobre o que a lista de referências
do seu colega tinha e seis bases não tinham.

## Relatórios e PRISMA

Uma busca que não se pode relatar é uma busca que não se pode defender, então
cada rodada termina com um relatório. `--report-level` escolhe o detalhe,
`--report-format` os arquivos; `report.py` renderiza de novo qualquer rodada
arquivada sem tocar na rede.

| Nível | O que você recebe |
|---|---|
| `simple` (padrão) | metadados da rodada; fontes (projeto); estratégia de busca (consulta estrutural + a string exata enviada a cada backend); resumo dos resultados; linha do tempo (projeto); fluxo PRISMA 2020 + checklist PRISMA-S; 10 principais registros por bloco; sugestões |
| `intermediate` | + cada registro único; a contribuição marginal de cada fonte ("encontrado só aqui"); distribuições por ano / veículo / autor; métricas de periódicos e sua evolução; veículos removidos pelo filtro; erros; estatísticas de acesso aberto; deriva das contagens contra rodadas anteriores |
| `full` | + cada registro com resumo e lista de autores completos, e quais fontes o encontraram; listas brutas por fonte antes da deduplicação; os registros filtrados; configuração de endpoints dos backends; arquivos de proveniência do projeto e das fontes; o log completo da rodada; ambiente |

Formatos: `md`, `html` (autocontido, claro/escuro, imprimível), `tex`, `pdf`,
`txt`. O PDF é compilado do LaTeX com xelatex / lualatex / pdflatex se um
deles estiver instalado, senão com o pandoc, senão por um escritor embutido
sem dependências — a opção nunca falha, apenas a tipografia degrada.

**Idiomas.** `report.py --lang` e `librarian.py --report-lang` aceitam `en`
(padrão), `pt-BR`, `es`, `de` ou `fr`; um diretório de pesquisa pode definir
`"defaults": {"lang": "pt-BR"}` em `project.json`. Só a estrutura do relatório
é traduzida — títulos, cabeçalhos de tabela, as etapas PRISMA 2020 e o diagrama
de fluxo em todos os formatos, o checklist PRISMA-S, o texto explicativo, as
sugestões, os separadores de milhar. Tudo o que a ferramenta encontrou ou
recebeu é reproduzido tal qual: títulos, resumos, autores, veículos, nomes e
notas dos blocos, as strings de consulta exatas, nomes dos backends, opções,
nomes de arquivos, despejos JSON e o log da rodada embutido. `run.log`, os logs
de auditoria e o console ficam em inglês seja qual for o idioma do relatório.
Exemplo: [`samples/pt-BR/report.md`](samples/pt-BR/report.md).

**PRISMA.** O relatório traz um diagrama de fluxo
[PRISMA 2020](https://www.prisma-statement.org/) (SVG no HTML, TikZ no
LaTeX/PDF, ASCII no Markdown/texto). As etapas que uma ferramenta pode conhecer
são preenchidas a partir dos dados — registros identificados por base,
registros identificados por outros métodos (fontes manuais por método),
registros removidos por automação (o filtro de veículos), duplicatas removidas,
registros restantes para triagem — e são honestas sobre a diferença entre
*identificados* (o que cada base informa) e *recuperados* (o que foi baixado
dentro de `--limit`). As etapas que só um humano pode conhecer — triados,
excluídos, procurados, avaliados, incluídos, com motivos de exclusão, para as
duas colunas — são lidas de `prisma.json` (uma rodada) ou `screening.json`
(diretório de pesquisa); um modelo é gravado no primeiro relatório, então
preencha-o conforme faz a triagem e rode `report.py` de novo. Um checklist de
relato de busca [PRISMA-S](https://doi.org/10.1186/s13643-020-01542-z) (todos
os 16 itens) é completado automaticamente onde a ferramenta tem os dados —
bases, estratégias completas, limites, filtros, datas, totais, método de
deduplicação, atualizações — e marca o restante como "a completar".

```bash
python librarian.py --report-level intermediate --report-format md html
python report.py lit/runs/20260815T095908 --level full --format pdf
python report.py --latest --format txt            # newest run, plain text
python librarian.py --no-report                   # search only
```

Filtros de relatório (nos dois modos): `--since/--until DATE`, `--latest`,
`--diff`, `--year-from/--year-to`, `--backends`, `--blocks`,
`--sources auto|manual|all`, `--records FILE…` (RIS/BibTeX/CSV/JSON extras só
para este relatório), `--metric NAME --min-metric X`, `--min-citations N`,
`--oa-only`, `--top N`, `--sort cited|year|metric`. Os filtros são impressos
nos metadados do relatório e no item 9 do PRISMA-S, para que um relatório
filtrado nunca seja confundido com a busca inteira.

## Métricas de periódicos

```bash
python journals.py fetch                                   # every journal seen in lit/: OpenAlex (+ Scopus with a key)
python journals.py import-scimago scimagojr_2024.csv --year 2024 --all
python journals.py import-csv jcr.csv --provider jcr_if --year 2023 --name-col "Journal name" --value-col JIF
python journals.py show --metric scopus_citescore
```

`lit/journals/metrics.json` mantém uma entrada por periódico (chaveada por
ISSN) com valores **por ano, nunca sobrescritos** — busque de novo no ano que
vem e o relatório mostra a série. Provedores: citação média em 2 anos e índice
h do OpenAlex (sem chave; instantâneo por ano de busca), CiteScore / SJR / SNIP
da Scopus (chave; histórico completo), SJR / índice H / quartil do SCImago (um
download de CSV por ano, o caminho para *todos* os ~30.000 periódicos), e o
Journal Impact Factor da Clarivate — proprietário, sem API gratuita, somente
importação de uma exportação licenciada. A ferramenta não vai raspá-lo.

### Relatórios de exemplo

[`samples/`](samples/) contém uma rodada real dos quatro blocos de exemplo de
`queries.example.json` contra as três bases **licenciadas em CC0** (OpenAlex,
arXiv, INSPIRE-HEP; 2026-08-28: 5.705 resultados identificados, 1.286
registros recuperados, 1.226 únicos), renderizada em todos os níveis e todos
os formatos — `simple` tem 6 páginas, `intermediate` 68, `full` 427. Trechos
dos PDFs:

| `simple`, p. 1 — metadados da rodada e estratégia de busca | `simple`, p. 3 — fluxo PRISMA 2020 |
|---|---|
| [![](samples/img/simple_p1.png)](samples/simple/report.pdf) | [![](samples/img/simple_p3.png)](samples/simple/report.pdf) |

| `simple`, p. 2 — consulta exata por backend, contagens | `full` — registros com resumos |
|---|---|
| [![](samples/img/simple_p2.png)](samples/simple/report.pdf) | [![](samples/img/full_records.png)](samples/full/report.pdf) |

Navegue: [simple](samples/simple/report.md) ·
[intermediate](samples/intermediate/report.md) ·
[full](samples/full/report.md) (Markdown, renderizado pelo GitHub), ou o
`.html`, `.tex`, `.pdf`, `.txt` ao lado de cada um;
[`samples/pt-BR/`](samples/pt-BR/) é o relatório `simple` da mesma rodada em
português do Brasil (`--lang pt-BR`).

[`samples/project/`](samples/project/) é o mesmo exemplo como **diretório de
pesquisa**: duas rodadas (uma primeira passada só com OpenAlex e a rodada CC0
completa) mais a lista de referências de um colega ingerida como fonte manual,
com a citação média em 2 anos do OpenAlex registrada para 103 veículos —
`report.md/html/tex/pdf/txt` (simple), `report_intermediate.md` e
`report_diff.md` (`--since 2026-08-28 --diff`).

| `project`, p. 1 — fontes e o que cada uma acrescentou | `project`, p. 3 — PRISMA com as duas colunas de identificação |
|---|---|
| [![](samples/img/project_p1.png)](samples/project/report.pdf) | [![](samples/img/project_prisma.png)](samples/project/report.pdf) |

**Por que só três bases nos exemplos.** OpenAlex, arXiv e INSPIRE publicam seus
metadados sob CC0, então seus registros — resumos incluídos — podem ser
redistribuídos aqui. Os dados da Scopus, do NASA ADS e do Semantic Scholar
vêm sob seus próprios termos de API (Scopus: sem redistribuição fora da sua
instituição; Semantic Scholar: ODC-BY), então relatórios construídos sobre
eles são para o seu próprio diretório de pesquisa, não para um repositório
público. A ferramenta roda as oito; os exemplos mostram três.

## Referência de comandos

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

Todo script: `--help` lista cada parâmetro com seu padrão; `--outdir`,
`--verbose`, `--quiet`, `--log-dir` são comuns a todos.

## Um fluxo de trabalho que funciona

1. Escreva 5–10 blocos; inclua pelo menos uma consulta cruzada deliberada
   entre literaturas que você suspeita estarem desconectadas.
2. `--selftest`, depois `--counts-only` para ver a forma de cada campo.
3. Aperte tudo o que retornar milhares de resultados — uma palavra genérica
   costuma ser a culpada.
4. Rodada completa com `--pdfs`; importe o RIS no Zotero. Leia o `report.md`.
5. **Leia cada resultado dos seus blocos pequenos à mão** antes de afirmar uma
   lacuna; registre o que triou e manteve em `prisma.json` e renderize o
   relatório de novo — o diagrama de fluxo fica então pronto para o material
   suplementar do artigo.
6. Vasculhe as listas de referências dos PDFs em busca de trabalhos que todos
   citam e você não tem — isso captura o que a busca por palavras-chave
   perde, e capturou as duas referências mais importantes no projeto para o
   qual isto foi construído.

Ou delegue o ciclo: apresente sua pergunta de pesquisa a um agente de IA
(Claude Code ou similar) e peça que ele esboce o `queries.json`, rode as
varreduras e percorra com você os resultados arquivados. O arquivo de consulta
estruturado, a configuração JSON e os diretórios de rodada com carimbo de tempo
são deliberadamente fáceis de um agente escrever e auditar — esta ferramenta
foi construída dentro de exatamente esse fluxo de trabalho.

## Roteiro

- Mais bases como configuração: Europe PMC, OpenAIRE, DOAJ, ERIC, EconBiz,
  Zenodo e ClinicalTrials.gov não precisam de chave alguma (CORE passou a integrar a ferramenta na 3.5.0)
  (`docs/FUTURE_BACKENDS.md` tem os detalhes de API reverificados, o
  teste booleano que cada um passou e o que os escritórios de patentes
  exigiriam — contribuições de entradas de `backends.json` funcionais são muito
  bem-vindas).
- Download legal de PDFs de acesso aberto a partir dos links do Unpaywall já
  coletados.
- Envio pela API web do Zotero (uma rodada direto para uma coleção).
- Snowballing via os endpoints de referências do OpenAlex/Semantic Scholar, e
  grafos de citação entre os resultados de uma rodada.

## Testes

```bash
python tests/test_librarian.py
```

325 verificações, só biblioteca padrão, sem rede e sem chaves — os backends
rodam contra respostas de API gravadas; os parsers de ingestão, a mesclagem do
diretório de pesquisa, o armazém de periódicos e o gerador de relatórios
contra diretórios sintéticos — de modo que a suíte exercita offline os
caminhos reais de parsing, mesclagem e renderização. O CI a roda em Linux,
Windows e macOS sob Python 3.9 e 3.13.

## Skill para o Claude Code

`SKILL.md` na raiz do repositório é uma skill do
[Claude Code](https://claude.com/claude-code) que ensina um agente a rodar o
scitech-librarian a partir do seu clone — qual script faz o quê, o fluxo de
chaves e consultas, e as armadilhas que cada base arma. Instale copiando o
arquivo para `~/.claude/skills/literature-search/SKILL.md`; o agente então
localiza o clone por `SCITECH_LIBRARIAN_HOME` (se definida) ou procurando por
`librarian.py`, e nunca copia os scripts para dentro de um projeto. A suíte de
testes verifica que uma cópia instalada é byte a byte idêntica ao arquivo
distribuído, de modo que a skill não pode se afastar da versão que descreve.

## Como foi construído

No Claude Code, para uso real: a primeira versão foi escrita nas sessões de
revisão bibliográfica de um projeto de física da matéria condensada (meados de
agosto de 2026, cerca de três dias de trabalho até a v2.2), endurecida rodando
verificações de novidade reais de doutorado — varreduras de 5.000 registros, o
travamento do arXiv, a discrepância de lixo do OpenAlex, erros de consulta na
interface da WoS — produtizada em 26 de agosto de 2026 (motor declarativo de
backends, suíte de testes offline, CI) em uma única sessão, e dotada do gerador
de relatórios PRISMA, do diretório de pesquisa, da ingestão, das métricas de
periódicos e dos manuais em 28 de agosto de 2026. Em termos de
[CRediT](https://credit.niso.org/):

| Papel CRediT | Fabio | Claude |
|---|---|---|
| **Conceituação** | Uma consulta em todas as bases como instrumento reprodutível; o método de contagens como verificação de novidade; a postura estrita quanto aos termos de serviço (WoS manual em vez de raspagem); o relatório PRISMA em três níveis; o diretório de pesquisa como unidade do laboratório, fontes manuais com proveniência, métricas de veículos acompanhadas ao longo do tempo | O esquema de consulta estrutural; o motor de bases como configuração; o modelo de documento do relatório e a cadeia de fallback do PDF; o projeto do diretório como índice |
| **Metodologia** | Disciplina de projeto de consultas ("um número pequeno é o achado — depois leia cada resultado"); seleção de bases e estratégia de acesso institucional | Quantificação de veículos lixo; a correção de limitação de grupos do arXiv; o projeto de checkpoint após cada chamada |
| **Software** | — | Todo ele |
| **Validação** | Varreduras de novidade ao vivo em consultas de pesquisa reais; pegou as armadilhas de gramática da WoS, o travamento do arXiv, a discrepância de contagens OpenAlex/Scopus | A suíte offline de 325 verificações; CI; autotestes ao vivo |
| **Investigação** | O labirinto do acesso institucional (CAPES/CAFe, VPN, obtenção de chaves) | Documentação de API de 8+ bases; análise do código de concorrentes |
| **Redação** | Revisão e edição | Rascunho original |
| **Recursos · Supervisão · Administração do projeto · Obtenção de financiamento** | Tudo | — |

## Licença

Apache License 2.0 — veja `LICENSE` e `NOTICE` (em inglês, que prevalecem).
Você pode usar, modificar e redistribuir, inclusive comercialmente, desde que a
licença e o aviso viajem junto; contribuições são aceitas nos mesmos termos
(seção 5). E respeite os termos de serviço de cada base que consultar; esta
ferramenta é feita para tornar isso o caminho fácil.

### Isenção de responsabilidade

Este software é fornecido **no estado em que se encontra** ("as is"), sem
garantias ou condições de qualquer tipo, expressas ou implícitas, incluindo,
sem limitação, qualquer garantia de comercialização, adequação a um propósito
específico, titularidade ou não infração. Em nenhuma hipótese o autor será
responsável por danos de qualquer natureza — diretos, indiretos, especiais,
incidentais ou consequentes — nem por qualquer outra reclamação ou
responsabilidade, seja contratual, extracontratual ou de outra ordem,
decorrente de, originada de ou relacionada ao software ou ao seu uso, mesmo
que avisado da possibilidade de tais danos (Apache License 2.0, seções 7 e 8).
Somente você é responsável por usá-lo licitamente, pelas consultas que executa
e pelos registros que mantém, e por cumprir os termos de serviço e a licença
de cada base, API e conjunto de dados que ele acessa em seu nome.

Este é um projeto independente. Não é afiliado, endossado ou apoiado por
OpenAlex, NASA ADS, arXiv, INSPIRE-HEP, Elsevier (Scopus), Clarivate (Web of
Science, JCR), Semantic Scholar, Crossref, CORE, Unpaywall ou SCImago; seus
nomes são usados apenas para identificar os serviços que ele consulta.
