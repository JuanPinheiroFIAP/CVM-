# Exportações do Painel CVM — dicionário de dados

Dados abertos da CVM já processados (captação de fundos multimercado, publicações/fatos
relevantes e composição de carteira), exportados para consumo por outros projetos. Gerados
por `atualizar.bat` / `python painel.py` e regravados do zero a cada execução — não são
editados manualmente.

Este arquivo é a cópia versionada do dicionário de dados; uma cópia dele é colocada em
`exportacoes/README.md` a cada geração, pra viajar junto com os dados.

## Formatos

Cada tabela sai em três arquivos equivalentes:

- **`.parquet`** — tipos nativos (datas, números, booleanos). **Recomendado para outro código**
  (pandas, DuckDB, Power BI, Spark…): sem ambiguidade de parsing.
- **`.csv`** — separador `;`, decimal `,`, UTF-8 com BOM (abre direto no Excel em português).
- **`.xlsx`** — só quando a tabela tem até 1.048.575 linhas (limite do Excel); acima disso só
  CSV/Parquet.

## Estrutura de pastas

```
exportacoes/
  catalogo.json             # manifesto: toda tabela, com descrição, grupo, linhas, colunas e caminho
  README.md                 # esta mesma documentação
  captacao/
    fundos/                 # captacao_fundos*  (uma linha por fundo/classe)
    gestoras/                # captacao_gestoras*  (agregado por gestora)
  publicacoes/               # publicacoes_*  (fatos relevantes, recompras, assembleias, IPE)
  carteiras/                  # carteiras_*  (composição de carteira — CDA)
```

`catalogo.json` é um dict `{"<pasta>/<nome>": {...}}` (ou só `"<nome>"` quando a tabela está na
raiz). Cada entrada tem `nome`, `pasta`, `descricao`, `grupo`, `linhas`, `colunas` (lista) e
`gerado` (timestamp). Use-o para descobrir tabelas/colunas sem precisar abrir cada arquivo.

## Convenções gerais

- **Moeda**: sempre R$ (reais) cheios — nunca em mil ou milhões — em colunas `pl_*`,
  `capt_*`, `resgate_*`, `valor_*` etc.
- **Chave de fundo**: `cnpj` é o CNPJ **da classe de cotas** (não do fundo "pai"). Um fundo com
  subclasses vira uma linha por classe; quando falamos "fundo" nas descrições, é sempre nesse
  nível de classe.
- **Janelas de tempo** (sufixo `_1d`, `_5d`, `_21d`, `_63d`, `_126d`, `_252d`, `_MTD`, `_YTD` em
  colunas, ou valores da coluna `janela`): números de pregões encerrados na última data com dado
  (ou do início do mês/ano pra MTD/YTD). `pl_inicial`/`capt_liquida` etc. de uma janela são
  sempre calculados a partir do pregão-base daquela janela até o último disponível.
- **`fundo_de_cotas`** (`S`/`N`): `S` = a classe é um **FIC** (Fundo de Investimento em Cotas) —
  investe quase todo o seu PL num fundo "master", que **também aparece como linha própria** na
  mesma base. Somar PL/captação do FIC e do master juntos **duplica o valor** (é o mesmo dinheiro
  contado duas vezes). Use essa coluna pra filtrar antes de somar por gestora/classe.
- **`exclusivo`** (booleano): fundo com um único cotista — capta/resgata em lumps grandes que
  podem distorcer médias/percentuais de um grupo.
- **`universo`** (nas tabelas agregadas por gestora): `todos` | `sem_exclusivos` | `sem_cotas`.
  - `sem_cotas` é a visão **recomendada** para o tamanho real de uma gestora (exclui os FICs,
    evitando a duplicação com o master descrita acima) — é o que `captacao_gestoras_fundos` usa
    por padrão nas colunas `gestora_*`.
  - `sem_exclusivos` exclui fundos de cotista único (útil pra olhar dinâmica "de mercado", sem
    movimentos pontuais grandes dominando o agregado).
  - `todos` é a soma bruta, sem nenhum filtro — tem a duplicação FIC/master embutida.

## Tabelas

### `captacao/fundos/` — uma linha por fundo (classe)

| tabela | grão | chave |
|---|---|---|
| `captacao_fundos` | 1 fundo | `cnpj` |
| `captacao_fundos_janelas` | 1 fundo × janela (formato longo) | `cnpj`, `janela` |
| `captacao_fundos_mensal` | 1 fundo × mês (13 últimos meses) | `cnpj`, `mes` |
| `captacao_fundos_diaria` | 1 fundo × pregão (~63 últimos) | `cnpj`, `data` |

`captacao_fundos` traz cadastro (`fundo`, `gestora`, `administrador`, `classe_anbima`,
`publico_alvo`, `exclusivo`, `previdencia`, `fundo_de_cotas`, `condominio`, `data_inicio`,
`pl_atual`, `cotistas`) e, para cada janela `j`, as colunas `capt_liquida_j`, `capt_bruta_j`,
`resgate_j`, `pl_inicial_j`, `pct_pl_j` (= capt_liquida ÷ pl_inicial), `delta_cotistas_j`,
`rentab_pct_j`. `captacao_fundos_janelas` tem o mesmo conteúdo em formato longo (1 linha por
janela em vez de colunas lado a lado).

### `captacao/gestoras/` — agregado por gestora

| tabela | grão | chave |
|---|---|---|
| `captacao_gestoras_ranking` | 1 gestora × universo (formato largo) | `gestora`, `universo` |
| `captacao_gestoras_janelas` | 1 gestora × janela × universo | `gestora`, `janela`, `universo` |
| `captacao_gestoras_classe_janelas` | 1 gestora × classe ANBIMA × janela × universo | `gestora`, `classe_anbima`, `janela`, `universo` |
| `captacao_gestoras_mensal` | 1 gestora × mês × universo | `gestora`, `mes`, `universo` |
| `captacao_gestoras_diaria` | 1 gestora × pregão × universo | `gestora`, `data`, `universo` |
| `captacao_gestoras_fundos` | **1 fundo**, com a gestora ao lado ⭐ | `cnpj` |

`captacao_gestoras_ranking` tem `n_fundos`, `pl_atual`, `share_pl_pct` (participação no PL do
universo) e, por janela, `capt_liquida_j` e `pct_pl_j`.

**`captacao_gestoras_fundos` é a base recomendada para outros relatórios**: mesmas colunas de
`captacao_fundos` (nível fundo) + todas as colunas de `captacao_gestoras_ranking` (universo
`sem_cotas`) coladas ao lado com prefixo `gestora_` (ex.: `gestora_pl_atual`,
`gestora_capt_liquida_21d`) + `pct_pl_na_gestora` (quanto do PL *limpo* da gestora está nesse
fundo) + `rank_pl_na_gestora` (posição do fundo por PL dentro da própria gestora). Uma linha por
fundo, FIC ou não — `fundo_de_cotas` identifica os FICs individualmente, caso queira reconstruir
outra visão (ex.: `todos`) agrupando você mesmo.

### `publicacoes/` — fatos relevantes, recompras, assembleias, IPE

| tabela | grão | chave |
|---|---|---|
| `publicacoes_fatos_relevantes` | 1 documento de Fato Relevante (companhia aberta) | `cnpj` + `data_entrega` + `categoria` |
| `publicacoes_recompras` | 1 documento sobre recompra de ações (filtro por palavra-chave no assunto) | idem |
| `publicacoes_assembleias` | 1 documento de assembleia (edital/ata/proposta/boletim) | idem |
| `publicacoes_ipe_todas_categorias` | 1 documento, qualquer categoria do IPE (12 meses) | `cnpj` + `data_entrega` + `categoria` + `protocolo` |
| `publicacoes_fundos_fr_assembleias` | 1 documento eventual de **fundo** (não companhia): fato relevante/assembleia | `cnpj` + `data_recebimento` + `tipo` |

Todas trazem `link` (URL do documento no portal da CVM — abre direto só através do
`servidor.py` deste projeto, que contorna a página em branco do RAD).

### `carteiras/` — composição de carteira (CDA), fundos multimercado não exclusivos

| tabela | grão | chave |
|---|---|---|
| `carteiras_posicoes` | 1 posição (fundo × tipo de aplicação × ativo) no mês mais recente | `cnpj` + `tipo_aplicacao` + `ativo` |
| `carteiras_tipos_aplicacao` | 1 fundo × tipo de aplicação (agregado) | `cnpj` + `tipo_aplicacao` |

Só entram fundos com PL ≥ mínimo configurado (`--min-pl`, default R$20 mi). `pct_pl` é o % do PL
do fundo naquela posição/tipo; `pct_pl_anterior` e `delta_pp` comparam com o mês de carteira
anterior quando disponível.

## Atualização

Gerado por `atualizar.bat` (ou `python painel.py`), que roda `baixar_cvm.py` → `monitor.py` →
`publicacoes.py` → junta tudo. O timestamp de cada tabela está em `catalogo.json` (`gerado`) e
no painel (`Dados até ... · gerado em ...`).
