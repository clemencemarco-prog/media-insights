# diligence/formatters.py

import pandas as pd


# ──────────────────────────────────────────────────────────────
# Convertir une série en numérique proprement
# ──────────────────────────────────────────────────────────────
def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str)
        .str.replace("\u00A0", "", regex=False)  # espace insécable
        .str.replace(" ", "", regex=False)        # espace normal
        .str.replace(",", ".", regex=False),      # virgule → point
        errors="coerce"
    )


# ──────────────────────────────────────────────────────────────
# Format français : "1 234,56"
# ──────────────────────────────────────────────────────────────
def format_fr(n, decimals=2):
    if pd.isna(n):
        return ""
    s = f"{float(n):,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


# ──────────────────────────────────────────────────────────────
# Format compact : "1.2k", "3.4M", "5.6B"
# ──────────────────────────────────────────────────────────────
def format_compact(n, decimals=2):
    if pd.isna(n):
        return ""
    n = float(n)
    for k, u in [(1e9, "B"), (1e6, "M"), (1e3, "k")]:
        if abs(n) >= k:
            return f"{n / k:.{decimals}f}{u}"
    return f"{n:.{decimals}f}"


# ──────────────────────────────────────────────────────────────
# Détecter si une série contient des pourcentages (ex: CTR)
# ──────────────────────────────────────────────────────────────
def is_percent_series(s: pd.Series):
    name = (s.name or "").lower()
    if "ctr" in name:
        return True
    try:
        vals = pd.to_numeric(s, errors="coerce")
        return ((vals >= 0) & (vals <= 1)).mean() >= 0.8
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# Formater un DataFrame selon le type de colonnes et le format choisi
# ──────────────────────────────────────────────────────────────
def format_dataframe_for_display(df_in: pd.DataFrame, num_format: str) -> pd.DataFrame:
    df_out = df_in.copy()

    for col in df_out.columns:
        if pd.api.types.is_numeric_dtype(df_out[col]):

            # Cas 1 : colonnes de pourcentages
            if is_percent_series(df_out[col]):
                if num_format == "Brut":
                    df_out[col] = (df_out[col] * 100).map(lambda x: f"{x:.2f}%")
                else:
                    df_out[col] = (df_out[col] * 100).map(
                        lambda x: f"{x:,.2f}%".replace(",", " ").replace(".", ",")
                    )

            # Cas 2 : colonnes numériques classiques
            else:
                if num_format == "Séparateurs (1 234,56)":
                    df_out[col] = df_out[col].map(lambda x: format_fr(x, 2))
                elif num_format == "Compact (1.2k / 3.4M)":
                    df_out[col] = df_out[col].map(lambda x: format_compact(x, 2))

    return df_out
