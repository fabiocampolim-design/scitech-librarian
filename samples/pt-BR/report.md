# Relatório de busca bibliográfica -- execução 20260828T160426

Gerado por scitech-librarian 3.2 (nível do relatório: simple). Todos os números abaixo são reproduzíveis a partir do diretório da execução arquivado `20260828T160426`.

| Item | Valor |
|---|---|
| Início da execução | 2026-08-28 16:04:26 |
| Duração | 42 s |
| Arquivo de consultas | queries.example.json |
| Blocos | PSC, MLP, NOV, QC |
| Backends / fontes | openalex, arxiv, inspire |
| Modo | coleta completa, até 300 registros por bloco e backend |
| Filtro de veículos não curados | ligado |
| Consulta de acesso aberto | não executada |
| Métricas de periódicos | registradas para 103 periódicos |
| Filtros | nenhum |
| Interrompida | não |

## Estratégia de busca

Cada bloco é uma consulta estrutural -- uma conjunção de grupos de sinônimos, (a OR b) AND (c OR d) -- traduzida para a gramática nativa de cada backend. As cadeias abaixo são exatamente o que foi enviado (item 8 do PRISMA-S).

### Bloco PSC: Perovskite solar cell degradation under humidity

Finalidade: grounding block -- expect thousands of hits; use it to sanity-check that every backend is reachable and the counts are plausible

```
(perovskite solar cell OR halide perovskite photovoltaic) AND (degradation OR stability OR encapsulation) AND (humidity OR moisture OR water ingress)
```

| Backend | Cadeia de consulta enviada |
|---|---|
| openalex | ("perovskite solar cell" OR "halide perovskite photovoltaic") AND (degradation OR stability OR encapsulation) AND (humidity OR moisture OR "water ingress") |
| arxiv | (all:"perovskite solar cell" OR all:"halide perovskite photovoltaic") AND (all:"degradation" OR all:"stability" OR all:"encapsulation") |
| inspire | ("perovskite solar cell" or "halide perovskite photovoltaic") and ("degradation" or "stability" or "encapsulation") and ("humidity" or "moisture" or "water ingress") |

### Bloco MLP: Machine-learned interatomic potentials for amorphous materials

Finalidade: a narrower intersection -- expect hundreds; good for testing record fetch and RIS export

```
(machine learning potential OR machine-learned interatomic potential OR neural network potential) AND (amorphous OR glass OR disordered solid) AND (molecular dynamics OR structure prediction)
```

O arXiv recebe apenas os grupos [0, 1] (limitação de booleanos aninhados).

| Backend | Cadeia de consulta enviada |
|---|---|
| openalex | ("machine learning potential" OR "machine-learned interatomic potential" OR "neural network potential") AND (amorphous OR glass OR "disordered solid") AND ("molecular dynamics" OR "structure prediction") |
| arxiv | (all:"machine learning potential" OR all:"machine-learned interatomic potential" OR all:"neural network potential") AND (all:"amorphous" OR all:"glass" OR all:"disordered solid") |
| inspire | ("machine learning potential" or "machine-learned interatomic potential" or "neural network potential") and ("amorphous" or "glass" or "disordered solid") and ("molecular dynamics" or "structure prediction") |

### Bloco NOV: EXAMPLE NOVELTY CHECK: origami metamaterials as topological acoustic pumps

Finalidade: novelty-check pattern -- a SMALL number is the good outcome; read every hit by hand before claiming a gap

```
(origami OR kirigami) AND (acoustic metamaterial OR phononic crystal) AND (topological pumping OR Thouless pump OR edge state)
```

| Backend | Cadeia de consulta enviada |
|---|---|
| openalex | (origami OR kirigami) AND ("acoustic metamaterial" OR "phononic crystal") AND ("topological pumping" OR "Thouless pump" OR "edge state") |
| arxiv | (all:"origami" OR all:"kirigami") AND (all:"acoustic metamaterial" OR all:"phononic crystal") |
| inspire | ("origami" or "kirigami") and ("acoustic metamaterial" or "phononic crystal") and ("topological pumping" or "Thouless pump" or "edge state") |

### Bloco QC: Quasicrystal photonics (arXiv-tuned example)

Finalidade: demonstrates arxiv_groups: arXiv chokes on deeply nested booleans, so name the two groups it should get

```
(quasicrystal OR quasiperiodic lattice) AND (photonic OR waveguide OR optical lattice) AND (localization OR critical states OR fractal spectrum)
```

O arXiv recebe apenas os grupos [0, 2] (limitação de booleanos aninhados).

| Backend | Cadeia de consulta enviada |
|---|---|
| openalex | (quasicrystal OR "quasiperiodic lattice") AND (photonic OR waveguide OR "optical lattice") AND (localization OR "critical states" OR "fractal spectrum") |
| arxiv | (all:"quasicrystal" OR all:"quasiperiodic lattice") AND (all:"localization" OR all:"critical states" OR all:"fractal spectrum") |
| inspire | ("quasicrystal" or "quasiperiodic lattice") and ("photonic" or "waveguide" or "optical lattice") and ("localization" or "critical states" or "fractal spectrum") |

## Resumo dos resultados

| Bloco | openalex | arxiv | inspire | Identificados | Recuperados | Únicos |
|---|---|---|---|---|---|---|
| PSC | 4569 | 175 | 0 | 4.744 | 475 | 474 |
| MLP | 238 | 138 | 0 | 376 | 344 | 313 |
| NOV | 0 | 0 | 0 | 0 | 0 | 0 |
| QC | 154 | 414 | 17 | 585 | 467 | 439 |
| Total | 4.961 | 727 | 17 | 5.705 | 1286 | 1226 |

Identificados = contagens de acertos das bases (não comparáveis entre backends: operadores de proximidade são descartados e a radicalização difere). Recuperados = registros efetivamente baixados após o filtro de veículos, limitados por `--limit`. Únicos = após a deduplicação por DOI/título entre todas as fontes.

## Fluxo PRISMA 2020

```
IDENTIFICAÇÃO
+------------------------------------------+     +------------------------------------------+
| Registros identificados em bases de      |     | Registros removidos antes da triagem:    |
| dados                                    |     | ferramentas de automação (filtro de      |
| (n = 5.705)                              |     | veículos) (n = 37)                       |
| openalex: 4.961                          | --> | duplicatas removidas (n = 60)            |
| arxiv: 727                               |     +------------------------------------------+
| inspire: 17                              |
+------------------------------------------+
                      |
                      v
TRIAGEM
+------------------------------------------+     +------------------------------------------+
| Registros triados (n = 1.226)            | --> | Registros excluídos (n = --)             |
+------------------------------------------+     +------------------------------------------+
                      |
                      v
+------------------------------------------+     +------------------------------------------+
| Relatos buscados para recuperação (n =   |     | Relatos não recuperados (n = --)         |
| --)                                      | --> +------------------------------------------+
+------------------------------------------+
                      |
                      v
+------------------------------------------+     +------------------------------------------+
| Relatos avaliados quanto à elegibilidade |     | Relatos excluídos:                       |
| (n = --)                                 | --> | (n = --)                                 |
+------------------------------------------+     +------------------------------------------+
                      |
                      v
INCLUÍDOS
+------------------------------------------+
| Estudos incluídos na revisão (n = --)    |
| Relatos dos estudos incluídos (n = --)   |
+------------------------------------------+
```

| Etapa | n |
|---|---|
| Registros identificados em bases de dados | 5.705 |
|   openalex | 4.961 |
|   arxiv | 727 |
|   inspire | 17 |
| Registros recuperados (baixados / importados) | 1.323 |
| Removidos antes da triagem: automação (veículos não curados) | 37 |
| Removidos antes da triagem: duplicatas | 60 |
| Registros a triar (únicos) | 1.226 |
| Registros triados | 1.226 (assumido = únicos) |
| Registros excluídos na triagem | -- |
| Relatos buscados para recuperação | -- |
| Relatos não recuperados | -- |
| Relatos avaliados quanto à elegibilidade | -- |
| Estudos incluídos | -- |
| Relatos dos estudos incluídos | -- |

As etapas automáticas são calculadas a partir dos dados; '--' marca etapas manuais ainda não registradas em prisma.json. Note que 'identificados' conta os acertos informados por cada base, enquanto 'recuperados' é o que foi baixado dentro de `--limit`; por isso os dois diferem em blocos grandes.

### Lista de verificação PRISMA-S para relato da busca

| Item | Requisito | Esta busca |
|---|---|---|
| 1 | Nome da base de dados | openalex, arxiv, inspire (APIs públicas documentadas) |
| 2 | Busca em múltiplas bases | 3 bases de dados, uma consulta estrutural por bloco traduzida para cada gramática nativa; ver Estratégia de busca |
| 3 | Registros de estudos | não se aplica |
| 4 | Recursos on-line e navegação | nenhum registrado |
| 5 | Busca por citações | não realizada |
| 6 | Contatos | nenhum registrado |
| 7 | Outros métodos | nenhum |
| 8 | Estratégias de busca completas | relatadas literalmente por backend em Estratégia de busca; arquivadas em queries.json |
| 9 | Limites e restrições | download de registros limitado a 300 por bloco e backend, mais citados primeiro; sem limites de data, idioma ou tipo de documento |
| 10 | Filtros de busca | filtro de veículos ligado: registros de repositórios não curados (Zenodo, Figshare, SSRN...) removidos |
| 11 | Trabalhos anteriores | nenhum |
| 12 | Atualizações | 3 execução(ões) anterior(es) arquivada(s); contagens acompanhadas em counts_history.csv |
| 13 | Datas das buscas | buscado em 2026-08-28 16:04:26 |
| 14 | Revisão por pares | nenhum |
| 15 | Total de registros | 5.705 identificados em bases de dados; 1.323 recuperados; 1.226 únicos |
| 16 | Deduplicação | DOI idêntico ou, na falta, os 90 primeiros caracteres do título em minúsculas; 60 duplicatas removidas |

## 10 principais registros por bloco

Deduplicados entre fontes, ordenados por cited. O conjunto completo está em all_records.csv / .ris.

### Bloco PSC (474 únicos)

| Título | Autores | Ano | Veículo | Citações | DOI | OpenAlex 2-yr mean citedness |
|---|---|---|---|---|---|---|
| Incorporation of rubidium cations into perovskite solar cells improves photovoltaic performance | Michael Saliba; Taisuke Matsui; Konrad Domanski et al. | 2016 | Science | 3691 | [10.1126/science.aah5557](https://doi.org/10.1126/science.aah5557) |  |
| High-efficiency two-dimensional Ruddlesden–Popper perovskite solar cells | Hsinhan Tsai; Wanyi Nie; Jean‐Christophe Blancon et al. | 2016 | Nature | 3361 | [10.1038/nature18306](https://doi.org/10.1038/nature18306) |  |
| Efficient, stable and scalable perovskite solar cells using poly(3-hexylthiophene) | Eui Hyuk Jung; Nam Joong Jeon; Eun Young Park et al. | 2019 | Nature | 2318 | [10.1038/s41586-019-1036-3](https://doi.org/10.1038/s41586-019-1036-3) |  |
| A Layered Hybrid Perovskite Solar‐Cell Absorber with Enhanced Moisture Stability | Ian C. P. Smith; Eric T. Hoke; Diego Solís-Ibarra et al. | 2014 | Angewandte Chemie International Edition | 2006 | [10.1002/anie.201406466](https://doi.org/10.1002/anie.201406466) | 15.006 (2026) |
| Review of recent progress in chemical stability of perovskite solar cells | Guangda Niu; Xudong Guo; Liduo Wang | 2014 | Journal of Materials Chemistry A | 1945 | [10.1039/c4ta04994b](https://doi.org/10.1039/c4ta04994b) |  |
| Understanding Degradation Mechanisms and Improving Stability of Perovskite Photovoltaics | Caleb C. Boyd; Rongrong Cheacharoen; Tomas Leijtens et al. | 2018 | Chemical Reviews | 1767 | [10.1021/acs.chemrev.8b00336](https://doi.org/10.1021/acs.chemrev.8b00336) | 53.886 (2026) |
| Formamidinium and Cesium Hybridization for Photo‐ and Moisture‐Stable Perovskite Solar Cell | Jin‐Wook Lee; Deok‐Hwan Kim; Hui‐Seon Kim et al. | 2015 | Advanced Energy Materials | 1661 | [10.1002/aenm.201501310](https://doi.org/10.1002/aenm.201501310) | 18.63 (2026) |
| 23.6%-efficient monolithic perovskite/silicon tandem solar cells with improved stability | Kevin A. Bush; Axel F. Palmstrom; Zhengshan J. Yu et al. | 2017 | Nature Energy | 1533 | [10.1038/nenergy.2017.9](https://doi.org/10.1038/nenergy.2017.9) |  |
| Investigation of CH 3 NH 3 PbI 3 Degradation Rates and Mechanisms in Controlled Humidity Environments Using in Situ Techniques | Jinli Yang; Braden D. Siempelkamp; Dianyi Liu et al. | 2015 | ACS Nano | 1342 | [10.1021/nn506864k](https://doi.org/10.1021/nn506864k) | 16.894 (2026) |
| Carbon Nanotube/Polymer Composites as a Highly Stable Hole Collection Layer in Perovskite Solar Cells | Severin N. Habisreutinger; Tomas Leijtens; Giles E. Eperon et al. | 2014 | Nano Letters | 1198 | [10.1021/nl501982b](https://doi.org/10.1021/nl501982b) |  |

### Bloco MLP (313 únicos)

| Título | Autores | Ano | Veículo | Citações | DOI | OpenAlex 2-yr mean citedness |
|---|---|---|---|---|---|---|
| Atom-centered symmetry functions for constructing high-dimensional neural network potentials | Jörg Behler | 2011 | The Journal of Chemical Physics | 1644 | [10.1063/1.3553717](https://doi.org/10.1063/1.3553717) |  |
| Realistic Atomistic Structure of Amorphous Silicon from Machine-Learning-Driven Molecular Dynamics | Volker L. Deringer; Noam Bernstein; Albert P. Bartók et al. | 2018 | The Journal of Physical Chemistry Letters | 269 | [10.1021/acs.jpclett.8b00902](https://doi.org/10.1021/acs.jpclett.8b00902) |  |
| Machine-learned interatomic potentials by active learning: amorphous and liquid hafnium dioxide | Ganesh Sivaraman; Anand Narayanan Krishnamoorthy; Matthias Baur et al. | 2020 | npj Computational Materials | 185 | [10.1038/s41524-020-00367-7](https://doi.org/10.1038/s41524-020-00367-7) |  |
| Machine-learned interatomic potentials by active learning: amorphous and liquid hafnium dioxide | Ganesh Sivaraman; Anand Narayanan Krishnamoorthy; Matthias Baur et al. | 2019 | Cambridge University Engineering Department Publications Database | 184 | [10.17863/cam.55408](https://doi.org/10.17863/cam.55408) | 1 (2026) |
| Growth Mechanism and Origin of High sp3 Content in Tetrahedral Amorphous Carbon | Miguel A. Caro; Volker L. Deringer; Jari Koskinen et al. | 2018 | Physical Review Letters | 178 | [10.1103/physrevlett.120.166101](https://doi.org/10.1103/physrevlett.120.166101) |  |
| Constructing first-principles phase diagrams of amorphous LixSi using machine-learning-assisted sampling with an evolutionary algorithm | Nongnuch Artrith; Alexander Urban; Gerbrand Ceder | 2018 | The Journal of Chemical Physics | 155 | [10.1063/1.5017661](https://doi.org/10.1063/1.5017661) |  |
| Study of Li atom diffusion in amorphous Li3PO4 with neural network potential | Wenwen Li; Yasunobu Ando; Emi Minamitani et al. | 2017 | The Journal of Chemical Physics | 154 | [10.1063/1.4997242](https://doi.org/10.1063/1.4997242) |  |
| Impact of the Local Environment on Li Ion Transport in Inorganic Components of Solid Electrolyte Interphases | Taiping Hu; Jianxin Tian; Fuzhi Dai et al. | 2022 | Journal of the American Chemical Society | 107 | [10.1021/jacs.2c11521](https://doi.org/10.1021/jacs.2c11521) |  |
| Thermal conductivity modeling using machine learning potentials: application to crystalline and amorphous silicon | Xin Qian; Shiyu Peng; Xiaobo Li et al. | 2019 | Materials Today Physics | 103 | [10.1016/j.mtphys.2019.100140](https://doi.org/10.1016/j.mtphys.2019.100140) |  |
| A unified deep neural network potential capable of predicting thermal conductivity of silicon in different phases | Ruiyang Li; Eungkyu Lee; Tengfei Luo | 2020 | Materials Today Physics | 102 | [10.1016/j.mtphys.2020.100181](https://doi.org/10.1016/j.mtphys.2020.100181) |  |

### Bloco QC (439 únicos)

| Título | Autores | Ano | Veículo | Citações | DOI | OpenAlex 2-yr mean citedness |
|---|---|---|---|---|---|---|
| Hyperuniform states of matter | Salvatore Torquato | 2018 | Physics Reports | 485 | [10.1016/j.physrep.2018.03.001](https://doi.org/10.1016/j.physrep.2018.03.001) |  |
| Localization and delocalization of light in photonic moiré lattices | Peng Wang; Yuanlin Zheng; Xianfeng Chen et al. | 2019 | Nature | 482 | [10.1038/s41586-019-1851-6](https://doi.org/10.1038/s41586-019-1851-6) |  |
| Delocalization of a disordered bosonic system by repulsive interactions | B. Deissler; Matteo Zaccanti; G. Roati et al. | 2010 | Nature Physics | 273 | [10.1038/nphys1635](https://doi.org/10.1038/nphys1635) |  |
| Topological triple phase transition in non-Hermitian Floquet quasicrystals | Sebastian Weidemann; Mark Kremer; Stefano Longhi et al. | 2022 | Nature | 225 | [10.1038/s41586-021-04253-0](https://doi.org/10.1038/s41586-021-04253-0) |  |
| Disorder-Enhanced Transport in Photonic Quasicrystals | Liad Levi; Mikael C. Rechtsman; Barak Freedman et al. | 2011 | Science | 205 | [10.1126/science.1202977](https://doi.org/10.1126/science.1202977) |  |
| Generalized Aubry-André self-duality and mobility edges in non-Hermitian quasiperiodic lattices | Tong Liu; Hao Guo; Yong Pu et al. | 2020 | Physical review. B./Physical review. B | 148 | [10.1103/physrevb.102.024205](https://doi.org/10.1103/physrevb.102.024205) |  |
| Topological Phase Transitions and Mobility Edges in Non-Hermitian Quasicrystals | Quan Lin; Tianyu Li; Lei Xiao et al. | 2022 | Physical Review Letters | 136 | [10.1103/physrevlett.129.113601](https://doi.org/10.1103/physrevlett.129.113601) |  |
| Localization and delocalization of light in photonic moiré lattices | Peng Wang; Yuanlin Zheng; Xianfeng Chen et al. | 2020 | LA Referencia (Red Federada de Repositorios Institucionales de Publicaciones Científicas) | 121 | [(link)](https://openalex.org/W3102201054) |  |
| Bose-Einstein condensates in optical quasicrystal lattices | Laurent Sanchez-Palencia; L. Santos | 2005 | Physical Review A | 117 | [10.1103/physreva.72.053607](https://doi.org/10.1103/physreva.72.053607) |  |
| Observing Localization in a 2D Quasicrystalline Optical Lattice | Matteo Sbroscia; Konrad Viebahn; Edward Carter et al. | 2020 | Physical Review Letters | 105 | [10.1103/physrevlett.125.200604](https://doi.org/10.1103/physrevlett.125.200604) |  |

## Sugestões

- Bloco PSC: openalex 4.569 acertos -- provavelmente um termo genérico está por trás disso; restrinja um grupo ou acrescente um mais específico antes de ler.
- Bloco PSC: as contagens diferem >20x entre backends (175 a 4.569); gramática e cobertura divergem, portanto não compare esses números -- descubra aqui, cite uma única fonte.
- Bloco NOV: zero acertos em todos os backends. Ou a interseção é realmente vazia (um achado -- verifique os sinônimos primeiro) ou um grupo é estreito demais; tente remover um grupo e executar de novo.
- Bloco QC: as contagens diferem >20x entre backends (17 a 414); gramática e cobertura divergem, portanto não compare esses números -- descubra aqui, cite uma única fonte.
- 2 par(es) bloco/backend atingiram o limite `--limit` (300); aumente-o (maior total 4.569) se precisar do conjunto completo de registros em vez da fatia mais citada.
- Nenhum backend de nível de citação (Scopus, Web of Science, NASA ADS) participou desta busca; acrescente o ADS (token gratuito) ou o Scopus antes de citar contagens.
- O status de acesso aberto não foi consultado; execute de novo com `--pdfs` (opcionalmente `--pdf-blocks`) para coletar links legais de PDF em AA via Unpaywall.
- As etapas manuais do fluxo PRISMA estão vazias: preencha prisma.json (triados / excluídos / avaliados / incluídos) e execute report.py de novo para completar o diagrama.
- Bloco PSC: o total de acertos passou de 14.620 (execução 20260828T100120) para 4.744; alguma deriva é esperada à medida que os índices crescem, mas um salto grande geralmente significa que a consulta mudou -- compare o queries.json das duas execuções.
- Bloco MLP: o total de acertos passou de 838 (execução 20260828T100120) para 376; alguma deriva é esperada à medida que os índices crescem, mas um salto grande geralmente significa que a consulta mudou -- compare o queries.json das duas execuções.
- Bloco QC: o total de acertos passou de 978 (execução 20260828T100120) para 585; alguma deriva é esperada à medida que os índices crescem, mas um salto grande geralmente significa que a consulta mudou -- compare o queries.json das duas execuções.
