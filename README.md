# Mangue Logger 8

App de telemetria automotiva (Baja SAE) no estilo das ferramentas de análise da F1: traços sincronizados,
**delta de tempo por distância**, **mini-setores** (roxo / verde / amarelo), replay com **LEDs de RPM**, análise de CVT,
comparação estatística de setups e relatórios (PDF, Excel, HTML). Interface web (HTML/CSS/JS) servida localmente.

## Instalação e uso

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
mangue-logger serve                                     # abre http://127.0.0.1:8765 no navegador
```

Sem dados? Na primeira tela, clique em **Carregar demonstração** (4 runs sintéticas, com setups diferentes).
Para usar os seus: arraste os CSVs para a janela ou use **＋ Carregar**.

Janela própria (sem navegador), opcional: `pip install -e ".[desktop]"` e `mangue-logger gui`.

### Formato do CSV

Colunas `f1` e `f2` com contagem de pulsos por amostra bruta: **f1 = RPM, f2 = velocidade** (configurável em *Config → Perfil*;
CSVs da v6 usavam o inverso). Metadados opcionais ficam em `run.csv.meta.json`:

```json
{"setup": {"mola": "dura", "peso_cvt": "46"}, "tags": ["enduro"], "notes": "pista seca"}
```

## Telas

| Tela | O que faz |
|---|---|
| **Visão geral** | KPIs, resumo, ranking estilo *timing tower* (gap para o líder), barra de fases, insights filtráveis |
| **Telemetria** | Velocidade, RPM e aceleração empilhados; cursor/zoom/pan sincronizados (o zoom rebusca mais resolução); eixo tempo ou distância; sinal bruto; **canais matemáticos** (`rpm / (vel + 1)`); faixa de fases |
| **Comparar** | Δ tempo × distância contra uma referência ★, **mini-setores** com cores de F1, tempo final por run |
| **Replay** | Painel de bordo: velocidade, LEDs de RPM, barra de aceleração/frenagem, fase, play/scrub 0,5×–4× |
| **Motor** | CVT (RPM × velocidade, mediana e P10–P90), RPM de saída/sustentado, tempo por faixa de RPM e velocidade, FFT do RPM |
| **Setups** | Agrupa runs por um campo do setup e testa se a diferença é real (Welch, IC 95%, d de Cohen) |
| **Runs** | Qualidade dos dados e editor de setup/tags/notas por run |
| **Biblioteca** | Todas as runs já carregadas (SQLite): busca por nome, tag, setup |
| **Relatórios** | PDF, Excel (gráficos nativos), HTML, JSON, CSV + prévia |
| **Config** | Perfil do veículo (sensor, limiares das regras, faixa de potência), setup global, projeto `.mlproj` |

O **Filtro** (Butterworth, Bessel, Chebyshev, Savitzky-Golay, mediana, média móvel; corte em Hz, zero-fase) fica numa gaveta
acessível de qualquer tela.

## CLI

```bash
mangue-logger analyze run1.csv run2.csv --cutoff-hz 1.5 --excel out.xlsx --pdf out.pdf --html out.html
mangue-logger analyze runs/*.csv --group-by peso_cvt --metric vel_mean     # Welch entre setups
mangue-logger quality runs/*.csv
```

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest              # unidade, propriedades, API, JS (node) e E2E no Chromium (Qt WebEngine)
ruff check src tests && mypy
```

Documentação técnica: [ARCHITECTURE.md](ARCHITECTURE.md) · API interativa em `/api/docs` com o servidor rodando.
