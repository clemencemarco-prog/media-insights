# app.py
import streamlit as st

from diligence.theme import (
    configure_page,
    inject_theme,
    render_header,
    render_sidebar
)
from diligence.file_io import load_table
from diligence.formatters import format_dataframe_for_display, to_num
from diligence.pivoting import build_pivot
from diligence.insights import (
    pivot_to_payload,
    call_openai_comment_on_pivot,
    fallback_comment_on_pivot,
)

# ──────────────────────────────────────────────────────────────
# 1️⃣ CONFIGURATION DE LA PAGE + THÈME
# ──────────────────────────────────────────────────────────────
configure_page()          # set_page_config
inject_theme()            # CSS
render_header()           # bandeau hero + logo


# ──────────────────────────────────────────────────────────────
# 2️⃣ STATE INITIAL
# ──────────────────────────────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = None
if "pivot" not in st.session_state:
    st.session_state.pivot = None
if "value_cols" not in st.session_state:
    st.session_state.value_cols = []
if "num_format" not in st.session_state:
    st.session_state.num_format = "Séparateurs (1 234,56)"


# ──────────────────────────────────────────────────────────────
# 3️⃣ SIDEBAR (“wizard”)
# ──────────────────────────────────────────────────────────────
step = render_sidebar(st.session_state.num_format)

# === Format des nombres (global) ===
with st.sidebar:
    st.subheader("Format des nombres")

    options = [
        "Séparateurs (1 234,56)",
        "Compact (1.2k / 3.4M)",
        "Brut"
    ]

    default = st.session_state.get("num_format", options[0])  # valeur actuelle

    choice = st.selectbox(
        "Affichage",
        options,
        index=options.index(default),
        key="numformat_global"  # clé UNIQUE
    )

    st.session_state.num_format = choice


# ──────────────────────────────────────────────────────────────
# 4️⃣ STEP 1 — UPLOAD
# ──────────────────────────────────────────────────────────────
if step == 1:
    st.markdown("### Step 1 — Upload data")

    with st.container():
        st.markdown('<div class="card">', unsafe_allow_html=True)

        uploaded = st.file_uploader("📂 CSV ou Excel", type=["csv", "xlsx", "xls"])

        if uploaded:
            try:
                df = load_table(uploaded)
                st.session_state.df = df

                st.success(
                    f"Fichier chargé : {uploaded.name} · "
                    f"{df.shape[0]} lignes × {df.shape[1]} colonnes"
                )

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Lignes", f"{len(df):,}".replace(",", " "))
                c2.metric("Colonnes", df.shape[1])

                show_all = st.toggle("📋 Afficher toutes les lignes (aperçu)", value=False)
                n = len(df) if show_all else min(15, len(df))

                st.dataframe(
                    format_dataframe_for_display(df.head(n), st.session_state.num_format),
                    use_container_width=True,
                    height=min(520, 35 * n + 110)
                )

                st.info("Passe à l’étape **Step 2 – Pivot** via la sidebar 👉")

            except Exception as e:
                st.error(f"Erreur de lecture : {e}")

        else:
            st.info("Dépose un fichier pour commencer.")

        st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# 5️⃣ STEP 2 — PIVOT
# ──────────────────────────────────────────────────────────────
elif step == 2:
    st.markdown("### Step 2 — Configure le pivot")

    if st.session_state.df is None:
        st.warning("Importe d’abord un fichier dans **Step 1**.")
    else:
        df = st.session_state.df
        all_cols = df.columns.tolist()

        # ---- Nettoyage des defaults si le fichier a changé
        cols_sig = tuple(all_cols)
        if st.session_state.get("_cols_sig") != cols_sig:
            st.session_state["_cols_sig"] = cols_sig
            for k in ("index_cols", "columns_cols", "value_cols"):
                prev = st.session_state.get(k, [])
                st.session_state[k] = [c for c in prev if c in all_cols]

        default_index = st.session_state.get("index_cols", [])
        default_columns = st.session_state.get("columns_cols", [])
        default_values = st.session_state.get("value_cols", [])

        st.markdown('<div class="card">', unsafe_allow_html=True)

        index_cols = st.multiselect(
            "Lignes (index)",
            options=all_cols,
            #default=default_index,
            key="index_cols"
        )

        #columns_cols = st.multiselect(
        #    "Colonnes (optionnel)",
        #    options=all_cols,
        #    default=default_columns,
        #    key="columns_cols"
        #)
        columns_cols= []

        value_cols = st.multiselect(
            "Valeurs (métriques)",
            options=all_cols,
            #default=default_values,
            key="value_cols"
        )

        agg_choice = st.selectbox(
            "Agrégateur",
            ["sum", "mean", "count", "median", "min", "max"],
            key="agg_choice"
        )

        # ---- Construction du pivot
        pvt, msg = build_pivot(
            df=df,
            index_cols=index_cols,
            columns_cols=columns_cols,
            value_cols=value_cols,
            agg_choice=agg_choice,
        )

        if msg:
            st.info(msg)

        if pvt is not None:
            st.session_state.pivot = pvt  # sauvegarde pour Step 3

            # Style + centrage
            st.markdown(
                """
                <style>
                [data-testid="stDataFrame"] {
                    width: 60% !important;
                    margin: 0 auto;
                    border-radius: 12px;
                }
                .stDataFrame td, .stDataFrame th {
                    white-space: nowrap;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            # Hauteur auto selon le nombre de lignes
            n_rows = pvt.shape[0]
            row_h, header_h, pad = 35, 38, 12
            min_h, max_h = 150, 600
            auto_h = min(max_h, max(min_h, header_h + pad + n_rows * row_h))

            pvt = pvt.dropna(how="all")

            st.success("Pivot calculé ✅")

            st.dataframe(
                format_dataframe_for_display(pvt, st.session_state.num_format),
                use_container_width=False,
                height=auto_h,
            )

        st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# 6️⃣ STEP 3 — INSIGHTS IA
# ──────────────────────────────────────────────────────────────
elif step == 3:
    st.markdown("### Step 3 — Insights IA (sur le pivot)")

    pvt = st.session_state.get("pivot")
    if pvt is None:
        st.warning("Calcule d’abord un pivot dans **Step 2**.")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        # 1) Affichage du pivot actuel
        st.write("**Pivot utilisé pour l’analyse**")
        st.dataframe(
            format_dataframe_for_display(pvt, st.session_state.num_format),
            use_container_width=True
        )

        # 2) Préparation du payload
        try:
            payload = pivot_to_payload(pvt)
        except Exception as e:
            st.error(f"Impossible de préparer les données du pivot : {e}")
            st.markdown('</div>', unsafe_allow_html=True)
            raise

        # 3) Debug (optionnel)
        with st.expander("🔧 Debug : afficher le payload (optionnel)", expanded=False):
            st.json(
                payload if payload["shape"]["rows"] <= 500
                else {**payload, "rows": "(tronqué…)"}
            )

        # 4) Paramètres IA
        st.markdown("### ⚙️ Paramètre d’analyse IA")
        use_openai = st.toggle("🧠 Utiliser OpenAI (si clé .env)", value=True)

        # 5) Génération
        gen = st.button("🧠 Générer le commentaire", type="primary")
        if gen:
            try:
                if use_openai:
                    comment = call_openai_comment_on_pivot(
                        payload,
                        language="fr",
                        audience="media_expert",
                        depth="deep"
                    )
                else:
                    raise RuntimeError("OpenAI désactivé.")
            except Exception as e:
                comment = fallback_comment_on_pivot(payload)
                st.warning(f"(Fallback utilisé) Raison : {e}")

            # 6) Rendu du commentaire
            st.markdown('<div class="card-soft">', unsafe_allow_html=True)
            st.subheader("Commentaire généré")
            st.markdown(comment)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# 7️⃣ STEP 4 — EXPORT
# ──────────────────────────────────────────────────────────────
elif step == 4:
    st.markdown("### Step 4 — Export")

    if st.session_state.pivot is None:
        st.info("Calcule d’abord un pivot dans **Step 2**.")
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)

        pvt = st.session_state.pivot
        st.dataframe(
            format_dataframe_for_display(pvt, st.session_state.num_format),
            use_container_width=True
        )

        st.download_button(
            "⬇️ Télécharger le pivot (CSV brut)",
            data=pvt.to_csv().encode("utf-8"),
            file_name="pivot_export.csv",
            mime="text/csv"
        )

        st.markdown('</div>', unsafe_allow_html=True)
