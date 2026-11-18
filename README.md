# Painel CVM

Painel único com dados abertos da CVM:

- **Captação de Fundos por gestora** (Multimercado, Renda Fixa, Ações, Cambial e FMP-FGTS): panorama de todas as gestoras com PL, porte e captação líquida; página de cada gestora com fundos, classes, gráficos e comparação com peers; aba "Como é calculado" explicando cada tabela.
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
- **bases "tudão"** (`bases/base_fundos` e `bases/base_gestoras`): uma linha por fundo e uma por gestora, com CNPJs, PL, porte e captação em todas as janelas; relacionam-se por `cnpj_gestora` (veja `EXPORTACOES.md`);
- fundo de cotas (FIC) investe quase todo o PL no seu fundo master, que também entra na base — somar os dois na gestora duplicaria o PL/fluxo. Por isso as tabelas de gestora têm a opção de universo `sem_cotas` (exclui FICs; é o que o painel e as bases usam por padrão), além de `todos` e `sem_exclusivos`. O campo `fundo_de_cotas` identifica os FICs linha a linha;
- publicações (fatos relevantes, recompras, assembleias, fundos, todas as categorias do IPE);
- carteiras (todas as posições e % por tipo de aplicação).

CSV usa `;` como separador, `,` como decimal e UTF-8 com BOM (abre direto no Excel em português). Valores em R$.

## Atualização diária (Agendador de Tarefas)

`atualizar_diario.bat` atualiza tudo **sem abrir nada** (baixa os dados novos, regenera as exportações e o painel) e grava o log em `logs/atualizacao_AAAA-MM-DD.log`; `logs/ultima_atualizacao.txt` mostra o resultado da última rodada. Código de saída 0 = ok, 1 = falhou. Uma segunda execução simultânea é ignorada (trava em `data/.atualizando.lock`).

No Agendador de Tarefas do Windows: ação **Iniciar um programa** → `...\CVMtualizar_diario.bat`, gatilho diário (a CVM não publica aos fins de semana; seg–sex basta), "Iniciar em" = pasta do projeto. Ou rode `agendar_tarefa.bat` (cria a tarefa seg–sex às 07:00).
