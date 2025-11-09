# diligence/pivoting.py
import pandas as pd
from .formatters import to_num

def add_row_subtotals_and_total(pvt: pd.DataFrame, level=0,
                                subtotal_label="Sous-total", total_label="Total") -> pd.DataFrame:
    if isinstance(pvt.index, pd.MultiIndex) and pvt.index.nlevels >= 2:
        pieces = []
        for g in pvt.index.get_level_values(level).unique():
            block = pvt.xs(g, level=level, drop_level=False)
            sub = block.droplevel(level).sum(numeric_only=True)
            sub_row = pd.DataFrame([sub.values], columns=pvt.columns,
                                   index=pd.MultiIndex.from_tuples([(g, subtotal_label)], names=pvt.index.names))
            pieces.append(pd.concat([block, sub_row]))
        out = pd.concat(pieces)
        total_vals = out.loc[out.index.get_level_values(1)!=subtotal_label].sum(numeric_only=True)
        total_idx = pd.MultiIndex.from_tuples([(total_label, "")], names=pvt.index.names)
        total_row = pd.DataFrame([total_vals.values], columns=pvt.columns, index=total_idx)
        return pd.concat([out, total_row])
    else:
        total_row = pd.DataFrame([pvt.sum(numeric_only=True).values], columns=pvt.columns,
                                 index=pd.Index([total_label], name=pvt.index.name))
        return pd.concat([pvt, total_row])

def build_pivot(df: pd.DataFrame, index_cols, columns_cols, value_cols, agg_choice):
    """
    Retourne (pvt, msg). Si msg non vide, affiche un avertissement au lieu d'un pivot.
    """
    # ── Garde-fous UI ───────────────────────────────────────────
    if not index_cols and not columns_cols:
        return None, "Choisis au moins **une** colonne pour *Lignes* **ou** *Colonnes*."
    if not value_cols:
        return None, "Choisis au moins **une** métrique dans *Valeurs*."

    # ── Préparation des données ─────────────────────────────────
    df_vals = df.copy()
    agg_map = {}
    for col in value_cols:
        if agg_choice in {"sum", "mean", "median", "min", "max"}:
            df_vals[col] = to_num(df_vals[col])
        agg_map[col] = agg_choice

    # ── Pivot ───────────────────────────────────────────────────
    pvt = pd.pivot_table(
        df_vals,
        index=index_cols if index_cols else None,
        columns=columns_cols if columns_cols else None,
        values=value_cols,
        aggfunc=agg_map,
        fill_value=0,
        margins=False
    )

    # 🧹 Supprime les lignes entièrement vides (toutes les colonnes NaN)
    pvt = pvt.dropna(how="all")

    # ── Totaux ──────────────────────────────────────────────────
    if isinstance(pvt.index, pd.MultiIndex) and pvt.index.nlevels >= 2 and not columns_cols:
        pvt = add_row_subtotals_and_total(pvt, level=0)
    else:
        total_row = pd.DataFrame(
            [pvt.sum(numeric_only=True).values],
            columns=pvt.columns,
            index=pd.Index(["Total"], name=pvt.index.name)
        )
        pvt = pd.concat([pvt, total_row])

    # ── Retour ─────────────────────────────────────────────────
    return pvt, ""
