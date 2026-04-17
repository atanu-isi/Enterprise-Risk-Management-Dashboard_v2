"""
Enterprise Risk Management Dashboard — Protiviti
FastAPI Backend + Static HTML Frontend
Version 4.0.0  — Midnight dark theme · High-contrast charts · Interactive KRI live ticker
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from typing import Optional
import pandas as pd
import numpy as np
import os, uvicorn

# ── Injected CSS + JS for live KRI ticker (midnight dark theme) ───────────────
_INJECT_STYLE = r"""
<style id="live-kri-theme">
/* ═══════════════════════════════════════════════════
   LIVE KRI TICKER BAR — midnight dark style
   ═══════════════════════════════════════════════════ */
#live-kri-ticker-bar {
  position: fixed !important; top: 0 !important; left: 0 !important; right: 0 !important;
  height: 32px !important;
  background: linear-gradient(90deg, #050a14 0%, #0a1530 60%, #0f1e40 100%) !important;
  z-index: 999999 !important; display: flex !important; align-items: center !important;
  overflow: hidden !important;
  box-shadow: 0 1px 0 rgba(77,159,255,0.2), 0 2px 16px rgba(0,0,0,.6) !important;
  border: none !important;
  border-bottom: 1px solid rgba(77,159,255,0.18) !important;
}
body { padding-top: 32px !important; }

#live-kri-ticker-bar .ticker-label {
  flex-shrink: 0 !important; padding: 0 14px !important; height: 100% !important;
  background: linear-gradient(90deg,#1a3a7a,#0f2555) !important;
  display: flex !important; align-items: center !important;
  gap: 7px !important; font-size: 9px !important; font-weight: 800 !important;
  letter-spacing: 2.2px !important; text-transform: uppercase !important;
  color: #93c5fd !important; white-space: nowrap !important;
  border-right: 1px solid rgba(77,159,255,0.25) !important;
}
.ticker-live-dot {
  width: 6px !important; height: 6px !important;
  background: #22d67a !important;
  border-radius: 50% !important; flex-shrink: 0 !important;
  box-shadow: 0 0 6px #22d67a !important;
  animation: tld 1.4s ease-in-out infinite !important;
}
@keyframes tld { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(.7)} }
#live-kri-ticker-bar .ticker-track { flex: 1 !important; overflow: hidden !important; }
#live-kri-ticker-bar .ticker-inner { display: flex !important; align-items: center !important; will-change: transform; }
.ticker-item { display: inline-flex !important; align-items: center !important; gap: 5px !important; padding: 0 16px !important; white-space: nowrap !important; border-right: 1px solid rgba(77,159,255,0.1) !important; }
.ticker-item .t-name  { color: #6b9fd4 !important; font-size: 9.5px !important; font-weight: 600 !important; letter-spacing: .2px !important; }
.ticker-item .t-val   { color: #e8f0fe !important; font-size: 12px !important; font-weight: 800 !important; transition: color .35s !important; font-variant-numeric: tabular-nums !important; font-family: 'JetBrains Mono', monospace !important; }
.ticker-item .t-arrow { font-size: 9px !important; }
.ticker-item .t-arrow.up   { color: #22d67a !important; }
.ticker-item .t-arrow.down { color: #ff4d6a !important; }
.ticker-item .t-rag   { font-size: 8px !important; padding: 2px 5px !important; border-radius: 3px !important; font-weight: 800 !important; letter-spacing: .5px !important; }
.ticker-item .t-rag.G { background: rgba(34,214,122,0.2) !important; color: #22d67a !important; border: 1px solid rgba(34,214,122,0.35) !important; }
.ticker-item .t-rag.A { background: rgba(255,184,48,0.2) !important; color: #ffb830 !important; border: 1px solid rgba(255,184,48,0.35) !important; }
.ticker-item .t-rag.R { background: rgba(255,77,106,0.2) !important; color: #ff4d6a !important; border: 1px solid rgba(255,77,106,0.35) !important; }


</style>
"""

_INJECT_SCRIPT = """
<script id="live-kri-animation">
(function () {
  "use strict";

  /* ── helpers ── */
  function stripFmt(s){ return String(s).replace(/[%, ]/g,"").replace(/[₹]/g,""); }
  function isNum(s){
    if(!s || s==="--" || s==="-" || s==="\u2014") return false;
    var v=parseFloat(stripFmt(s));
    return !isNaN(v) && isFinite(v) && String(s).trim().length < 20;
  }
  function toNum(s){ return parseFloat(stripFmt(s)); }
  function fmtLike(orig,val){
    var s=String(orig);
    if(s.indexOf("%")>-1)  return val.toFixed(2)+"%";
    if(s.indexOf("₹")>-1) return "₹"+val.toFixed(2);
    var dp=(s.split(".")[1]||"").length;
    return dp===0 ? String(Math.round(val)) : val.toFixed(Math.min(dp,4));
  }

  /* ── patch Chart.js defaults for dark theme ── */
  function patchCharts(){
    if(window.Chart && window.Chart.defaults){
      var d=window.Chart.defaults;
      d.color = '#c8daf5';
      if(d.plugins && d.plugins.legend && d.plugins.legend.labels){
        d.plugins.legend.labels.color = '#c8daf5';
      }
      if(d.scale){
        if(d.scale.ticks) d.scale.ticks.color = '#8aaace';
        if(d.scale.grid)  d.scale.grid.color  = 'rgba(100,150,220,0.08)';
      }
    }
  }

  /* ── TICKER ── */
  var _items=[], _offset=0, _speed=0.5;

  function escH(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;"); }

  function buildTicker(kris){
    var inner=document.getElementById("live-kri-ticker-inner");
    if(!inner) return;
    inner.innerHTML="";
    kris.concat(kris).forEach(function(k){
      var sp=document.createElement("span");
      sp.className="ticker-item";
      var rag=String(k.rag||"G").trim()[0];
      sp.innerHTML=
        '<span class="t-name">'+escH(k.name)+'</span>'+
        '<span class="t-val" data-tikr="'+k.idx+'">'+escH(k.disp)+'</span>'+
        '<span class="t-arrow '+(k.trend==="Up"?"up":"down")+'">'+(k.trend==="Up"?"&#9650;":"&#9660;")+'</span>'+
        '<span class="t-rag '+rag+'">'+escH(rag)+'</span>';
      inner.appendChild(sp);
    });
    _items=kris;
  }

  function scrollTicker(){
    var inner=document.getElementById("live-kri-ticker-inner");
    if(!inner){ requestAnimationFrame(scrollTicker); return; }
    var half=inner.scrollWidth/2;
    _offset+=_speed;
    if(_offset>=half) _offset=0;
    inner.style.transform="translateX(-"+_offset+"px)";
    requestAnimationFrame(scrollTicker);
  }

  function tickerUpdate(){
    /* values are static — no simulation, no blinking */
  }

  function injectBar(){
    if(document.getElementById("live-kri-ticker-bar")) return;
    var bar=document.createElement("div");
    bar.id="live-kri-ticker-bar";
    bar.innerHTML='<div class="ticker-label"><span class="ticker-live-dot"></span>LIVE KRI</div>'
      +'<div class="ticker-track"><div class="ticker-inner" id="live-kri-ticker-inner"></div></div>';
    document.body.insertBefore(bar,document.body.firstChild);
  }

  function loadTicker(){
    fetch("/api/kri/summary")
      .then(function(r){ return r.json(); })
      .then(function(data){
        var kris=(data.data||[]).filter(function(k){
          return isNum(k["Current_Value_Display"]||"");
        }).map(function(k,i){
          var d=String(k["Current_Value_Display"]||"");
          return {idx:i,name:String(k["KRI Name"]||"KRI").slice(0,26),
            disp:d,origDisp:d,raw:toNum(d),_cur:toNum(d),
            _dir:(Math.random()>.5?1:-1),
            rag:String(k["RAG Status"]||k["RAG"]||"G"),
            trend:String(k["Trend"]||"")};
        });
        if(!kris.length) return;
        injectBar();
        buildTicker(kris);
        requestAnimationFrame(scrollTicker);
        setTimeout(tickerUpdate,2000);
      }).catch(function(){});
  }

  /* ── boot ── */
  function init(){
    patchCharts();
    loadTicker();
  }

  if(document.readyState==="loading")
    document.addEventListener("DOMContentLoaded",init);
  else
    setTimeout(init,150);
})();
</script>
"""

# ── HTML injection middleware ─────────────────────────────────────────────────
class InjectThemeMiddleware(BaseHTTPMiddleware):
    """Injects the live-KRI animation + light-theme CSS/JS into every HTML response."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        ct = response.headers.get("content-type", "")
        if "text/html" not in ct:
            return response
        # Read body
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk
        html = body_bytes.decode("utf-8", errors="replace")
        # Inject before </head> (style) and before </body> (script)
        if "</head>" in html:
            html = html.replace("</head>", _INJECT_STYLE + "</head>", 1)
        else:
            html = _INJECT_STYLE + html
        if "</body>" in html:
            html = html.replace("</body>", _INJECT_SCRIPT + "</body>", 1)
        else:
            html = html + _INJECT_SCRIPT
        # Build clean headers — drop Content-Length so Starlette recalculates
        # it correctly for the now-larger body; also drop Content-Encoding
        # because we've already decoded the body above.
        skip = {"content-length", "content-encoding", "transfer-encoding"}
        clean_headers = {
            k: v for k, v in response.headers.items()
            if k.lower() not in skip
        }
        return HTMLResponse(
            content=html,
            status_code=response.status_code,
            headers=clean_headers,
        )

EXCEL_FILE = os.path.join(os.path.dirname(__file__), "Enterprise_Risk_Dashboard_Formula_Driven.xlsx")

_cache: dict = {}

# ── Unit classification helpers ───────────────────────────────────────────────

# Units that are percentage-type → display as "XX.XX%"
PCT_UNITS = {
    "percent", "%", "percent of limit", "percent of nii", "% of nii",
    "percent of tier-1", "percent nii impact", "percent on-time",
    "percent of advances",
}

# Units that should display as plain rounded number (2dp)
NUMERIC_UNITS = {
    "score (1-5)", "score (1-10)", "score 0-100", "score", "cvss 0-10",
    "hhi index", "years",
}

# Units that should display as integer
INT_UNITS = {
    "count", "count/qtr", "gb",
}


def _classify_unit(unit: str) -> str:
    """Return 'pct' | 'int' | 'num' | 'currency' | 'other'."""
    u = (unit or "").strip().lower()
    if u in PCT_UNITS:
        return "pct"
    if u in INT_UNITS:
        return "int"
    if u in NUMERIC_UNITS:
        return "num"
    if "₹" in u or "tco2" in u.lower():
        return "currency"
    return "other"


def _fmt_value(val, unit: str) -> str:
    """
    Format a KRI current value for display:
      - percent-type units  → "57.78%"
      - integer-type units  → "128"
      - numeric/score/years → "57.78"
      - currency/other      → "1720.00"
      - text                → as-is
    """
    if val is None:
        return "—"
    if isinstance(val, str):
        return val.strip() if val.strip() else "—"

    kind = _classify_unit(unit)
    try:
        fval = float(val)
    except (TypeError, ValueError):
        return str(val)

    if kind == "pct":
        return f"{fval:.2f}%"
    if kind == "int":
        return str(int(round(fval)))
    if kind == "num":
        return f"{fval:.2f}"
    # currency / other
    return f"{fval:.2f}"


def _enrich_kri_records(records: list) -> list:
    """Add Current_Value_Display and Unit_Kind to every KRI record."""
    for rec in records:
        unit = str(rec.get("Unit", "") or "")
        raw = rec.get("Current Value")
        rec["Current_Value_Display"] = _fmt_value(raw, unit)
        rec["Unit_Kind"] = _classify_unit(unit)
        # Round raw numeric to 6dp for JSON cleanliness
        if raw is not None and not isinstance(raw, str):
            try:
                rec["Current Value"] = round(float(raw), 6)
            except Exception:
                pass
    return records


def _load() -> dict:
    global _cache
    if _cache:
        return _cache
    xl = pd.ExcelFile(EXCEL_FILE)
    for sheet in xl.sheet_names:
        try:
            if sheet == "Monthly_KRI_Trend":
                df = pd.read_excel(xl, sheet_name=sheet, header=2)
            elif sheet in {"P3_Capital_Disclosure"}:
                df = pd.read_excel(xl, sheet_name=sheet, header=2)
            else:
                df = pd.read_excel(xl, sheet_name=sheet, header=1)
            df.columns = [str(c).strip().replace('\n', ' ') for c in df.columns]
            df = df.dropna(how="all")
            _cache[sheet] = df
        except Exception:
            _cache[sheet] = pd.DataFrame()
    return _cache


def _j(df: pd.DataFrame) -> list:
    return df.replace({np.nan: None}).to_dict(orient="records")


def _safe(df, col):
    return df[col] if col in df.columns else pd.Series(dtype=str)


def _fmt_pct(val):
    try:
        return round(float(val), 2)
    except Exception:
        return val


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load()
    yield


app = FastAPI(
    title="Protiviti — Enterprise Risk Dashboard API",
    description="Unified Enterprise Risk Management Dashboard",
    version="3.1.0",
    lifespan=lifespan
)
# CORS must be added before the injection middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# Inject live-KRI animation + light background into every HTML page
app.add_middleware(InjectThemeMiddleware)

# ── System ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "company": "Protiviti", "sheets": list(_load().keys())}


@app.get("/api/reload")
def reload():
    global _cache
    _cache = {}
    _load()
    return {"status": "reloaded", "sheets": list(_cache.keys())}


@app.get("/api/kri/live-config")
def live_config():
    """
    Returns animation configuration for the Live KRI ticker.
    stepMs  — milliseconds between value ticks (slow drift).
    spreadPct — maximum ± drift as a fraction of the current value.
    """
    return {
        "animation": "enabled",
        "stepMs": 3000,
        "spreadPct": 0.005,
        "pulseDurationS": 3,
        "theme": "light"
    }


# ── KRI ───────────────────────────────────────────────────────────────────────
@app.get("/api/kri/summary")
def kri_summary(risk_category: Optional[str] = None, rag_status: Optional[str] = None):
    df = _load().get("KRI_Master_Summary", pd.DataFrame())
    if df.empty:
        raise HTTPException(404, "Sheet not found")
    if risk_category:
        df = df[df["Risk Category"].astype(str).str.contains(risk_category, case=False, na=False)]
    if rag_status:
        df = df[df["RAG Status"].astype(str).str.lower() == rag_status.lower()]
    records = _enrich_kri_records(_j(df))
    return {"count": len(records), "data": records}


@app.get("/api/kri/rag-counts")
def rag_counts():
    df = _load().get("KRI_Master_Summary", pd.DataFrame())
    if df.empty or "RAG Status" not in df.columns:
        return {"Green": 0, "Amber": 0, "Red": 0, "total": 0}
    c = df["RAG Status"].value_counts().to_dict()
    return {
        "Green": int(c.get("Green", 0)),
        "Amber": int(c.get("Amber", 0)),
        "Red":   int(c.get("Red", 0)),
        "total": int(len(df))
    }


@app.get("/api/kri/overview-full")
def kri_overview_full():
    """
    Return all KRI records from KRI_Master_Summary with:
    - Current_Value_Display: properly formatted string (XX.XX% for pct, int for counts, etc.)
    - Unit_Kind: classification of unit type
    - by_category: RAG counts per risk category
    Only KRI_Master_Summary values are used here — no other sheets.
    """
    df = _load().get("KRI_Master_Summary", pd.DataFrame())
    if df.empty:
        raise HTTPException(404, "KRI_Master_Summary sheet not found")

    records = _enrich_kri_records(_j(df))

    categories: dict = {}
    for rec in records:
        cat = str(rec.get("Risk Category", "Other"))
        categories.setdefault(cat, []).append(rec)

    rag_counts_by_cat: dict = {}
    for cat, recs in categories.items():
        rag_counts_by_cat[cat] = {
            "Green": sum(1 for r in recs if str(r.get("RAG Status", "")).lower() == "green"),
            "Amber": sum(1 for r in recs if str(r.get("RAG Status", "")).lower() == "amber"),
            "Red":   sum(1 for r in recs if str(r.get("RAG Status", "")).lower() == "red"),
            "total": len(recs)
        }

    return {
        "total": len(records),
        "rag_summary": {
            "Green": sum(1 for r in records if str(r.get("RAG Status", "")).lower() == "green"),
            "Amber": sum(1 for r in records if str(r.get("RAG Status", "")).lower() == "amber"),
            "Red":   sum(1 for r in records if str(r.get("RAG Status", "")).lower() == "red"),
        },
        "by_category": rag_counts_by_cat,
        "data": records
    }


@app.get("/api/kri/trend")
def kri_trend(kri_name: Optional[str] = None):
    df = _load().get("Monthly_KRI_Trend", pd.DataFrame())
    if df.empty:
        raise HTTPException(404, "Monthly_KRI_Trend sheet not found")
    if "KRI Name" in df.columns:
        df = df.dropna(subset=["KRI Name"])
        df = df[df["KRI Name"].astype(str).str.strip() != ""]
    if kri_name:
        df = df[df["KRI Name"].astype(str).str.contains(kri_name, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/kri/trend-series")
def kri_trend_series():
    """
    Returns KRI trend data in chart-ready format.
    Values for each month use Current_Value_Display formatting from _fmt_value.
    Units are cross-referenced from KRI_Master_Summary for consistency.
    """
    df = _load().get("Monthly_KRI_Trend", pd.DataFrame())
    if df.empty:
        raise HTTPException(404, "Monthly_KRI_Trend sheet not found")
    if "KRI Name" in df.columns:
        df = df.dropna(subset=["KRI Name"])
        df = df[df["KRI Name"].astype(str).str.strip() != ""]

    # Cross-reference units from KRI_Master_Summary
    kri_units: dict = {}
    kri_master = _load().get("KRI_Master_Summary", pd.DataFrame())
    if not kri_master.empty and "KRI Name" in kri_master.columns and "Unit" in kri_master.columns:
        for _, row in kri_master.iterrows():
            kri_units[str(row["KRI Name"]).strip()] = str(row.get("Unit", "") or "")

    month_cols = ["May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25",
                  "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26", "Mar-26", "Apr-26"]
    available_months = [m for m in month_cols if m in df.columns]

    series = []
    for _, row in df.iterrows():
        kri_name = str(row["KRI Name"]).strip()
        unit = kri_units.get(kri_name, str(row.get("Unit", "") or "")).strip()
        direction = str(row.get("Direction", "")).strip()
        kind = _classify_unit(unit)
        is_pct = (kind == "pct")

        red_thresh   = row.get("Red Thresh")   if "Red Thresh"   in df.columns else None
        amber_thresh = row.get("Amber Thresh") if "Amber Thresh" in df.columns else None

        monthly_vals = []
        for m in available_months:
            v = row.get(m)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                try:
                    fv = round(float(v), 6)
                    monthly_vals.append({
                        "value":   fv,
                        "display": _fmt_value(fv, unit)
                    })
                except Exception:
                    monthly_vals.append(None)
            else:
                monthly_vals.append(None)

        def _safe_float(col_name):
            val = row.get(col_name)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                return None
            try:
                return round(float(val), 6)
            except Exception:
                return None

        current_raw = _safe_float("Apr-26 (Current)")

        series.append({
            "id":              int(row["#"]) if "#" in df.columns and row.get("#") is not None else None,
            "kri_name":        kri_name,
            "unit":            unit,
            "unit_kind":       kind,
            "is_percent":      is_pct,
            "direction":       direction,
            "red_threshold":   round(float(red_thresh),   6) if red_thresh   is not None and not (isinstance(red_thresh,   float) and np.isnan(red_thresh))   else None,
            "amber_threshold": round(float(amber_thresh), 6) if amber_thresh is not None and not (isinstance(amber_thresh, float) and np.isnan(amber_thresh)) else None,
            "months":          available_months,
            "values":          monthly_vals,
            "current":         current_raw,
            "current_display": _fmt_value(current_raw, unit),
            "avg_12m":         _safe_float("12M Avg"),
            "avg_3m":          _safe_float("3M Avg"),
            "trend":           str(row.get("Trend", "")).strip() if "Trend" in df.columns else "",
            "mom_change":      _safe_float("MoM Change"),
        })

    return {"count": len(series), "months": available_months, "series": series}


@app.get("/api/kri/thresholds")
def kri_thresholds():
    df = _load().get("KRI_Thresholds", pd.DataFrame())
    return {"count": len(df), "data": _j(df)}


# ── Pillar 1 ──────────────────────────────────────────────────────────────────
@app.get("/api/pillar1/credit-risk")
def credit_risk(segment: Optional[str] = None, rag: Optional[str] = None, npa_category: Optional[str] = None):
    df = _load().get("P1_Credit_Risk", pd.DataFrame())
    if segment:
        df = df[df["Segment"].astype(str).str.contains(segment, case=False, na=False)]
    if rag:
        df = df[df["RAG"].astype(str).str.lower() == rag.lower()]
    if npa_category:
        df = df[df["NPA_Category"].astype(str).str.contains(npa_category, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar1/credit-summary")
def credit_summary():
    df = _load().get("P1_Credit_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "NPA_Category" in df.columns:
        r["npa_dist"] = df["NPA_Category"].value_counts().to_dict()
    if "Segment" in df.columns:
        r["segment_dist"] = df["Segment"].value_counts().to_dict()
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "Outstanding_Cr" in df.columns:
        r["total_outstanding"] = round(float(df["Outstanding_Cr"].sum()), 2)
        r["npa_outstanding"] = round(float(df[df["NPA_Category"] != "Standard"]["Outstanding_Cr"].sum()), 2) if "NPA_Category" in df.columns else 0
    if "ECL_Cr" in df.columns:
        r["total_ecl"] = round(float(df["ECL_Cr"].sum()), 2)
    if "Sector" in df.columns and "Outstanding_Cr" in df.columns:
        r["sector_exposure"] = df.groupby("Sector")["Outstanding_Cr"].sum().sort_values(ascending=False).head(10).round(2).to_dict()
    if "Outstanding_Cr" in df.columns and r.get("total_outstanding", 0) > 0:
        r["npa_ratio_pct"] = round(r.get("npa_outstanding", 0) / r["total_outstanding"] * 100, 2)
    return r


@app.get("/api/pillar1/market-risk")
def market_risk(desk: Optional[str] = None):
    df = _load().get("P1_Market_Risk", pd.DataFrame())
    if desk:
        df = df[df["Desk"].astype(str).str.contains(desk, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar1/market-summary")
def market_summary():
    df = _load().get("P1_Market_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "VaR_1D_Cr" in df.columns:
        r["total_var"] = round(float(df["VaR_1D_Cr"].sum()), 2)
    if "SVaR_Cr" in df.columns:
        r["total_svar"] = round(float(df["SVaR_Cr"].sum()), 2)
    if "IRC_Cr" in df.columns:
        r["total_irc"] = round(float(df["IRC_Cr"].sum()), 2)
        r["irc"] = r["total_irc"]  # alias for frontend
    if "MTM_Cr" in df.columns:
        r["total_mtm"] = round(float(df["MTM_Cr"].sum()), 2)
    if "Desk" in df.columns:
        r["desk_count"] = int(df["Desk"].nunique())
        if "VaR_1D_Cr" in df.columns:
            desk_var = df.groupby("Desk")["VaR_1D_Cr"].sum().round(2).to_dict()
            r["desk_var"] = desk_var
            r["var_by_desk"] = desk_var  # alias for frontend
    if "Asset_Class" in df.columns and "Face_Value_Cr" in df.columns:
        r["asset_class_exposure"] = df.groupby("Asset_Class")["Face_Value_Cr"].sum().round(2).to_dict()
    return r


@app.get("/api/pillar1/operational-risk")
def operational_risk(business_unit: Optional[str] = None, rag: Optional[str] = None):
    df = _load().get("P1_Operational_Risk", pd.DataFrame())
    if business_unit:
        df = df[df["Business_Unit"].astype(str).str.contains(business_unit, case=False, na=False)]
    if rag:
        df = df[df["RAG"].astype(str).str.lower() == rag.lower()]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar1/operational-summary")
def op_summary():
    df = _load().get("P1_Operational_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Gross_Loss_Lakhs" in df.columns:
        r["total_gross_loss"] = round(float(df["Gross_Loss_Lakhs"].sum()), 2)
        r["total_loss"] = r["total_gross_loss"]  # alias
    if "Net_Loss_Lakhs" in df.columns:
        r["total_net_loss"] = round(float(df["Net_Loss_Lakhs"].sum()), 2)
    if "Risk_Category" in df.columns and "Net_Loss_Lakhs" in df.columns:
        r["loss_by_category"] = df.groupby("Risk_Category")["Net_Loss_Lakhs"].sum().round(2).to_dict()
    if "Business_Unit" in df.columns and "Gross_Loss_Lakhs" in df.columns:
        bu_loss = df.groupby("Business_Unit")["Gross_Loss_Lakhs"].sum().round(2).to_dict()
        r["loss_by_bu"] = bu_loss
        r["bu_loss"] = bu_loss  # alias for frontend
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "Status" in df.columns:
        status = df["Status"].value_counts().to_dict()
        r["status"] = status
        r["status_dist"] = status  # alias for frontend
    r["total_incidents"] = len(df)
    # Near miss count
    for nm_col in ["Near_Miss", "Near_Miss_Flag", "Type"]:
        if nm_col in df.columns:
            nm_mask = df[nm_col].astype(str).str.lower().str.contains("near", na=False)
            r["near_misses"] = int(nm_mask.sum())
            break
    if "Gross_Loss_Lakhs" in df.columns and "Net_Loss_Lakhs" in df.columns:
        gross = float(df["Gross_Loss_Lakhs"].sum())
        net   = float(df["Net_Loss_Lakhs"].sum())
        if gross > 0:
            rr = round((gross - net) / gross * 100, 2)
            r["recovery_rate_pct"] = rr
            r["recovery_rate"] = f"{rr}%"  # alias for frontend
    return r


@app.get("/api/pillar1/capital-adequacy")
def capital_adequacy():
    df = _load().get("P1_Capital_Adequacy", pd.DataFrame())
    if df.empty:
        return {"count": 0, "data": [], "summary": {}}
    records = _j(df)
    pct_cols = [c for c in df.columns if "%" in c or "ratio" in c.lower() or "crar" in c.lower() or "cet" in c.lower()]
    # Build summary from latest quarter row
    latest = df.iloc[-1] if len(df) else pd.Series()
    summary = {}
    for col in ["CRAR_%", "CET1_%", "Tier1_%", "Tier2_%", "CCB_%", "D-SIB_Buffer_%",
                "Leverage_Ratio_%", "Total_RWA_Cr", "Total_Capital_Cr",
                "Capital_Buffer_Cr", "ICAAP_Headroom_Cr", "Credit_RWA_Cr",
                "Market_RWA_Cr", "Op_RWA_Cr"]:
        if col in df.columns and pd.notna(latest.get(col)):
            summary[col] = round(float(latest[col]), 2)
    return {"count": len(records), "pct_columns": pct_cols, "data": records, "summary": summary}


# ── Pillar 2 ──────────────────────────────────────────────────────────────────
@app.get("/api/pillar2/liquidity-risk")
def liquidity_risk(scenario: Optional[str] = None):
    df = _load().get("P2_Liquidity_Risk", pd.DataFrame())
    if scenario:
        df = df[df["Stress_Scenario"].astype(str).str.contains(scenario, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/liquidity-summary")
def liquidity_summary():
    df = _load().get("P2_Liquidity_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    # Avg ratios — exposed under frontend-expected keys AND legacy keys
    for col, key in [("LCR_%", "avg_lcr"), ("NSFR_%", "avg_nsfr"), ("SLR_%", "avg_slr"), ("CRR_%", "avg_crr")]:
        if col in df.columns:
            val = _fmt_pct(df[col].mean())
            r[key] = f"{val}%"
            r[col.lower().replace("%", "_pct")] = val  # legacy key
    # HQLA total
    for hqla_col in ["HQLA_Cr", "HQLA_Amount_Cr", "HQLA"]:
        if hqla_col in df.columns:
            r["total_hqla"] = round(float(df[hqla_col].sum()), 2)
            break
    # LCR by stress scenario (for bar chart)
    if "Stress_Scenario" in df.columns and "LCR_%" in df.columns:
        r["lcr_by_scenario"] = df.groupby("Stress_Scenario")["LCR_%"].mean().round(2).to_dict()
    # NSFR trend (by scenario or month if available)
    if "Stress_Scenario" in df.columns and "NSFR_%" in df.columns:
        r["nsfr_trend"] = df.groupby("Stress_Scenario")["NSFR_%"].mean().round(2).to_dict()
    # Stressed LCR (minimum across scenarios)
    if "LCR_%" in df.columns:
        r["stress_lcr"] = f"{_fmt_pct(df['LCR_%'].min())}%"
    if "Stress_Scenario" in df.columns:
        r["scenario_dist"] = df["Stress_Scenario"].value_counts().to_dict()
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    return r


@app.get("/api/pillar2/irrbb")
def irrbb(scenario: Optional[str] = None):
    df = _load().get("P2_IRRBB", pd.DataFrame())
    if scenario:
        df = df[df["Scenario"].astype(str).str.contains(scenario, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/irrbb-summary")
def irrbb_summary():
    df = _load().get("P2_IRRBB", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    # Average sensitivities under frontend-expected keys
    if "NII_Impact_%" in df.columns:
        r["avg_nii_sensitivity"] = round(float(df["NII_Impact_%"].mean()), 2)
        r["max_nii_impact"] = round(float(df["NII_Impact_%"].abs().max()), 2)
        r["nii_impact_%"] = _fmt_pct(df["NII_Impact_%"].mean())  # legacy
    # Check for NII in Cr column too
    for nii_col in ["NII_Impact_Cr", "NII_Cr", "NII_Impact"]:
        if nii_col in df.columns:
            r["avg_nii_sensitivity"] = round(float(df[nii_col].mean()), 2)
            r["max_nii_impact"] = round(float(df[nii_col].abs().max()), 2)
            break
    if "EVE_Impact_Pct_Tier1" in df.columns:
        r["avg_eve_sensitivity"] = round(float(df["EVE_Impact_Pct_Tier1"].mean()), 2)
        r["eve_impact_pct_tier1"] = _fmt_pct(df["EVE_Impact_Pct_Tier1"].mean())  # legacy
    for dur_col in ["Duration_Gap_Yrs", "Duration_Gap"]:
        if dur_col in df.columns:
            r["duration_gap_yrs"] = _fmt_pct(df[dur_col].mean())
            break
    # Per-scenario breakdowns for charts
    if "Scenario" in df.columns:
        r["scenario_count"] = int(df["Scenario"].nunique())
        r["scenarios"] = df["Scenario"].value_counts().to_dict()
        # NII by scenario
        for nii_col in ["NII_Impact_Cr", "NII_Cr", "NII_Impact_%", "NII_Impact"]:
            if nii_col in df.columns:
                r["nii_by_scenario"] = df.groupby("Scenario")[nii_col].mean().round(2).to_dict()
                break
        # EVE by scenario
        for eve_col in ["EVE_Impact_Pct_Tier1", "EVE_Impact_%", "EVE_Impact"]:
            if eve_col in df.columns:
                r["eve_by_scenario"] = df.groupby("Scenario")[eve_col].mean().round(2).to_dict()
                break
    return r


@app.get("/api/pillar2/concentration-risk")
def concentration_risk(dimension: Optional[str] = None):
    df = _load().get("P2_Concentration_Risk", pd.DataFrame())
    if dimension:
        df = df[df["Dimension"].astype(str).str.contains(dimension, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/concentration-summary")
def conc_summary():
    df = _load().get("P2_Concentration_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Dimension" in df.columns:
        r["dimension_dist"] = df["Dimension"].value_counts().to_dict()
    if "Category" in df.columns and "Exposure_Cr" in df.columns:
        r["top_exposures"] = df.groupby("Category")["Exposure_Cr"].sum().sort_values(ascending=False).head(10).round(2).to_dict()
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "HHI_Index" in df.columns:
        r["avg_hhi"] = round(float(df["HHI_Index"].mean()), 4)
        r["max_hhi"] = round(float(df["HHI_Index"].max()), 4)
    if "Conc_%" in df.columns:
        r["avg_conc_pct"] = _fmt_pct(df["Conc_%"].mean())
        r["max_conc_pct"] = _fmt_pct(df["Conc_%"].max())
    # Breach summary
    if "Breach_Flag" in df.columns:
        r["breach_dist"] = df["Breach_Flag"].value_counts().to_dict()
        r["breach_count"] = int((df["Breach_Flag"].astype(str).str.lower() == "yes").sum())
    # Dimension + average concentration for bar chart
    if "Dimension" in df.columns and "Conc_%" in df.columns:
        r["conc_by_dimension"] = df.groupby("Dimension")["Conc_%"].mean().round(2).to_dict()
    # Top category exposures per dimension
    if "Dimension" in df.columns and "Category" in df.columns and "Exposure_Cr" in df.columns:
        sector_rows = df[df["Dimension"].str.lower() == "sector"] if "Dimension" in df.columns else df
        if not sector_rows.empty:
            r["sector_exposure"] = sector_rows.groupby("Category")["Exposure_Cr"].sum().sort_values(ascending=False).head(10).round(2).to_dict()
        geo_rows = df[df["Dimension"].str.lower() == "geography"] if "Dimension" in df.columns else pd.DataFrame()
        if not geo_rows.empty:
            r["geo_exposure"] = geo_rows.groupby("Category")["Exposure_Cr"].sum().sort_values(ascending=False).head(10).round(2).to_dict()
    # Utilisation % by dimension
    if "Dimension" in df.columns and "Utilisation_%" in df.columns:
        r["utilisation_by_dimension"] = df.groupby("Dimension")["Utilisation_%"].mean().round(2).to_dict()
    # Total exposure
    if "Exposure_Cr" in df.columns:
        r["total_exposure"] = round(float(df["Exposure_Cr"].sum()), 2)
    return r


@app.get("/api/pillar2/climate-risk")
def climate_risk(sector: Optional[str] = None, state: Optional[str] = None):
    df = _load().get("P2_Climate_Risk", pd.DataFrame())
    if sector:
        df = df[df["Sector"].astype(str).str.contains(sector, case=False, na=False)]
    if state:
        df = df[df["State"].astype(str).str.contains(state, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/climate-summary")
def climate_summary():
    df = _load().get("P2_Climate_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    # Sector exposure
    if "Sector" in df.columns and "Exposure_Cr" in df.columns:
        r["sector_exposure"] = df.groupby("Sector")["Exposure_Cr"].sum().round(2).to_dict()
    # Physical risk — total and average
    if "Physical_Risk_Score" in df.columns:
        r["avg_physical_risk"] = _fmt_pct(df["Physical_Risk_Score"].mean())
    for phys_col in ["Physical_Risk_Exposure_Cr", "Physical_Exposure_Cr"]:
        if phys_col in df.columns:
            r["total_physical"] = round(float(df[phys_col].sum()), 2)
            break
    # If no dedicated physical exposure column, use overall exposure with high physical risk score
    if "total_physical" not in r and "Exposure_Cr" in df.columns and "Physical_Risk_Score" in df.columns:
        mask = df["Physical_Risk_Score"] >= df["Physical_Risk_Score"].median()
        r["total_physical"] = round(float(df.loc[mask, "Exposure_Cr"].sum()), 2)
    # Transition risk — total and average
    if "Transition_Risk_Score" in df.columns:
        r["avg_transition_risk"] = _fmt_pct(df["Transition_Risk_Score"].mean())
    for trans_col in ["Transition_Risk_Exposure_Cr", "Transition_Exposure_Cr"]:
        if trans_col in df.columns:
            r["total_transition"] = round(float(df[trans_col].sum()), 2)
            break
    if "total_transition" not in r and "Exposure_Cr" in df.columns and "Transition_Risk_Score" in df.columns:
        mask = df["Transition_Risk_Score"] >= df["Transition_Risk_Score"].median()
        r["total_transition"] = round(float(df.loc[mask, "Exposure_Cr"].sum()), 2)
    # Overall climate score
    if "Overall_Climate_Score" in df.columns:
        r["avg_climate_score"] = _fmt_pct(df["Overall_Climate_Score"].mean())
    # Carbon intensity
    for carbon_col in ["Carbon_Intensity_tCO2/Cr", "Carbon_Intensity", "Carbon_Intensity_tCO2", "GHG_Intensity"]:
        if carbon_col in df.columns:
            r["avg_carbon_intensity"] = round(float(df[carbon_col].mean()), 2)
            break
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "Net_Zero_Aligned" in df.columns:
        r["net_zero"] = df["Net_Zero_Aligned"].value_counts().to_dict()
    if "TCFD_Category" in df.columns:
        r["tcfd_dist"] = df["TCFD_Category"].value_counts().to_dict()
    # Risk type distribution (Physical vs Transition)
    if "Risk_Type" in df.columns:
        r["risk_type_dist"] = df["Risk_Type"].value_counts().to_dict()
    elif "Physical_Risk_Score" in df.columns and "Transition_Risk_Score" in df.columns:
        df_copy = df.copy()
        df_copy["_dom"] = df_copy.apply(
            lambda row: "Physical" if (row.get("Physical_Risk_Score", 0) or 0) >= (row.get("Transition_Risk_Score", 0) or 0) else "Transition", axis=1
        )
        r["risk_type_dist"] = df_copy["_dom"].value_counts().to_dict()
    # Climate VaR total
    if "Climate_VaR_Cr" in df.columns:
        r["total_climate_var"] = round(float(df["Climate_VaR_Cr"].sum()), 2)
        r["avg_climate_var"] = round(float(df["Climate_VaR_Cr"].mean()), 4)
    # Stranded asset risk distribution
    if "Stranded_Asset_Risk" in df.columns:
        r["stranded_asset_dist"] = df["Stranded_Asset_Risk"].value_counts().to_dict()
    # ESG rating distribution
    if "ESG_Rating" in df.columns:
        r["esg_rating_dist"] = df["ESG_Rating"].value_counts().to_dict()
    # State-wise exposure
    if "State" in df.columns and "Exposure_Cr" in df.columns:
        r["state_exposure"] = df.groupby("State")["Exposure_Cr"].sum().sort_values(ascending=False).head(10).round(2).to_dict()
    # Physical risk by sector
    if "Sector" in df.columns and "Physical_Risk_Score" in df.columns:
        r["physical_risk_by_sector"] = df.groupby("Sector")["Physical_Risk_Score"].mean().round(2).to_dict()
    # Transition risk by sector
    if "Sector" in df.columns and "Transition_Risk_Score" in df.columns:
        r["transition_risk_by_sector"] = df.groupby("Sector")["Transition_Risk_Score"].mean().round(2).to_dict()
    return r


@app.get("/api/pillar2/cyber-risk")
def cyber_risk(severity: Optional[str] = None):
    df = _load().get("P2_Cyber_Risk", pd.DataFrame())
    if severity:
        df = df[df["Severity"].astype(str).str.contains(severity, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/cyber-summary")
def cyber_summary():
    df = _load().get("P2_Cyber_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Financial_Impact_Lakhs" in df.columns:
        r["total_financial_impact"] = round(float(df["Financial_Impact_Lakhs"].sum()), 2)
    if "MTTD_Hrs" in df.columns:
        r["avg_mttd"] = round(float(df["MTTD_Hrs"].mean()), 2)
    if "MTTR_Hrs" in df.columns:
        r["avg_mttr"] = round(float(df["MTTR_Hrs"].mean()), 2)
    if "Severity" in df.columns:
        r["severity_dist"] = df["Severity"].value_counts().to_dict()
    if "Attack_Vector" in df.columns:
        r["attack_vectors"] = df["Attack_Vector"].value_counts().to_dict()
    if "Asset_Affected" in df.columns:
        r["assets_affected"] = df["Asset_Affected"].value_counts().to_dict()
    if "CVSS_Score" in df.columns:
        r["avg_cvss"] = round(float(df["CVSS_Score"].mean()), 2)
    return r


@app.get("/api/pillar2/fraud-risk")
def fraud_risk(channel: Optional[str] = None, fraud_type: Optional[str] = None):
    df = _load().get("P2_Fraud_Risk", pd.DataFrame())
    if channel:
        df = df[df["Channel"].astype(str).str.contains(channel, case=False, na=False)]
    if fraud_type:
        df = df[df["Fraud_Type"].astype(str).str.contains(fraud_type, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/fraud-summary")
def fraud_summary():
    df = _load().get("P2_Fraud_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Amount_Lakhs" in df.columns:
        r["total_amount"] = round(float(df["Amount_Lakhs"].sum()), 2)
    if "Net_Loss_Lakhs" in df.columns:
        r["total_net_loss"] = round(float(df["Net_Loss_Lakhs"].sum()), 2)
    if "Recovery_Rate_%" in df.columns:
        r["avg_recovery_rate"] = _fmt_pct(df["Recovery_Rate_%"].mean())
    if "Channel" in df.columns:
        r["channel_dist"] = df["Channel"].value_counts().to_dict()
    if "Fraud_Type" in df.columns:
        r["fraud_type_dist"] = df["Fraud_Type"].value_counts().to_dict()
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    return r


@app.get("/api/pillar2/third-party-risk")
def third_party(criticality: Optional[str] = None, rag: Optional[str] = None):
    df = _load().get("P2_Third_Party_Risk", pd.DataFrame())
    if criticality:
        df = df[df["Criticality"].astype(str).str.contains(criticality, case=False, na=False)]
    if rag:
        df = df[df["RAG"].astype(str).str.lower() == rag.lower()]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/third-party-summary")
def tpr_summary():
    df = _load().get("P2_Third_Party_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Criticality" in df.columns:
        r["criticality_dist"] = df["Criticality"].value_counts().to_dict()
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "SLA_Breach" in df.columns:
        r["sla_breach"] = df["SLA_Breach"].value_counts().to_dict()
    if "Actual_Uptime_%" in df.columns:
        r["avg_uptime"] = _fmt_pct(df["Actual_Uptime_%"].mean())
    if "Vendor_Risk_Score" in df.columns:
        r["avg_risk_score"] = round(float(df["Vendor_Risk_Score"].mean()), 2)
    return r


@app.get("/api/pillar2/reputational-risk")
def reputational_risk(category: Optional[str] = None):
    df = _load().get("P2_Reputational_Risk", pd.DataFrame())
    if category:
        df = df[df["Category"].astype(str).str.contains(category, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/reputational-summary")
def rep_summary():
    df = _load().get("P2_Reputational_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "Sentiment_Score" in df.columns:
        r["avg_sentiment"] = round(float(df["Sentiment_Score"].mean()), 2)
    if "NPS_Score" in df.columns:
        r["avg_nps"] = round(float(df["NPS_Score"].mean()), 2)
    if "Category" in df.columns:
        r["category_dist"] = df["Category"].value_counts().to_dict()
    if "Customer_Complaints" in df.columns:
        r["total_complaints"] = int(df["Customer_Complaints"].sum())
    if "Complaints_Resolved_%" in df.columns:
        r["avg_resolution_rate"] = _fmt_pct(df["Complaints_Resolved_%"].mean())
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    return r


@app.get("/api/pillar2/strategic-risk")
def strategic_risk(quarter: Optional[str] = None):
    df = _load().get("P2_Strategic_Risk", pd.DataFrame())
    if quarter:
        df = df[df["Quarter"].astype(str).str.contains(quarter, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar2/strategic-summary")
def strategic_summary():
    df = _load().get("P2_Strategic_Risk", pd.DataFrame())
    if df.empty:
        return {}
    r = {}
    if "RAG" in df.columns:
        r["rag"] = df["RAG"].value_counts().to_dict()
    if "BSC_Perspective" in df.columns:
        r["bsc_dist"] = df["BSC_Perspective"].value_counts().to_dict()
    if "Weighted_Score" in df.columns:
        r["avg_weighted_score"] = round(float(df["Weighted_Score"].mean()), 3)
    if "ROCE_%" in df.columns:
        r["avg_roce"] = _fmt_pct(df["ROCE_%"].mean())
    if "ROE_%" in df.columns:
        r["avg_roe"] = _fmt_pct(df["ROE_%"].mean())
    return r


# ── Pillar 3 ──────────────────────────────────────────────────────────────────
@app.get("/api/pillar3/capital-disclosure")
def capital_disclosure(entity: Optional[str] = None):
    df = _load().get("P3_Capital_Disclosure", pd.DataFrame())
    if entity:
        df = df[df["Entity"].astype(str).str.contains(entity, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


@app.get("/api/pillar3/market-disclosure")
def market_disclosure(timeliness: Optional[str] = None):
    df = _load().get("P3_Market_Disclosure", pd.DataFrame())
    if timeliness:
        df = df[df["Timeliness"].astype(str).str.contains(timeliness, case=False, na=False)]
    return {"count": len(df), "data": _j(df)}


# ── Monthly Data ──────────────────────────────────────────────────────────────
@app.get("/api/monthly-data")
def monthly_data():
    df = _load().get("Monthly_Data", pd.DataFrame())
    return {"count": len(df), "data": _j(df)}


# ── Static files & SPA ────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/{full_path:path}")
def spa(full_path: str):
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
