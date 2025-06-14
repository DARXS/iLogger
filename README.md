# MANGUE iLOGGER

**MANGUE LOGGER** é uma plataforma de análise de dados de telemetria veicular, desenvolvida em Python com PyQt6. O software é projetado para processar, visualizar e comparar dados de múltiplos testes de veículos (denominados "RUNs"), oferecendo uma suíte de ferramentas para engenheiros otimizarem o processo de tomada de decisão com base em evidências quantitativas.

O sistema transforma arquivos de dados brutos `.csv` em um dashboard interativo, permitindo a aplicação de filtros digitais, extração de métricas de desempenho (KPIs) e geração de relatórios técnicos detalhados nos formatos PDF e Excel.

## Funcionalidades Técnicas

-   **Análise Comparativa de Corridas (Runs)**: Permite o carregamento e a análise simultânea de múltiplos arquivos de dados. O estado da aplicação, contendo os dados de todas as corridas carregadas, é gerenciado centralmente para garantir consistência entre as diferentes telas de visualização.

-   **Processamento de Sinais e Filtragem Digital**: Implementa uma robusta camada de processamento de sinais utilizando a biblioteca `SciPy.signal`. Os seguintes filtros são aplicáveis em tempo real a qualquer canal de dados:
    -   Butterworth
    -   Chebyshev I & II
    -   Bessel
    -   Savitzky-Golay
    -   Filtro de Mediana
    -   Média Móvel

A aplicação dos filtros é não destrutiva, ocorrendo na camada de visualização e permitindo o ajuste dinâmico de parâmetros (ordem, frequência de corte, etc.) com atualização instantânea do gráfico.

-   **Visualização de Dados Dinâmica com `pyqtgraph`**: Utiliza a biblioteca `pyqtgraph`, otimizada para aplicações científicas e de engenharia, para renderizar gráficos interativos de alta performance. As visualizações incluem séries temporais, gráficos de dispersão (XY) e painéis de dashboard compostos.

-   **Extração de Métricas de Desempenho (KPIs)**: Automatiza o cálculo de indicadores chave de performance a partir do sinal de velocidade filtrado. As métricas incluem velocidade máxima ($v_{max}$), velocidade média, RPM máximo e médio, aceleração máxima, e a variação percentual entre as corridas.

-   **Construtor de Gráficos Customizados**: Oferece uma interface para que o usuário crie suas próprias visualizações, mapeando dinamicamente qualquer canal de dados disponível para os eixos X e Y, incluindo suporte a um eixo Y secundário para correlação de grandezas físicas distintas.

-   **Geração de Relatórios Técnicos (PDF & Excel)**:
    -   **PDF (`ReportLab`)**: Gera um documento PDF técnico contendo os metadados do setup do teste, tabelas de KPIs, observações textuais e snapshots de todos os gráficos gerados com os filtros aplicados.
    -   **Excel (`XlsxWriter`)**: Exporta um dashboard analítico em formato `.xlsx`. O arquivo é estruturado em múltiplas planilhas:
        1.  **Dashboard**: Gráficos nativos do Excel para interatividade e métricas principais.
        2.  **Setup e Métricas**: Tabelas com os dados de setup e os KPIs calculados.
        3.  **Dados Processados**: Planilhas individuais para cada RUN com os dados filtrados.
        4.  **Tidy Data**: Uma planilha contendo todos os dados em formato "tidy", otimizado para importação em outras ferramentas de análise (R, Power BI, etc.).

## Tech Stack

-   **Core & GUI**:
    -   **Python 3.8+**: Linguagem base do projeto.
    -   **PyQt6**: Framework para a construção da interface gráfica, utilizando o sistema de Signals & Slots para comunicação entre componentes.
-   **Análise e Manipulação de Dados**:
    -   **NumPy**: Para operações numéricas eficientes em arrays.
    -   **Pandas**: Para estruturação, manipulação e análise de dados através de DataFrames.
    -   **SciPy**: Para algoritmos científicos, especificamente o pacote `signal` para a implementação dos filtros digitais.
-   **Visualização**:
    -   **pyqtgraph**: Para plotagem de gráficos 2D de alta performance integrados à UI PyQt.
-   **Estilização e Relatórios**:
    -   **qt-material**: Tema para estilização moderna da interface.
    -   **ReportLab**: Para a geração programática de documentos PDF.
    -   **XlsxWriter**: Engine para o `pandas.ExcelWriter` que permite a criação de arquivos Excel complexos com gráficos e formatação.

## Arquitetura e Descrição dos Arquivos

O projeto adota uma arquitetura desacoplada, similar ao padrão Model-View-Controller (MVC), para promover a separação de responsabilidades, manutenibilidade e escalabilidade.

-   **Model (Lógica e Dados)**: Representado pelos diretórios `data`, `services` e `state`.
-   **View (Interface do Usuário)**: Representado pelo diretório `ui`.
-   **Controller (Lógica de Controle)**: A lógica de orquestração está principalmente na `main_window.py`, que conecta as ações da View aos Services.

---

### Descrição Detalhada dos Arquivos

#### Arquivos Raiz

-   **`main.py`**: O ponto de entrada da aplicação. Sua única responsabilidade é instanciar a `QApplication` e a `MainWindow`, e iniciar o loop de eventos da aplicação.
-   **`config.py`**: Arquivo de configuração centralizado. Define constantes globais como o nome e versão da aplicação, constantes físicas (ex: $g = 9.81 m/s^2$), parâmetros padrão para os filtros digitais e outras configurações estáticas para evitar "magic numbers" no código.
-   **`requirements.txt`**: Documento que especifica todas as dependências externas do projeto, permitindo a fácil recriação do ambiente de execução com `pip install -r requirements.txt`.

#### Diretório `data/`

-   **`run_data.py`**: Define a classe `RunData`, que atua como um modelo de dados. Cada instância desta classe encapsula todos os dados e metadados de uma única corrida (um arquivo `.csv`). Ela armazena o `DataFrame` do Pandas e provê métodos para cálculos básicos (como conversão de frequência para velocidade) sobre seus próprios dados.

#### Diretório `state/`

-   **`app_state.py`**: Implementa um gerenciador de estado compartilhado. Ele mantém a lista de objetos `RunData` que estão atualmente carregados na aplicação, além do setup geral. Isso desacopla os componentes da UI, que podem ler o estado atual a partir deste módulo em vez de passarem dados diretamente entre si, simplificando o fluxo de dados.

#### Diretório `services/`

-   **`processing_service.py`**: Contém a lógica de negócio principal para a análise de dados. Este serviço recebe a lista de `RunData` do `app_state` e executa os cálculos estatísticos comparativos (KPIs), retornando os resultados em estruturas de dados (normalmente DataFrames) prontas para serem exibidas na UI.
-   **`report_service.py`**: Orquestra a criação de relatórios em PDF usando a biblioteca `ReportLab`. Ele consome os dados do `app_state` e os resultados do `processing_service` para montar dinamicamente o documento, posicionando texto, tabelas (`Platypus Table`) e imagens dos gráficos.
-   **`file_service.py`**: Responsável pela exportação de dados para arquivos, primariamente o dashboard em Excel. Utiliza o `pandas.ExcelWriter` com a engine `xlsxwriter` para criar um arquivo multi-planilha, formatar células e embutir gráficos.

#### Diretório `ui/`

-   **`main_window.py`**: A classe `MainWindow` é o coração da interface gráfica. Ela monta a janela principal, instancia e organiza todos os widgets (usando `QStackedWidget` para a navegação entre as telas), define a barra de ferramentas (`QToolBar`) e conecta os sinais dos widgets (ex: cliques de botão) aos slots que invocam os serviços apropriados.

#### Diretório `ui/widgets/`

Este diretório contém todos os componentes de UI modulares e reutilizáveis.

-   **`navigation_panel.py`**: O painel de navegação à esquerda. Contém os botões que emitem sinais para que a `MainWindow` alterne a visualização no `QStackedWidget`.
-   **`controls_panel.py`**: A primeira tela da aplicação. Contém os widgets para seleção de arquivos, entrada de dados de setup e o botão para iniciar a análise.
-   **`plot_widgets.py`**: Define uma série de widgets especializados, cada um contendo um `pyqtgraph.PlotItem` e a lógica de plotagem para uma visualização específica (ex: `VelocityPlotWidget`, `AccelerationPlotWidget`). Cada um desses widgets também instancia seu próprio `FilterControlPanel`.
-   **`filter_control_panel.py`**: Um widget crucial e reutilizável. Fornece a interface (sliders, comboboxes) para o usuário selecionar e configurar um filtro. Ele emite um `pyqtSignal` sempre que um parâmetro de filtro é alterado, permitindo que o widget de gráfico pai se atualize.
-   **`dashboard_widget.py`**: Constrói a tela de dashboard, organizando múltiplos widgets de gráfico em um layout de grade (`QGridLayout`) para uma visão geral consolidada.
-   **`custom_plot_widget.py`**: Implementa a funcionalidade de criação de gráficos personalizados, contendo comboboxes para a seleção de canais de dados para os eixos X, Y1 e Y2.

# Estrutura do Projeto iLogger

```
iLogger/
├── main.py                 # Ponto de entrada da aplicação (Entry Point)
├── config.py               # Módulo de configuração central
├── requirements.txt        # Dependências do projeto

├── data/
│   └── run_data.py         # Classe de modelo para uma corrida (RUN)

├── services/
│   ├── processing_service.py   # Serviço para processamento de dados e estatísticas
│   ├── report_service.py       # Serviço para geração de relatórios PDF
│   └── file_service.py         # Serviço para exportação de arquivos (Excel)

├── state/
│   └── app_state.py        # Módulo de gerenciamento de estado da aplicação

└── ui/
    ├── main_window.py          # Janela principal (View principal e orquestrador da UI)
    ├── resources/              # Ativos estáticos (ícones, etc.)
    └── widgets/                # Componentes de UI reutilizáveis (Widgets)
        ├── controls_panel.py
        ├── custom_plot_widget.py
        ├── dashboard_widget.py
        ├── filter_control_panel.py
        ├── navigation_panel.py
        └── plot_widgets.py
```
## Instalação e Execução

1.  **Clone o repositório:**
    ```bash
    git clone https://your-repository-url/iLogger.git
    cd iLogger
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    # Windows: venv\Scripts\activate | macOS/Linux: source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Execute a aplicação:**
    ```bash
    python main.py
    ```
