# Changelog

## 7.0.0
### Corrigido
- **Cache compartilhava resultados entre runs diferentes** (estatísticas e comparações idênticas).
- Painéis Comparação e Fases quebravam com pyqtgraph recente.
- `eval` em canais virtuais permitia execução de código via workspace importado.
- Exporters/DLL abriam `QMessageBox` dentro da lógica e engoliam exceções.
### Adicionado
- Arquitetura em camadas, pacote `mangue_logger`, CLI headless, perfis de veículo, `.mlproj`.
- Relatório de qualidade de dados, metadados por run, biblioteca SQLite, teste de Welch entre setups.
- Painel **CVT**, regras de CVT e faixa de potência.
- Tarefas em background com progresso; logging em arquivo; hook de exceções.
- Testes (89), CI, ruff, mypy, pre-commit.
### Alterado
- Cutoff em Hz; distância trapezoidal; bordas de média móvel/mediana (ver ARCHITECTURE.md).
