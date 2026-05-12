<div align="center">

<img src="https://img.shields.io/badge/FLUX-Visual%20Data%20Pipelines-7C3AED?style=for-the-badge&logo=databricks&logoColor=white" alt="Flux Banner">

**A Visual Data Pipeline Builder**

*Build analysis like building blocks. No formulas, no code, no tears.*

[Features](#-key-features) •
[Architecture](#️-architecture) •
[Tech Stack](#-tech-stack) •
[Getting Started](#-getting-started) •
[Project Structure](#-project-structure) •
[Team](#-team)

</div>

---

## 📖 Overview

**FLUX** is a browser‑based, no‑code tool that transforms how people work with spreadsheet data.

Instead of memorising Excel formulas, you simply **drag blocks onto a canvas and connect them** – like drawing a flowchart. Upload a CSV, drop a Filter block, connect it to a Group By, then to a Chart, and **watch your results appear live at every single step.**

FLUX doesn’t just replace formulas – it **bridges the gap** between visual logic and Excel.  
- Build a pipeline → get the equivalent Excel formula instantly.  
- Paste an Excel formula → FLUX draws the visual pipeline for you.

> 🎯 **Built for SWE 4404 – Software Project Lab II**, 4th Semester, B.Sc. in Software Engineering.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🧩 **Drag‑and‑Drop Canvas** | Build data workflows visually – no code, no formula syntax |
| 👁️ **Live Previews at Every Step** | See exactly how your data transforms after each block |
| ♻️ **Reusable Pipeline Templates** | Save a pipeline once, swap the source file, rerun instantly |
| 🔄 **Two‑Way Excel Bridge** | Pipeline → Excel formula; Excel formula → visual pipeline |
| 🔍 **Visual Error Tracing** | Faulty blocks glow red, affected rows are flagged immediately |
| ▶️ **Step‑by‑Step Replay** | Animate data flow block‑by‑block to pinpoint errors |
| 🧹 **Data Cleaning Blocks** | Fill missing values, remove duplicates, split columns – no manual Excel cleanup |
| 📊 **Live Charts** | Pipe your data into bar, line, or pie charts instantly |
| 📁 **Cross‑Format Support** | Input and output `.csv` and `.xlsx` files |
| 🔐 **Secure Cloud Templates** | Save pipeline templates to your personal library (no CSV data stored) |

---

## 🧠 The Problems We Solve

1. **Formula Hell** – Excel’s learning curve is steep; intermediate users get stuck after `SUM` and `AVERAGE`.  
2. **Fragile Logic** – Changing a column breaks formulas everywhere (`#REF!`). Logic is baked into cells.  
3. **Hidden Errors** – Excel only shows `#N/A` or `#DIV/0!` at the end. Tracing the source is painful.  
4. **Opaque Spreadsheets** – Inheriting a colleague’s monster formula is like reading uncommented code.  
5. **No Reusability** – Rebuilding the same monthly report from scratch wastes hours.

**FLUX makes data analysis transparent, modular, and approachable.**

---


---

## Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | React.js, Vite, Tailwind CSS, React Flow, Zustand, Recharts | Canvas UI, state management, charts |
| **Execution Backend** | FastAPI (Python), Pydantic | Stateless pipeline execution engine |
| **Persistence Backend** | Django, Django REST Framework, Simple JWT | Authentication & template storage |
| **Database** | PostgreSQL | User accounts, saved templates |
| **CSV Parsing** | PapaParse (frontend), Python `csv` (backend) | CSV file handling |
| **Excel Export** | ExcelJS, OpenPyXL | `.xlsx` generation |
| **Version Control** | Git, GitHub | Collaboration & source control |
| **Documentation** | Google Docs | Collaborative editing |


- **FastAPI** handles all data processing – it receives a pipeline definition + CSV, executes the DAG, and returns results. No data is stored here.  
- **Django + PostgreSQL** manages user accounts, authentication, and persistent storage of pipeline templates (structure only, never CSV data).

---

##  Getting Started

### Prerequisites
- **Python**
- **Node.js** 
- **PostgreSQL** 
- **npm** or **yarn**

### 1. Clone the Repository
```bash
git clone https://github.com/mhsamir25/Flux.git
cd Flux