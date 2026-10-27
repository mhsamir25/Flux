# FLUX

A visual data pipeline platform that simplifies spreadsheet analysis through modular, interactive workflows.

---

## Overview

FLUX is a browser-based, no-code data preparation and analytics platform designed to bridge the gap between visual thinking and traditional spreadsheet software.

Traditional spreadsheet workflows force users to construct nested, brittle formulas directly inside grid cells. FLUX replaces that complexity with an intuitive visual canvas. Users assemble data workflows by connecting modular building blocks—such as filters, joins, grouping operations, data cleaners, and charts—into an end-to-end analytical pipeline.

Every transformation produces an immediate, live preview at each stage, giving users instant visibility into how their data evolves from raw file to final insight.

---

## Why Choose FLUX Over Excel or Pandas?

For decades, data analysis has been divided into two extremes: manual spreadsheets (like Microsoft Excel) and programmatic data science libraries (like Python Pandas). Both approaches present significant drawbacks for modern analytical teams.

```
+-----------------------------------------------------------------------------+
|                                    FLUX                                     |
|             The visual, modular sweet spot for modern analysis              |
+-----------------------------------------------------------------------------+
               ^                                           ^
               |                                           |
    Solves Excel's Weaknesses                   Solves Pandas' Weaknesses
    - No brittle cell coordinates               - Zero coding or syntax barriers
    - No hidden formula logic                   - Real-time visual data preview
    - No manual repetitive copy-pasting         - No Jupyter or environment setup
    - Visual, immediate error tracing           - Accessible to business analysts
```

### FLUX vs. Microsoft Excel

- **Decoupled Logic vs. Cell Coordinates:** In Excel, logic is tangled with presentation. Moving a cell, inserting a row, or renaming a header frequently results in `#REF!` or `#VALUE!` errors. In FLUX, logic is defined as self-contained operational blocks. Data flows through connections regardless of table dimensions.
- **Inspectable Stages vs. Black-Box Formulas:** Understanding an inherited spreadsheet often requires deciphering multi-line nested `INDEX(MATCH())` or `VLOOKUP` expressions across hidden tabs. FLUX makes every single intermediate step inspectable with a click.
- **True Reusability vs. Fragile Templates:** In Excel, applying last month's report to new data usually involves manual copy-pasting, formula dragging, and re-checking cell bounds. In FLUX, you simply swap the input data file; the entire pipeline re-runs cleanly with zero manual intervention.
- **Clear Error Diagnostics:** When a calculation fails in Excel, error indicators appear only in the output cells without indicating where the failure began. FLUX isolates the exact block and row where a data type mismatch or null reference originated.

### FLUX vs. Python & Pandas

- **Accessible Without Programming Skills:** Pandas is powerful but requires fluent knowledge of Python syntax, method chaining, indexing quirks, and environment management. FLUX delivers the architectural benefits of a Pandas DataFrame pipeline without writing a single line of code.
- **Instant Visual Feedback:** Working in Pandas typically requires iterative `df.head()` and `df.info()` calls in notebooks to inspect data states. FLUX displays the transformed dataset live at every node on the canvas as you build.
- **Cross-Functional Collaboration:** Code-based scripts isolate non-technical stakeholders, forcing business managers to wait on engineers for minor adjustments. FLUX visual pipelines can be read, audited, and adjusted by business analysts and technical teams alike.
- **Spreadsheet Interoperability:** Pandas scripts do not easily translate back to native spreadsheet logic. FLUX provides a built-in two-way bridge that converts visual blocks into equivalent Excel formulas and vice versa.

### Comparison Matrix

| Capability | Microsoft Excel | Python / Pandas | FLUX |
|---|---|---|---|
| **Learning Curve** | Low initially, steep for advanced formulas | Steep (requires programming) | Low (intuitive visual canvas) |
| **Logic Visibility** | Hidden inside individual cells | Code-based (abstract) | Visual flowchart of data steps |
| **Intermediate Data Previews** | Requires manual helper columns | Requires print statements/notebooks | Automatic at every node |
| **Susceptibility to Broken References** | High (coordinate-dependent) | Low | Low (schema-driven) |
| **Reusability on New Datasets** | Prone to manual copy-paste errors | High (via scripts) | High (single-click file swap) |
| **Error Diagnostics** | Generic errors (`#N/A`, `#REF!`) | Terminal tracebacks | Visual node and row highlight |
| **Formula Translation** | Native | None | Bi-directional Excel bridge |
| **Auditing & Collaboration** | Difficult on complex sheets | Requires code review | Clear visual layout for any viewer |

---

## Pipeline Nodes and How They Work

In FLUX, analytical pipelines are constructed using **Nodes**—discrete, modular blocks that perform one specific operation on data. 

Nodes have **input ports** on their left side and **output ports** on their right side. Connecting the output of one node to the input of another establishes a data path. When data is introduced at the source, it flows along these connections, transforming deterministically at each step.

```
[ Data Source ]  -->  [ Clean / Transform ]  -->  [ Aggregate / Join ]  -->  [ Chart / Export ]
 (CSV / Excel)          (Filter, Calculate)          (Group By, Pivot)        (Bar, Line, Table)
```

The node library is organized into five functional categories:

### 1. Data Source Nodes
Source nodes introduce raw data into the canvas. They parse files, detect column headers, infer data types, and serve as the entry points for all downstream operations.

- **Read CSV:** Loads comma-delimited or delimited text files. Parses rows cleanly and handles variable quoting and delimiters.
- **Read Excel (XLSX):** Ingests structured spreadsheets directly from Microsoft Excel workbooks, preserving column names and data formatting.

### 2. Transformation and Cleaning Nodes
Transformation nodes operate on rows and columns to cleanse, structure, and refine datasets before analysis.

- **Filter Rows:** Evaluates incoming rows against customizable conditions (e.g., numeric comparisons, text matching, date boundaries) to pass only relevant records downstream.
- **Add Calculated Column:** Creates new columns derived from existing fields using mathematical expressions, string manipulation, or conditional logic.
- **Fill Missing Values:** Identifies null or blank values across specified columns and populates them using configurable strategies (static defaults, forward fills, or mean values).
- **Remove Duplicates:** Identifies and eliminates redundant rows based on selected key columns or entire records.
- **Convert Data Type:** Coerces columns into explicit formats (integer, decimal, text, boolean, or date) to prevent type mismatches in subsequent mathematical operations.
- **Select Columns:** Filters out unnecessary columns to keep downstream datasets lightweight and focused.
- **Rename Columns:** Assigns business-friendly, standardized names to messy or abbreviated source headers.
- **Sort Rows:** Orders the dataset ascending or descending based on one or more sort keys.
- **Limit Rows:** Truncates datasets to a specified number of rows, useful for previewing large datasets or building top-N reports.

### 3. Join Nodes
Join nodes combine two separate data streams into a single unified dataset based on matching key values.

- **Join Node:** Combines a primary and secondary dataset based on one or more join keys. Supports standard relational join strategies:
  - **Inner Join:** Keeps only rows with matching keys in both datasets.
  - **Left Join:** Preserves all rows from the primary dataset, matching secondary data where available.
  - **Right Join:** Preserves all rows from the secondary dataset.
  - **Outer Join:** Retains all rows from both datasets, inserting nulls where records do not align.

### 4. Aggregation and Reshaping Nodes
Aggregation nodes condense row-level data into meaningful summary metrics.

- **Group By & Aggregate:** Groups records by categorical dimensions (such as Region, Department, or Product Line) and computes summary metrics across numerical fields (including Sum, Average, Count, Minimum, and Maximum).
- **Pivot Table:** Transposes unique values from a categorical column into individual column headers, calculating aggregate metrics at each intersection to generate matrix-style reporting views.

### 5. Output and Visualization Nodes
Output nodes consume processed data from upstream nodes and display it for consumption, presentation, or export.

- **Interactive Data Table:** Renders a clean, paginated, sortable tabular view of the current data state. Enables direct CSV and Excel file downloads of transformed results.
- **Bar Chart:** Visualizes categorical comparisons, ranking metrics across dimensions with interactive tooltips.
- **Line Chart:** Plots numerical trends over time or sequential categories, ideal for financial forecasting and trend monitoring.
- **Pie Chart:** Displays proportional share and distribution across categorical segments.

---

## Core Platform Capabilities

### Visual Canvas and Modular Logic
- **Intuitive Workflow Design:** Construct complex analytical transformations by arranging blocks on an open canvas rather than writing code or nested spreadsheet formulas.
- **Immediate Data Transparency:** Inspect intermediate tables at any node in the pipeline to verify intermediate results before proceeding to downstream steps.
- **Step-by-Step Replay:** Animate and step through the data flow to observe sequential transformations and verify logic before sharing findings.

### Quality Control and Error Isolation
- **Visual Error Tracing:** Whenever data inconsistencies, type mismatches, or unexpected values occur, affected blocks and specific rows are highlighted immediately.
- **Fail-Fast Feedback:** Catch logic errors early in the pipeline instead of discovering calculation errors in final summary cells.

### Two-Way Spreadsheet Bridge
- **Visual to Formula Translation:** Convert any visual pipeline into an equivalent, readable Excel formula for presentation or integration into legacy spreadsheets.
- **Formula to Visual Workflow:** Paste complex existing spreadsheet formulas into the platform to automatically generate an interactive, visual pipeline diagram.

### Reusable Pipeline Templates and Security
- **Reusable Analysis Models:** Save pipeline definitions as templates. When new periodic data arrives (such as monthly or quarterly reports), simply swap the input file to execute the entire analysis pipeline instantly.
- **Privacy-Conscious Architecture:** Only the workflow structure and transformation definitions are saved to personal template libraries. Proprietary row-level data is processed on demand and never retained persistently without explicit intent.

---

## Typical Use Cases

- **Recurring Management Reporting:** Standardize monthly, quarterly, and financial reconciliations. Upload updated transaction logs, and the platform automatically handles normalization, filtering, and report generation.
- **Marketing Campaign Analysis:** Ingest exports from analytics platforms, filter by channel or cohort, aggregate conversion rates, and chart performance trends in minutes.
- **Data Quality Audits:** Rapidly clean messy customer records, identifying malformed entries, missing fields, or duplicate contacts before importing into production systems.
- **Formula Audit and Documentation:** Deconstruct long legacy formulas created by colleagues into understandable, visual diagrams that team members can audit and verify collaboratively.

---

## Platform Architecture

FLUX is organized into two primary layers:

1. **User Interface Layer:** An interactive, single-page web application providing the drag-and-drop workspace, visual pipeline canvas, live data preview inspectors, dynamic charting components, and account management views.
2. **Analytical Engine and Services:** A modular service layer responsible for executing pipeline transformations, validating analytical sequences, managing user authentication, and storing custom pipeline templates.

---

## Project Structure

```
Flux/
├── Backend/
│   ├── alembic/
│   │   ├── versions/
│   │   │   └── 59c0a5b719e2_initial_schema.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── alembic.ini
│   ├── flux_dev.db
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── db.py
│       ├── data_cache.py
│       ├── rate_limit.py
│       ├── auth/
│       │   ├── backend.py
│       │   ├── dependencies.py
│       │   ├── manager.py
│       │   └── models.py
│       ├── csv_io/
│       │   ├── parser.py
│       │   └── xlsx_io.py
│       ├── dataframe/
│       │   ├── frame.py
│       │   ├── inference.py
│       │   └── schema.py
│       ├── engine/
│       │   ├── executor.py
│       │   ├── formula_engine.py
│       │   ├── registry.py
│       │   └── error_messages.py
│       ├── models/
│       │   ├── execution_log.py
│       │   └── pipeline_template.py
│       ├── nodes/
│       │   ├── base.py
│       │   ├── source/
│       │   │   ├── read_csv.py
│       │   │   └── read_xlsx.py
│       │   ├── transform/
│       │   │   ├── add_calculated_column.py
│       │   │   ├── convert_type.py
│       │   │   ├── fill_missing.py
│       │   │   ├── filter_node.py
│       │   │   ├── limit_rows.py
│       │   │   ├── remove_duplicates.py
│       │   │   ├── rename_column.py
│       │   │   ├── select_columns.py
│       │   │   └── sort_node.py
│       │   ├── aggregate/
│       │   │   ├── group_by_aggregate.py
│       │   │   └── pivot.py
│       │   ├── join/
│       │   │   └── join_node.py
│       │   └── output/
│       │       ├── _chart_base.py
│       │       ├── bar_chart.py
│       │       ├── data_table.py
│       │       ├── line_chart.py
│       │       └── pie_chart.py
│       ├── routers/
│       │   ├── data.py
│       │   ├── formula.py
│       │   ├── nodes.py
│       │   ├── pipeline.py
│       │   └── templates.py
│       └── schemas/
│           ├── data.py
│           ├── execution.py
│           ├── formula.py
│           ├── node.py
│           ├── pipeline.py
│           ├── template.py
│           └── user.py
│
├── Frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── index.css
│       ├── onboardingPipeline.js
│       ├── api/
│       │   └── executionApi.js
│       ├── store/
│       │   └── pipelineStore.js
│       ├── hooks/
│       │   ├── useAuth.js
│       │   └── useTemplates.js
│       ├── components/
│       │   ├── canvas/
│       │   │   ├── ReactFlowCanvas.jsx
│       │   │   ├── CanvasToolbar.jsx
│       │   │   └── CanvasMiniMap.jsx
│       │   ├── nodes/
│       │   │   └── FluxNode.jsx
│       │   ├── config/
│       │   │   ├── ConfigPanel.jsx
│       │   │   ├── FieldRenderer.jsx
│       │   │   └── fields/
│       │   ├── preview/
│       │   │   ├── DataPreviewTable.jsx
│       │   │   ├── ChartPreview.jsx
│       │   │   └── PreviewResizeHandle.jsx
│       │   ├── formula/
│       │   │   └── FormulaPanel.jsx
│       │   ├── sidebar/
│       │   │   └── NodeSidebar.jsx
│       │   ├── topbar/
│       │   │   └── TopBar.jsx
│       │   ├── replay/
│       │   │   └── ReplayControls.jsx
│       │   ├── templates/
│       │   │   └── TemplateBrowser.jsx
│       │   └── auth/
│       │       └── AuthModal.jsx
│       └── utils/
│           ├── chartData.js
│           └── edgePorts.js
│
├── Docs/
│   ├── Progress.md
│   └── init.md
└── README.md
```

---

## Getting Started

### Prerequisites

Ensure you have the following installed on your machine:
- Python 3.11 or newer
- Node.js 18 or newer
- npm package manager
- **PostgreSQL 15+** (optional, recommended for production / full JSONB support; SQLite can be used for quick local development)

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/mhsamir25/Flux.git
cd Flux
```

The project is organized into two primary directories:
- `Backend`: The execution engine, authentication service, and template management API.
- `Frontend`: The interactive web application and canvas interface.

---

### Step 2: Configure and Start the Backend

1. Navigate to the backend directory and set up a Python virtual environment:
   ```bash
   cd Backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Configure your environment settings:
   Create a `.env` file in the `Backend` directory:

   #### Option A: PostgreSQL (Recommended)
   1. Ensure PostgreSQL is installed and running.
   2. Create a database for the project (e.g. `flux`):
      ```bash
      # In your terminal:
      createdb flux

      # Or from within the psql prompt:
      # CREATE DATABASE flux;
      ```
   3. Add your connection string to `Backend/.env` using the `postgresql+asyncpg` driver:
      ```env
      FLUX_DATABASE_URL=postgresql+asyncpg://<username>:<password>@<host>:<port>/<database_name>
      ```
      *Example:*
      ```env
      FLUX_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flux
      ```
      *(If your local PostgreSQL role does not require a password, you can omit `:<password>`, e.g., `postgresql+asyncpg://<username>@localhost:5432/flux`)*

   #### Option B: SQLite (Quickest Local Setup)
   If you do not have PostgreSQL installed and want to run locally with zero database setup:
   ```env
   FLUX_DATABASE_URL=sqlite+aiosqlite:///./flux_dev.db
   ```

3. Initialize the database schema:
   Run Alembic migrations to apply all tables, indexes, and constraints:
   ```bash
   alembic upgrade head
   ```
   *(Alembic automatically provisions native PostgreSQL `UUID` and `JSONB` columns when connected to Postgres, or compatible fallback types when connected to SQLite.)*

4. Start the backend service:
   ```bash
   uvicorn app.main:app --reload
   ```
   The backend service will be available at `http://localhost:8000`.

---

### Step 3: Start the Frontend

In a separate terminal window:

1. Navigate to the frontend directory:
   ```bash
   cd Frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Launch the local development server:
   ```bash
   npm run dev
   ```
   Open your browser and navigate to `http://localhost:5173`.

---

### Step 4: Verification and Testing

To verify backend pipeline operations and transformation nodes:
```bash
cd Backend
source .venv/bin/activate
pytest
```

---

## Operational Notes

- **Default Port Configuration:** The frontend connects to the backend at `http://localhost:8000` by default. If your backend operates on a different host or port, configure `VITE_API_BASE_URL` in a `Frontend/.env` file.
- **Virtual Environment Best Practice:** Always activate the virtual environment (`source .venv/bin/activate`) before running database management or server commands to ensure dependency isolation.
