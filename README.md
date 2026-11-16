# Painel CVM

Painel único com dados abertos da CVM:

- **Captação Multimercado por gestora**: captação líquida em várias janelas, ranking, peers e acompanhamento de gestoras.
- **Publicações CVM**: fatos relevantes, recompras, assembleias, eventos de fundos e composição de carteira (CDA).

## Como usar

Requer Python 3 com `pandas` e `numpy`.

```
atualizar.bat      # baixa os dados, gera painel_cvm.html e abre o painel
abrir_painel.bat   # abre o painel já gerado
```

Abra sempre pelo servidor local (`servidor.py`): os links dos documentos da CVM dependem dele.

Os dados baixados (`data/`), os CSVs (`saidas/`) e o `painel_cvm.html` são gerados localmente e ficam fora do Git.
