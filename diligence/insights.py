# diligence/insights.py
import os, json, re
from pathlib import Path
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# ── OpenAI client ─────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

def _get_client():
    # Charge .env si besoin (rend le module autonome)
    if not os.getenv("OPENAI_API_KEY"):
        load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
        load_dotenv()  # fallback sur cwd
    if OpenAI is None:
        raise RuntimeError("Lib openai absente.")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY manquante.")
    return OpenAI(api_key=api_key)

# ── PIVOT → payload générique (inchangé) ─────────────────────────────────────
def pivot_to_payload(pvt: pd.DataFrame, max_rows: int = 1000) -> dict:
    tbl = pvt.copy()
    # Aplatit d'éventuelles colonnes MultiIndex
    if isinstance(tbl.columns, pd.MultiIndex):
        tbl.columns = [" | ".join(map(str, col)).strip() for col in tbl.columns]
    tbl = tbl.reset_index()
    if len(tbl) > max_rows:
        tbl = tbl.head(max_rows)

    numeric_cols = [c for c in tbl.columns if pd.api.types.is_numeric_dtype(tbl[c])]
    stats = {}
    for c in numeric_cols:
        s = pd.to_numeric(tbl[c], errors="coerce")
        stats[c] = {
            "sum": float(s.sum(skipna=True)),
            "mean": float(s.mean(skipna=True)) if s.notna().any() else 0.0,
            "min": float(s.min(skipna=True)) if s.notna().any() else 0.0,
            "max": float(s.max(skipna=True)) if s.notna().any() else 0.0,
            "non_null": int(s.notna().sum()),
        }

    return {
        "shape": {"rows": int(tbl.shape[0]), "cols": int(tbl.shape[1])},
        "columns": list(tbl.columns),
        "numeric_summary": stats,
        "rows": tbl.to_dict(orient="records"),
    }

def _shrink_payload_for_prompt(payload: dict, head: int = 25, tail: int = 10) -> dict:
    """Réduit le payload pour le prompt (évite l’explosion de tokens)."""
    rows = payload.get("rows", [])
    sampled = rows[:head] + (rows[-tail:] if len(rows) > head + tail else [])
    return {
        "shape": payload.get("shape", {}),
        "columns": payload.get("columns", [])[:60],   # limite le nb de colonnes affichées
        "numeric_summary": payload.get("numeric_summary", {}),
        "rows": sampled,
        "note": f"rows sampled: head={min(head, len(rows))}, tail={min(tail, max(0, len(rows)-head))}",
    }

# ── Aides “intelligentes” pour lecture médias & calculs pondérés ─────────────
def _find_col(cols, *candidates):
    """Cherche une colonne par mots-clés (insensible à la casse, accepte variations)."""
    pat = re.compile("|".join([fr"\b{re.escape(c)}\b" for c in candidates]), re.I)
    for c in cols:
        if pat.search(str(c)):
            return c
    return None

def _numeric(series_like):
    try:
        s = pd.to_numeric(series_like, errors="coerce")
        return s
    except Exception:
        return pd.Series([np.nan]*len(series_like))

def _infer_metrics_from_payload(payload: dict):
    cols = payload.get("columns", [])
    col_impr   = _find_col(cols, "Impressions", "Impr", "Imps")
    col_clicks = _find_col(cols, "Clicks", "Click", "Clics")
    col_ctr    = _find_col(cols, "CTR", "Click-Through Rate")
    col_spend  = _find_col(cols, "Spend", "Cost", "Dépense", "Budget")
    col_cpc    = _find_col(cols, "CPC")
    col_cpm    = _find_col(cols, "CPM")

    # Choisir une “métrique primaire” pertinente pour classer top/bottom
    primary_numeric = None
    for cand in [col_spend, col_clicks, col_impr, col_ctr, col_cpc, col_cpm]:
        if cand is not None:
            primary_numeric = cand
            break
    if primary_numeric is None:
        # fallback : première colonne numérique détectée dans les rows
        for c in cols:
            vals = [_ for _ in (r.get(c) for r in payload.get("rows", []))]
            if any(isinstance(v, (int, float)) for v in vals if v is not None):
                primary_numeric = c
                break

    return {
        "impressions": col_impr,
        "clicks": col_clicks,
        "ctr": col_ctr,
        "spend": col_spend,
        "cpc": col_cpc,
        "cpm": col_cpm,
        "primary": primary_numeric,
    }

def _analyze_payload(payload: dict):
    """Calcule pondérations, dispersion, top/bottom et checks qualité (pour guider le LLM)."""
    rows = payload.get("rows", [])
    m = _infer_metrics_from_payload(payload)

    def col_series(name):
        if name is None:
            return None
        s = pd.Series([r.get(name) for r in rows])
        return _numeric(s)

    s_impr   = col_series(m["impressions"])
    s_clicks = col_series(m["clicks"])
    s_ctr    = col_series(m["ctr"])
    s_spend  = col_series(m["spend"])
    s_cpc    = col_series(m["cpc"])
    s_cpm    = col_series(m["cpm"])

    # Pondérations
    weighted = {}
    if s_impr is not None and s_clicks is not None and s_impr.notna().any():
        sum_impr = float(np.nansum(s_impr))
        sum_clicks = float(np.nansum(s_clicks))
        weighted["ctr_weighted"] = (sum_clicks / sum_impr) if sum_impr > 0 else None
        weighted["clicks_sum"] = sum_clicks
        weighted["impressions_sum"] = sum_impr
    else:
        weighted["ctr_weighted"] = None

    if s_spend is not None and s_clicks is not None and s_clicks.notna().any():
        sum_spend = float(np.nansum(s_spend))
        sum_clicks = float(np.nansum(s_clicks))
        weighted["cpc_weighted"] = (sum_spend / sum_clicks) if (sum_clicks and sum_clicks > 0) else None
        weighted["spend_sum"] = sum_spend
    else:
        weighted["cpc_weighted"] = None

    if s_spend is not None and s_impr is not None and s_impr.notna().any():
        sum_spend = float(np.nansum(s_spend))
        sum_impr  = float(np.nansum(s_impr))
        weighted["cpm_weighted"] = (sum_spend / sum_impr * 1000) if (sum_impr and sum_impr > 0) else None

    # Dispersion sur la métrique primaire
    primary = m["primary"]
    s_primary = col_series(primary) if primary else None
    dispersion = {}
    if s_primary is not None and s_primary.notna().any():
        vals = s_primary.dropna().values
        dispersion = {
            "std": float(np.nanstd(vals, ddof=0)),
            "iqr": float(np.nanpercentile(vals, 75) - np.nanpercentile(vals, 25)),
            "min": float(np.nanmin(vals)),
            "max": float(np.nanmax(vals))
        }

    # Top / Bottom (sur métrique primaire)
    def build_ranked(rows, key_col, topn=5):
        if key_col is None:
            return []
        def getv(r):
            v = r.get(key_col)
            return float(v) if isinstance(v, (int, float)) else -np.inf
        ranked = sorted(rows, key=getv, reverse=True)
        return {"top": ranked[:topn], "bottom": list(reversed(ranked[-topn:]))}

    ranking = build_ranked(rows, primary, topn=5)

    # Qualité : CTR ~ Clicks/Impr ?
    quality = {"ctr_vs_ratio_warning": False, "missing_columns": []}
    if m["ctr"] and (m["clicks"] and m["impressions"]):
        ratio = s_clicks / s_impr.replace({0: np.nan}) if s_impr is not None else None
        if ratio is not None and s_ctr is not None:
            try:
                diff = np.nanmean(np.abs(ratio - s_ctr))
                quality["ctr_vs_ratio_warning"] = bool(diff > 0.02)  # > 2 pts en absolu
                quality["ctr_vs_ratio_avg_abs_diff"] = float(diff)
            except Exception:
                pass
    for label, name in (("impressions", "Impressions"), ("clicks", "Clicks"), ("spend", "Spend")):
        if m[label] is None:
            quality["missing_columns"].append(name)

    return {
        "inferred_metrics": m,
        "weighted": weighted,
        "dispersion_on_primary": {"metric": primary, **dispersion} if dispersion else {"metric": primary},
        "ranking_on_primary": {"metric": primary, **ranking},
        "data_quality": quality
    }

# ── Appel LLM renforcé (utilise l’analyse ci-dessus) ─────────────────────────
def call_openai_comment_on_pivot(
    payload: dict,
    language: str = "fr",
    audience: str = "media_expert",   # "media_expert" | "executive" | "marketing"
    depth: str = "deep"               # "deep" | "standard" | "brief"
) -> str:
    client = _get_client()
    slim = _shrink_payload_for_prompt(payload, head=25, tail=10)
    analysis = _analyze_payload(payload)

    if audience == "media_expert":
        persona = (
            "Tu es un expert en achat média / trading desk, culture data & attribution avancée. "
            "Tu écris pour un public de pairs (traders, analysts, CMO data-driven)."
        )
        length_hint = {"deep": 1200, "standard": 800, "brief": 450}[depth]
    elif audience == "executive":
        persona = "Tu es un directeur média parlant à un COMEX. Synthèse orientée business & décisions."
        length_hint = {"deep": 900, "standard": 600, "brief": 350}[depth]
    else:
        persona = "Tu es un stratège marketing orienté brand & performance."
        length_hint = {"deep": 900, "standard": 600, "brief": 350}[depth]

    prompt = f"""
{persona}

On te fournit un **pivot agrégé** et une **analyse pré-calculée** (pondérations, dispersion, top/bottom, checks qualité).
Rédige un rapport en **{language}**. **Utilise obligatoirement les agrégats pondérés** et aligne tous les chiffres sur ces agrégats.
N’invente aucune colonne manquante. Si une métrique est absente, propose le test/trace pour l’obtenir.

### Données (échantillon du pivot)
{json.dumps(slim, ensure_ascii=False, indent=2)}

### Analyse pré-calculée (à exploiter explicitement)
{json.dumps(analysis, ensure_ascii=False, indent=2)}

### Structure attendue
1) **Executive summary (2–3 phrases)** — axe principal, **CTR pondéré**, **CPC/CPM pondérés** si disponibles, risques/opportunités.
2) **Drivers de performance**
   - **Trade-off scale vs efficiency** (utilise CTR, CPC, CPM pondérés si présents).
   - Dispersion & hétérogénéité : cite l’écart-type/IQR de la métrique primaire.
   - **Outliers** (top/bottom) + hypothèses (ciblage, créa, fréquence, dayparting).
3) **Qualité & limites des données**
   - Signale les incohérences détectées (**CTR vs Clicks/Impressions**) et les colonnes manquantes.
4) **Plan d’actions priorisé (tableau)**
   - 3 à 5 actions classées **Impact↑ / Effort↓**, avec: Hypothèse, Test/Changement, KPI cible, Risque.
5) **Annexe courte**
   - 1–2 métriques numériques réellement pertinentes avec **ordres de grandeur**.

### Règles
- Appuie chaque recommandation sur un **signal chiffré** (ex: écart CPM/CTR pondérés, dispersion inter-segments).
- Si la **moyenne simple** diffère de la **pondérée** (>10%), **mentionne l’écart et privilégie la pondérée**.
- Longueur cible: ~{length_hint} tokens. Style concis, technique, sans fluff.
"""

    resp = client.chat.completions.create(
        model="gpt-4o-mini",           # passe à "gpt-4o" si tu veux plus costaud
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=length_hint
    )
    return resp.choices[0].message.content.strip()

# ── Fallback (sans OpenAI) ───────────────────────────────────────────────────
def fallback_comment_on_pivot(payload: dict) -> str:
    rows = payload.get("rows", [])
    if not rows:
        return "Aucune donnée dans le pivot."
    stats = payload.get("numeric_summary", {})
    if not stats:
        return "**TL;DR** — Pivot non numérique : vérifie les métriques choisies."

    num_cols = list(stats.keys())
    first = num_cols[0]
    total = stats[first]["sum"]
    mean  = stats[first]["mean"]

    try:
        top_rows = sorted(
            [r for r in rows if isinstance(r.get(first), (int, float))],
            key=lambda r: r.get(first) or 0,
            reverse=True
        )[:3]
    except Exception:
        top_rows = []

    lines = [
        f"**TL;DR** — La métrique « {first} » totalise {total:,.2f} (moyenne {mean:,.2f})."
        .replace(",", " ").replace(".", ","),
    ]
    if top_rows:
        lines.append("Top lignes (selon la première métrique numérique) :")
        # Exclut les colonnes numériques du label
        numeric_names = set(stats.keys())
        for r in top_rows:
            label = " | ".join(str(v) for k, v in r.items() if k not in numeric_names)[:120]
            lines.append(f"- {label} → {first}={r.get(first)}")
    lines.append(
        "Recos : approfondir les segments en tête, vérifier les extrêmes, et tester des variantes sur les segments sous-performants."
    )
    return "\n".join(lines)
