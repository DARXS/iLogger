# Mangue Logger v7

Análise de telemetria do Mangue Baja: RPM, velocidade, aceleração, distância, fases de condução,
**análise de CVT**, insights automáticos, comparação estatística entre setups e relatórios (Excel / PDF / JSON / CSV).

## Instalação

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[gui,reports]"                         # app completo
pip install -e ".[gui,reports,dev]"                     # + ferramentas de desenvolvimento
```

## Uso

```bash
mangue-logger-gui                                       # interface gráfica (ou: python -m mangue_logger gui)

# CLI (sem Qt) — bom para lote e CI
mangue-logger quality runs/*.csv                        # só qualidade dos dados
mangue-logger analyze run1.csv run2.csv --cutoff-hz 1.5 --excel out.xlsx --pdf out.pdf
mangue-logger analyze runs/*.csv --group-by peso_cvt --metric vel_max   # Welch entre setups
```

### Metadados por run (setup do veículo)

Ao lado de `run42.csv`, crie `run42.csv.meta.json`:

```json
{"setup": {"peso_cvt": "42", "mola": "A"}, "notes": "pista seca", "tags": ["cvt-teste"]}
```

### Perfil do veículo

`src/mangue_logger/profiles/baja_default.json` define sensor (raio do pneu, furos do disco, janela/taxa),
limiares das regras e a faixa de RPM de interesse (`power_band_rpm`, desativada por padrão — ajuste ao seu motor).
Use `--profile meu_perfil.json` ou o botão **🚗 Perfil** na GUI.

## Desenvolvimento

```bash
pytest            # 89 testes (unidade, propriedades, GUI offscreen, regras de arquitetura)
ruff check src tests && mypy
```

Veja [ARCHITECTURE.md](ARCHITECTURE.md) para camadas, decisões e o que ainda está pendente.
