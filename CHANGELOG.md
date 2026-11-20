# Changelog

## 8.0.0 — app web estilo F1
- **Nova interface web** (HTML/CSS/JS) servida por FastAPI: `mangue-logger serve`. Substitui a interface Qt.
- Telemetria com cursor/zoom/pan sincronizados, eixo tempo/distância, canais matemáticos, faixa de fases.
- **Comparar:** delta de tempo × distância e mini-setores com cores de F1.
- **Replay** com LEDs de RPM, barra de aceleração e scrub.
- Tela de Motor/CVT, Setups (Welch), Runs (metadados), Biblioteca, Relatórios (com prévia) e Config (perfil/sessão).
- Demonstração embutida; upload por arrastar-e-soltar; projeto `.mlproj` (schema 2; schema 1 ainda abre).
- Filtro agora é `FilterConfig` tipado (Hz) na sessão; API valida corte < Nyquist.
- Testes: API, JS (node) e E2E no Chromium; CI atualizado.
### Removido
- Camada PyQt6/pyqtgraph (`presentation/`). `PyQt6-WebEngine` virou opcional (janela própria).

## 7.x
- Arquitetura em camadas, ReportModel, relatórios PDF/Excel/HTML, CLI, perfis, biblioteca SQLite, correção do cache entre runs.
