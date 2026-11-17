# Painel CVM

Painel único com dados abertos da CVM:

- **Captação Multimercado por gestora**: captação líquida em várias janelas, ranking, peers e acompanhamento de gestoras.
- **Publicações CVM**: fatos relevantes, recompras, assembleias, eventos de fundos e composição de carteira (CDA).

## Como usar

Requer Python 3: `pip install -r requirements.txt` (pandas, numpy, pyarrow, xlsxwriter).

```
atualizar.bat      # baixa os dados, gera painel_cvm.html e abre o painel
abrir_painel.bat   # abre o painel já gerado
```

Abra sempre pelo servidor local (`servidor.py`): os links dos documentos da CVM dependem dele.

Os dados baixados (`data/`), os CSVs (`saidas/`) e o `painel_cvm.html` são gerados localmente e ficam fora do Git.

## Exportações

Todas as tabelas do painel saem completas (sem filtros da tela) em **CSV, Excel e Parquet**, na pasta `exportacoes/` e na aba **Exportações** do painel:

- captação por fundo e por gestora (janelas, mensal, diária, por classe ANBIMA);
- `captacao_gestoras_fundos`: base única, uma linha por fundo, com os indicadores do fundo ao lado dos da sua gestora (PL, captação, ranking) e o % do PL da gestora que está em cada fundo — pensada para alimentar outros relatórios;
- fundo de cotas (FIC) investe quase todo o PL no seu fundo master, que também entra na base — somar os dois na gestora duplicaria o PL/fluxo. Por isso as tabelas de gestora têm a opção de universo `sem_cotas` (exclui FICs; é o que o painel e a `captacao_gestoras_fundos` usam por padrão), além de `todos` e `sem_exclusivos`. O campo `fundo_de_cotas` identifica os FICs linha a linha;
- publicações (fatos relevantes, recompras, assembleias, fundos, todas as categorias do IPE);
- carteiras (todas as posições e % por tipo de aplicação).

CSV usa `;` como separador, `,` como decimal e UTF-8 com BOM (abre direto no Excel em português). Valores em R$.
