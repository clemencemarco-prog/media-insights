# diligence/file_io.py
# -------------------------------------------------------------
# 📂 Lecture et nettoyage des fichiers CSV ou Excel
# -------------------------------------------------------------

import io, csv
import pandas as pd
import streamlit as st  # ✅ Doit être ici, AVANT le décorateur


@st.cache_data(show_spinner=False)  # ✅ Ne bouge pas
def load_table(uploaded_file) -> pd.DataFrame:
    """Lit un fichier CSV ou Excel importé et le renvoie sous forme de DataFrame propre."""
    if uploaded_file is None:
        raise ValueError("Aucun fichier fourni.")

    name = uploaded_file.name.lower()

    # Si le fichier est un Excel (.xlsx ou .xls)
    if name.endswith((".xlsx", ".xls")):
        import openpyxl
        return pd.read_excel(uploaded_file, engine="openpyxl")

    # Lecture brute du contenu (texte)
    raw = uploaded_file.read()
    uploaded_file.seek(0)  # revient au début du fichier (utile si on veut le relire)

    if not raw:
        raise ValueError("Le fichier est vide.")
    if raw[:2] == b"PK":
        raise ValueError("On dirait un Excel renommé en .csv. Exporte en vrai CSV.")

    # Tentative de décodage (UTF-8 ou Latin-1)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="ignore")

    # Détection du séparateur : , ; tab ou |
    try:
        sep = csv.Sniffer().sniff(text[:5000], [",", ";", "\t", "|"]).delimiter
    except Exception:
        sep = ";" if text.splitlines()[0].count(";") >= text.splitlines()[0].count(",") else ","

    # Lecture en DataFrame
    df = pd.read_csv(io.StringIO(text), sep=sep)

    # Si une seule colonne, on retente avec un autre séparateur
    if df.shape[1] == 1:
        alt = ";" if sep != ";" else ","
        df = pd.read_csv(io.StringIO(text), sep=alt)

    if df.shape[1] == 1:
        raise ValueError("Séparateur inconnu (utilise , ou ;)")

    # Nettoyage : suppression des colonnes vides / 'Unnamed'
    df = df.dropna(how="all").loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)].reset_index(drop=True)
    return df
