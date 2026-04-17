# 🛡️ Enterprise Risk Management Dashboard

A unified, interactive risk management dashboard built with **FastAPI** (backend) and **HTML/CSS/JavaScript** (frontend), reading live data from the Excel workbook.

---

## 📋 Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | **3.9 or higher** |
| pip | Latest recommended |

---

## 🗂️ Project File Structure

```
risk_dashboard/
├── main.py                                           ← FastAPI backend (API + static file server)
├── Enterprise_Risk_Dashboard_Formula_Driven.xlsx     ← Data source (must be present!)
├── requirements.txt                                  ← Python dependencies
├── README.md                                         ← This file
└── static/
    └── index.html                                    ← Full dashboard UI (HTML/CSS/JS)
```

---

## 🚀 Setup & Run

### Step 1 — Install Python (if needed)

Download from https://www.python.org/downloads/

---

### Step 2 — Open Terminal in the Project Folder

**Windows:** Open File Explorer → navigate to `risk_dashboard/` → click address bar → type `cmd` → Enter

**macOS / Linux:**
```bash
cd /path/to/risk_dashboard
```

---

### Step 3 — (Recommended) Create a Virtual Environment

```bash
python -m venv venv

# Activate:
# Windows:  venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
```

---

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 5 — Run the Dashboard

```bash
python main.py
```

Then open **http://localhost:8000** in your browser.

---

## 📊 Dashboard Sections

| Section | Description |
|---------|-------------|
| ⬡ Overview | Enterprise-wide RAG heatmap, KRI summary, breach alerts |
| 💳 Credit Risk | NPA, ECL, segment distribution, high-risk accounts |
| 📊 Market Risk | VaR by desk, asset class exposure |
| ⚙️ Operational Risk | Loss events, BU breakdown, incident status |
| 🏛️ Capital Adequacy | CRAR/CET-1 trend, RWA composition |
| 💧 Liquidity Risk | LCR, NSFR, stress scenario analysis |
| ↕️ IRRBB | NII/EVE sensitivity, rate shock scenarios |
| 🔗 Concentration | Sector/borrower concentration, HHI index |
| 🌿 Climate Risk | Physical/transition risk, TCFD categories |
| 🔒 Cyber Risk | Severity, CVSS, MTTD/MTTR, attack vectors |
| 🕵️ Fraud Risk | Channel fraud, type distribution, recovery rate |
| 🤝 Third Party | Vendor criticality, SLA breach, risk scores |
| 📣 Reputational | Sentiment score, complaints, resolution rate |
| 🎯 Strategic | BSC scorecard, KPI variance |
| 📰 Pillar 3 | CRAR by entity, disclosure timeliness |
| 📈 KRI Trends | 12-month formula-driven KRI trend lines + full table |

---

## 🔌 REST API Endpoints

Full interactive docs at: **http://localhost:8000/docs**

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Health check |
| `GET /api/reload` | Force reload Excel data |
| `GET /api/kri/summary` | KRI master list |
| `GET /api/kri/rag-counts` | Green/Amber/Red counts |
| `GET /api/kri/trend` | Monthly KRI trend data |
| `GET /api/pillar1/credit-summary` | Credit risk aggregates |
| `GET /api/pillar1/market-summary` | Market risk aggregates |
| `GET /api/pillar1/capital-adequacy` | Capital adequacy quarterly |
| `GET /api/pillar2/liquidity-summary` | Liquidity metrics |
| `GET /api/pillar2/climate-summary` | Climate risk aggregates |
| `GET /api/pillar2/cyber-summary` | Cyber risk aggregates |
| `GET /api/pillar2/fraud-summary` | Fraud risk aggregates |

---

## 🔄 Data Refresh

Click **↺ Refresh Data** in the sidebar to reload data from the Excel file.

---

## ❗ Troubleshooting

### `FileNotFoundError`
Ensure `Enterprise_Risk_Dashboard_Formula_Driven.xlsx` is in the **same folder** as `main.py`.

### `Port 8000 already in use`
Edit `main.py` last line: change `port=8000` to another port like `8001`.

### `ModuleNotFoundError`
Run `pip install -r requirements.txt` with your virtual environment activated.

---

## 📞 Reference

- **Project:** Enterprise Level Unified Risk Management Dashboard
- 
