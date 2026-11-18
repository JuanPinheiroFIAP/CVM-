# Exportações do Painel CVM — dicionário de dados

Dados abertos da CVM já processados (captação de **todas as classes de fundos com Informe
Diário** — Multimercado, Renda Fixa, Ações, Cambial e FMP-FGTS; publicações/fatos relevantes; e
composição de carteira), exportados para consumo por outros projetos. FIDC, FII, FIP e FIAGRO não
têm informe diário de captação e não estão nas tabelas de captação. Gerados
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
  bases/                    # ⭐ base_fundos e base_gestoras: os "tudões", ligáveis por CNPJ
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

## Bases "tudão" — para relacionar fundos e gestoras ⭐

| tabela | grão | chave |
|---|---|---|
| `bases/base_fundos` | 1 fundo (classe de cotas) | `cnpj_fundo` |
| `bases/base_gestoras` | 1 gestora | `cnpj_gestora` |

**Como relacionar:** `base_fundos.cnpj_gestora = base_gestoras.cnpj_gestora` (muitos fundos para
uma gestora). Os CNPJs vêm do registro da CVM e estão formatados (`00.000.000/0000-00`; gestora PF
aparece como CPF). `cnpj_fundo` é o CNPJ **da classe**; `cnpj_fundo_pai` é o do fundo "pai" (uma
mesma pessoa jurídica pode ter várias classes). Também existe `cnpj_administrador`. Gestoras e
CNPJs têm correspondência 1 para 1 no cadastro; fundos sem gestora informada ficam com
`cnpj_gestora` vazio. As demais tabelas de captação por fundo/gestora também trazem
`cnpj_gestora`, então podem ser ligadas às bases pela mesma chave.

- **`base_fundos`**: CNPJs, nome, gestora, administrador, `classe_cvm`, `classe_anbima`,
  público-alvo, flags (`exclusivo`, `previdencia`, `fundo_de_cotas`), `pl_atual`, `porte_fundo`
  (Pequeno < R$ 100 mi · Médio < R$ 1 bi · Grande ≥ R$ 1 bi), cotistas, captação/PL/rentabilidade em
  todas as janelas (`capt_liquida_21d`…), captação e PL inicial por mês
  (`capt_liquida_mes_AAAAMM`, `pl_inicio_mes_AAAAMM`), `pct_pl_na_gestora`, `rank_pl_na_gestora` e os
  indicadores da gestora (`gestora_*`).
- **`base_gestoras`** (universo `sem_cotas`, isto é, sem FICs, para não duplicar PL): `cnpj_gestora`,
  `gestora`, `n_fundos`, `n_fundos_exclusivos`, `n_fundos_grandes/medios/pequenos`, `pl_atual`,
  `porte_gestora` (Pequena < R$ 1 bi · Média < R$ 10 bi · Grande ≥ R$ 10 bi), `rank_pl`,
  `share_pl_pct`, PL por classe CVM (`pl_multimercado`, `pl_renda_fixa`, `pl_acoes`, `pl_cambial`,
  `pl_fmp_fgts`), captação por janela (`capt_liquida_j`, `capt_bruta_j`, `resgate_j`, `pl_inicial_j`,
  `pct_pl_j`, `fundos_com_captacao_j`, `delta_cotistas_j`), rankings (`rank_pct_pl_j` entre gestoras
  com PL ≥ R$ 100 mi; `rank_capt_liquida_j`) e captação/PL por mês.
- Exemplo (Python): `bf.merge(bg, on="cnpj_gestora", suffixes=("", "_g"))`.

## Tabelas

### `captacao/fundos/` — uma linha por fundo (classe)

| tabela | grão | chave |
|---|---|---|
| `captacao_fundos` | 1 fundo | `cnpj` |
| `captacao_fundos_janelas` | 1 fundo × janela (formato longo) | `cnpj`, `janela` |
| `captacao_fundos_mensal` | 1 fundo × mês (13 últimos meses) | `cnpj`, `mes` |
| `captacao_fundos_diaria` | 1 fundo × pregão (~63 últimos) | `cnpj`, `data` |

`captacao_fundos` traz cadastro (`fundo`, `gestora`, `administrador`, `classe_cvm`, `classe_anbima`,
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
| `captacao_gestoras_classe_janelas` | 1 gestora × classe CVM × classe ANBIMA × janela × universo | `gestora`, `classe_cvm`, `classe_anbima`, `janela`, `universo` |
| `captacao_gestoras_classe_cvm_janelas` | 1 gestora × classe CVM × janela × universo | `gestora`, `classe_cvm`, `janela`, `universo` |
| `captacao_gestoras_mensal` | 1 gestora × mês × universo | `gestora`, `mes`, `universo` |
| `captacao_gestoras_diaria` | 1 gestora × pregão × universo | `gestora`, `data`, `universo` |

`captacao_gestoras_ranking` tem `n_fundos`, `pl_atual`, `share_pl_pct` (participação no PL do
universo) e, por janela, `capt_liquida_j` e `pct_pl_j`.

> A antiga `captacao_gestoras_fundos` foi incorporada a `bases/base_fundos`.

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

## Como cada coluna é calculada (por tabela)

Fonte da captação: **Informe Diário de Fundos** (CVM) — `CAPTC_DIA`, `RESG_DIA`,
`VL_PATRIM_LIQ`, `NR_COTST`, `VL_QUOTA` por classe e dia (subclasses somadas na classe) — mais o
**Registro de Fundo/Classe** para o cadastro. Valores em R$ cheios.

**Conceitos usados em várias tabelas**

| termo | cálculo |
|---|---|
| `capt_liquida` | Σ (captação − resgate) dos pregões da janela (do pregão seguinte à data-base até o último dado) |
| `capt_bruta` / `resgate` | Σ da captação / Σ dos resgates no mesmo período |
| `pl_inicial` | PL do fundo na **data-base** da janela (último valor conhecido até essa data) |
| `pct_pl` | `capt_liquida ÷ pl_inicial × 100`; vazio quando `pl_inicial ≤ 0` |
| `delta_cotistas` | nº de cotistas na última data − nº na data-base |
| `rentab_pct` | `cota_última ÷ cota_data-base − 1`, em %. Para classes com subclasses, usa a cota da subclasse de maior PL do dia |
| `janela` / `data_base` | 1d, 5d, 21d, 63d, 126d, 252d = nº de pregões para trás; MTD/YTD = último pregão do mês/ano anterior |
| `classe_cvm` | classificação do registro CVM: Multimercado, Renda Fixa, Ações, Cambial, FMP-FGTS |
| `classe_anbima` | classificação ANBIMA do registro (a "linha" do fundo) |
| `previdencia` | `true` quando a classe ANBIMA contém "Previdência" |

**`captacao_fundos` / `captacao_fundos_janelas`** — uma linha por classe (fundo). `pl_atual` = PL do
último pregão; `cotistas` = nº de cotistas do último pregão. As colunas por janela seguem a tabela
acima. Universo: classes em funcionamento normal, com informe nos últimos 5 pregões e PL > 0.

**`captacao_fundos_mensal`** — por fundo e mês: `capt_liquida` = Σ captação líquida dos pregões
do mês (o último mês é parcial); `pl_inicio_mes` = PL no último pregão do mês anterior;
`pct_pl = capt_liquida ÷ pl_inicio_mes × 100`.

**`captacao_fundos_diaria`** — captação líquida de cada pregão dos últimos 63. **Dias com
`capt_liquida = 0` são omitidos** (ausência = 0), para reduzir o tamanho.

**Tabelas por gestora** — agrupam os fundos pelo nome da gestora do cadastro:
`n_fundos` = nº de classes; `n_fundos_com_base` = nº com `pl_inicial > 0`; `pl_atual` = Σ PL
atual; **`capt_liquida`, `capt_bruta`, `resgate`, `pl_inicial` = somas apenas dos fundos com
`pl_inicial > 0`** (fundo criado dentro da janela fica de fora); `fundos_com_captacao` = nº com
`capt_liquida > 0`; `delta_cotistas` = Σ; `pct_pl = Σ capt_liquida ÷ Σ pl_inicial × 100`
(média ponderada pelo PL). `share_pl_pct` (ranking) = `pl_atual` da gestora ÷ Σ `pl_atual` de todas
as gestoras do mesmo `universo` × 100. `captacao_gestoras_classe_janelas` e
`captacao_gestoras_classe_cvm_janelas` repetem essas contas separando por classe ANBIMA (dentro da
classe CVM) e só por classe CVM.

**`bases/base_fundos`** — a linha do fundo + colunas da gestora (`gestora_*`, universo `sem_cotas`); `pct_pl_na_gestora = pl_atual do fundo ÷ gestora_pl_atual × 100`; `rank_pl_na_gestora` = posição do fundo por PL dentro da gestora. **`bases/base_gestoras`** usa as somas por gestora descritas acima (universo `sem_cotas`); rankings = posição em ordem decrescente de `pct_pl` (só gestoras com PL ≥ R$ 100 mi) e de `capt_liquida`.

**`captacao_gestoras_mensal` / `_diaria`** — somas por gestora (e `universo`) dos valores mensais /
diários dos fundos; `pct_pl` mensal = Σ `capt_liquida` ÷ Σ `pl_inicio_mes` × 100.

> **Painel (tela)**: usa as mesmas contas com o universo **sem exclusivos e sem FIC** (padrão),
> alternável pelos filtros do topo; os valores aparecem em R$ mi/bi. A aba "Como é calculado" do
> painel descreve cada tabela da tela coluna por coluna (porte, peers, média por fundo etc.).

**Publicações** — `publicacoes_*` são cópias das listas do IPE/Eventuais da CVM sem cálculo
(recompras = documentos do IPE cujo *assunto/espécie* contém termos de recompra, excluídas OPAs).
**Carteiras** — `valor_mercado` = `VL_MERC_POS_FINAL` do CDA; `pct_pl = valor_mercado ÷ PL do
fundo × 100`; `delta_pp = pct_pl − pct_pl_anterior` (mês de carteira anterior);
`carteiras_tipos_aplicacao` soma `pct_pl` por tipo de aplicação. Escopo atual: fundos
**Multimercado** abertos com PL ≥ mínimo.

## Atualização

Gerado por `atualizar.bat` (ou `python painel.py`), que roda `baixar_cvm.py` → `monitor.py` →
`publicacoes.py` → junta tudo. O timestamp de cada tabela está em `catalogo.json` (`gerado`) e
no painel (`Dados até ... · gerado em ...`).
