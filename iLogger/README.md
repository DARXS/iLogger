# MANGUE LOGGER v2.0

**MANGUE LOGGER** is a powerful desktop application designed for the analysis and visualization of vehicle dynamics data. Built for engineering teams, particularly in contexts like Baja SAE competitions, it transforms raw sensor data from test runs into actionable insights through interactive plots, statistical analysis, and comprehensive reports.

![image](https://user-images.githubusercontent.com/12952802/183290940-818a7f01-706f-47a3-8994-0a37e8c1ac02.png) 

## Key Features

-   **Multi-File Analysis**: Load and compare data from multiple CSV files simultaneously.
-   **Interactive Visualizations**: Explore data through a variety of plots, including time series, acceleration profiles, and RPM vs. Velocity relationships.
-   **Advanced Digital Filtering**: Apply and instantly visualize the effects of various filters (Butterworth, Savitzky-Golay, Chebyshev, etc.) with adjustable parameters. Each plot's filters are managed independently.
-   **Statistical Summary**: Automatically generate key performance metrics (max/average velocity, max/average RPM, max acceleration, etc.) for each run.
-   **Comparative Analysis**: View statistical tables and bar charts that compare metrics and show percentage variations across different runs.
-   **Custom Plot Builder**: Create custom plots by choosing any available data channel for the X and Y axes, including a secondary Y-axis.
-   **Dashboard View**: Display a grid of key performance plots for an at-a-glance overview.
-   **Comprehensive Reporting**:
    -   Generate detailed **PDF reports** including setup information, observations, statistical tables, and all generated plots.
    -   Export processed data from all runs to a single **Excel file** (`.xlsx`) for further analysis.

## Tech Stack

-   **GUI Framework**: [PyQt6](https://www.riverbankcomputing.com/software/pyqt/)
-   **UI Styling**: [qt-material](https://github.com/UN-GCPDS/qt-material)
-   **Data Plotting**: [pyqtgraph](http://www.pyqtgraph.org/)
-   **Data Manipulation**: [Pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/)
-   **Scientific Computing**: [SciPy](https://scipy.org/)
-   **Report Generation**: [Matplotlib](https://matplotlib.org/), [XlsxWriter](https://xlsxwriter.readthedocs.io/)

## Project Structure

The project is organized into a modular structure to separate concerns:

```
iLogger/
├── config.py               # Application constants (e.g., app name, physical values, filter defaults)
├── main.py                 # Main application entry point
├── requirements.txt        # Project dependencies
|
├── data/
│   └── run_data.py         # Class for encapsulating and processing data of a single run
|
├── services/
│   ├── file_service.py     # Handles file operations like exporting to Excel
│   ├── processing_service.py # High-level data processing and statistics generation
│   └── report_service.py   # Handles PDF report generation
|
├── state/
│   └── app_state.py        # Manages the application's shared state (e.g., loaded data)
|
└── ui/
    ├── main_window.py      # The main application window
    ├── resources/          # Icons, images, and other UI assets
    └── widgets/            # Reusable UI components (navigation, plots, control panels)
```

## Installation

To run MANGUE LOGGER on your local machine, follow these steps.

**Prerequisites**: Python 3.8 or newer.

1.  **Clone the repository:**
    ```bash
    git clone https://your-repository-url/iLogger.git
    cd iLogger
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For macOS/Linux
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**
    The project's dependencies are listed in `requirements.txt`.
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Launch the Application:**
    ```bash
    python main.py
    ```

2.  **Load Data:**
    -   On the **Controles** tab, click **"Selecionar Arquivos CSV para Análise"**.
    -   Select one or more `.csv` files to analyze. The files must contain `f1` and `f2` columns representing sensor readings.
    -   (Optional) Fill in the **"Setup do Veículo"** and **"Observações"** fields. This information will be used in the PDF report.

3.  **Analyze Data:**
    -   Click **"Rodar Análise"**. The data will be processed, and the application will switch to the first plot.
    -   Use the **navigation panel** on the left to switch between different views:
        -   **Rotação, Velocidade, Aceleração, Distância**: Time-series plots for key metrics.
        -   **Relação RPM x Velocidade**: A plot showing the relationship between engine speed and vehicle speed.
        -   **Estatísticas**: View tables of performance metrics and their percentage variation, alongside a comparative bar chart.
        -   **Dashboard**: See a grid of the most important plots in one place.
        -   **Gráfico Personalizado**: Create your own plots from the available data channels.

4.  **Apply Filters:**
    -   In each plot view, a **"Configuração de Filtro"** panel is available on the right.
    -   Select a filter type and adjust its parameters using the sliders.
    -   The plot will update in real-time to reflect your changes. **These filters are independent for each plot.** The filters set on the "Velocidade" plot are used for the "Estatísticas" calculations.

5.  **Generate Reports:**
    -   Use the toolbar at the top of the window:
        -   **"Salvar Relatório PDF"**: Creates a comprehensive PDF with all data, tables, and plots.
        -   **"Exportar Dados para Excel"**: Saves all processed data into a `.xlsx` file, with each run in a separate sheet.

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.