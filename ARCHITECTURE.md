# Arquitetura

```
navegador (HTML/CSS/JS, sem build)  ──HTTP/JSON──►  web (FastAPI)  ──►  application  ──►  domain (NumPy/SciPy puro)
                                                          │                  ▲
                                                          └──► infrastructure ┘   (leitores, exporters, SQLite, logging)
```

Regras de dependência (impostas por `tests/test_architecture.py`): `domain` não conhece web/Qt/I/O; `application` não
conhece web nem infraestrutura concreta; `infrastructure` não conhece web; nenhum `eval`/`exec` no pacote.

| Camada | Conteúdo |
|---|---|
| `domain/` | `Run` imutável, `SensorConfig`, `VehicleProfile`, `FilterConfig` (Hz) → `Pipeline` → `ProcessedRun` (read-only), cache LRU, analisadores (fases, CVT, faixa de potência, Welch), regras → `Finding`, **avaliador seguro** de expressões, decimação min/max |
| `application/` | `Session`, `ProcessingService`, `load_runs` (paralelo), `analysis`, `ReportModel`/`build_report`, `RunView` |
| `infrastructure/` | `CsvRunReader` (qualidade dos dados), exporters (PDF/Excel/HTML/JSON/CSV), biblioteca SQLite, workspace, projeto `.mlproj`, logging |
| `web/` | `state.py` (AppService), `queries.py` (séries, delta, motor, visão geral), `server.py` (rotas + validação Pydantic), `demo.py`, `desktop.py` (janela opcional) |
| `web/static/` | `js/chart.js` (motor de gráficos em canvas), `js/views/*` (uma tela por arquivo), `css/app.css` |

## Decisões

1. **Cálculo no servidor, desenho no navegador.** Filtros, integração, delta e estatísticas rodam em Python (testados);
   o JS só desenha. Séries trafegam decimadas (união dos mín/máx por canal: nenhum pico se perde) e o zoom rebusca a janela.
2. **Delta de tempo por distância** (como na análise de voltas da F1): `t(d)` interpolado por run numa grade comum;
   mini-setores por diferença de `t` nas bordas; roxo = melhor entre todas, verde = melhor que a referência.
3. **Cache correto.** Chave = (SHA-256 do CSV + sensor, hash do filtro). A v6 usava só o filtro e misturava runs.
4. **Tudo validado na borda.** Pydantic nos corpos, `FilterConfig.validate` (corte < Nyquist), perfil rejeita chaves
   desconhecidas, uploads só `.csv` com nome sanitizado, expressões só via lista branca de AST.
5. **Sem build de front-end.** ES modules nativos, nenhuma dependência de CDN: funciona offline.

## Testes

- Unidade e propriedades (hypothesis) do núcleo; API com `TestClient`; utilidades JS com `node --test`.
- **E2E no Chromium real** (Qt WebEngine offscreen): carrega a demo, navega nas 10 telas sem erro de console, confere pixels
  nos canvas, hover/zoom/rebusca, canal matemático, replay, filtro, edição de metadados, biblioteca, relatórios, upload.

## Limitações conhecidas

- O app é local (um usuário, `127.0.0.1`); não há autenticação. Não exponha a porta na rede.
- Limiares das regras de CVT são valores iniciais — calibre com runs reais do carro.
- Sem GPS não há mapa de pista; as comparações usam distância integrada da velocidade.
- A DLL de leitura do log binário só carrega no Windows.
