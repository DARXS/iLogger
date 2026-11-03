# Arquitetura

```
presentation (PyQt6/pyqtgraph) ──► application ──► domain (NumPy/SciPy puro)
        │                              ▲
        └────────► infrastructure ─────┘   (leitores, exporters, storage, logging)
```

Regra: dependências só apontam para dentro. **Impostas por `tests/test_architecture.py`**
(domínio sem Qt/I/O; aplicação sem Qt/infra; infra sem UI; sem `eval`/`exec`).

| Camada | Conteúdo |
|---|---|
| `domain/` | `Run` (imutável), `SensorConfig`, `VehicleProfile`, `FilterConfig` (cutoff em Hz), `Pipeline` → `ProcessedRun` (read-only), cache LRU, analisadores (fases, CVT, faixa de potência, Welch), regras → `Finding`, avaliador **seguro** de expressões |
| `application/` | `Session` (fonte única de estado), `ProcessingService` (dono do cache), `load_runs` (paralelo, cancelável, com progresso), `analysis` (funções puras), `RunView` (fachada de transição com a API da v6), Protocols (`RunReader`, `Exporter`) |
| `infrastructure/` | `CsvRunReader` (relatório de qualidade), DLL sem Qt, exporters (Excel/PDF/JSON/CSV, sem Qt), `WorkspaceManager` (sem efeitos no import, escrita atômica, validação), `.mlproj`, biblioteca SQLite, logging rotativo |
| `presentation/` | Janela, painéis, `Worker`/`TaskManager` (QThreadPool), `AppState` (ponte Qt ↔ Session) |

## Decisões principais

1. **Cache correto.** Chave = `(sha256 do CSV + config do sensor, hash do filtro)`. Na v6 a chave era só o filtro e runs diferentes compartilhavam resultados (regressão coberta em `test_regression_cache.py`).
2. **Dados imutáveis.** `Run` e `ProcessedRun` são read-only; a troca de estado derivado é atômica (seguro entre threads).
3. **Ids ≠ rótulos.** `ChannelRegistry` e `RunStats` usam ids estáveis; textos de UI só aparecem na apresentação.
4. **Nada de números mágicos.** Sensor e limiares das regras vivem no `VehicleProfile` (JSON, validado).
5. **UI nunca bloqueia.** Carga, análise e exportação rodam em `Worker`s; erros viram diálogo com traceback + log.
6. **Segurança.** Canais virtuais passam por interpretador de AST com lista branca (sem `eval`); workspaces importados são validados.

## Mudanças de comportamento em relação à v6 (intencionais)

- Cutoff dos filtros em **Hz** (UI/presets legados continuam funcionando; convertidos pela taxa da run).
- Distância por integração **trapezoidal** (~0,1% menor que a soma retangular da v6).
- Média móvel/mediana com borda `nearest` (v6 usava zero-padding e derrubava as pontas).
- NaN em f1/f2 continuam virando 0 pulsos, mas agora **geram aviso** de qualidade.
- Textos de insight deixaram de falar em "perfil urbano"; novas regras de CVT e faixa de potência.
- Corrigido bug herdado: painéis Comparação/Fases quebravam (`PlotItem.setBackground` não existe no pyqtgraph).

Séries filtradas (RPM, velocidade, aceleração) conferidas contra a v6 para uma run isolada: diferença ~1e-9.

## Ainda pendente (honesto)

- `presentation/panels/analysis_view.py` (~2100 linhas) foi **migrado, não refatorado**: continua um módulo grande com estilo denso. Próximo passo: um arquivo por painel + view-models.
- Exporters ainda leem de `RunView`; o `ReportModel` (dados → renderizadores) é a próxima etapa.
- Biblioteca de runs (SQLite) e comparação por setup existem no núcleo/CLI; **ainda sem tela** na GUI.
- Build PyInstaller no CI está escrito, mas não foi executado.
- DLL: só carrega no Windows; ideal é um parser Python do formato binário.
