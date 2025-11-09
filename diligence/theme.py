# diligence/theme.py
import os
import streamlit as st

# -------------------------------
# 1) Page config
# -------------------------------
def configure_page():
    st.set_page_config(
        page_title="Media Insights – Diligence",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded",
    )

# -------------------------------
# 2) CSS / theme
#    - removes Streamlit header (white bar)
#    - removes toolbar & decoration
#    - removes sidebar header
#    - keeps a tiny top padding for your own title block
# -------------------------------
def inject_theme():
    st.markdown("""
    <style>
    /* 🧹 SUPPRESSION TOTALE DU HEADER STREAMLIT ET DE LA BARRE BLANCHE */
    .stApp > header[data-testid="stHeader"],
    [data-testid="stDecoration"],
    header[data-testid="stHeader"],
    [data-testid="stHeader"] *,
    [data-testid="stToolbar"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: 0 !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    /* Supprime la marge de sécurité que Streamlit ajoute autour du header */
    [data-testid="stAppViewContainer"],
    .stApp > div:first-child,
    main[role="main"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
        background: #F7F9FC !important;
        box-shadow: none !important;
        border-top: none !important;
    }

    /* Conteneur principal : zéro padding-top */
    .block-container {
        padding-top: 0 !important;
        margin-top: 0 !important;
        background: #F7F9FC !important;
    }

    /* Corps et HTML */
    html, body {
        margin: 0 !important;
        padding: 0 !important;
        background: #F7F9FC !important;
        overflow-x: hidden !important;
    }

    /* Kill la shadow résiduelle dans certaines versions (pseudo éléments) */
    [data-testid="stAppViewContainer"]::before,
    [data-testid="stAppViewContainer"]::after,
    .stApp::before,
    .stApp::after {
        display: none !important;
        content: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    /* Sidebar */
    [data-testid="stSidebarHeader"] {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    section[data-testid="stSidebar"]{
      transform:none !important; visibility:visible !important;
      position:sticky !important; top:0 !important; height:100vh !important;
      min-width:280px !important; max-width:280px !important;
      background:#FFFFFF !important;
      border-right:1px solid #E5E7EB !important;
    }

    /* Footer + Menu */
    #MainMenu, footer { visibility: hidden !important; display: none !important; }

    /* Ajuste ton background */
    :root {
        --brand:#2563EB;
        --bg:#F7F9FC;
    }
    </style>
    """, unsafe_allow_html=True)


# -------------------------------
# 3) Custom header (your title)
# -------------------------------
def render_header():
    left, right = st.columns([1, .28])
    with left:
        st.markdown("""
        <div class="card" style="
            background:linear-gradient(135deg,#EFF4FF 0%,#F7F9FF 100%);
            border:1px solid #e6ecff; border-radius:18px; padding:22px;
            box-shadow:0 4px 14px rgba(37,99,235,.08); margin-bottom:12px;">
          <h2 style="margin:0 0 6px;">Media Insights – Diligence</h2>
          <p style="color:#475569;margin:0;">
            Importe tes données média, construis un tableau croisé, puis génère un commentaire 🧠 automatiquement.
          </p>
        </div>
        """, unsafe_allow_html=True)
    with right:
        if os.path.exists("logo.png"):
            st.image("logo.png", width=160)

# -------------------------------
# 4) Sidebar (exported name matches your import)
# -------------------------------
def render_sidebar(current_num_format: str | None = None):
    with st.sidebar:
        st.markdown('<div class="sidebar-steps">', unsafe_allow_html=True)
        st.header("Guide")
        step = st.radio(
            "Navigation",
            options=[1,2,3,4],
            format_func=lambda x: {
                1:"Step 1 – Upload",
                2:"Step 2 – Pivot",
                3:"Step 3 – Insights IA",
                4:"Step 4 – Export"
            }[x],
            label_visibility="collapsed"
        )
        st.markdown('</div>', unsafe_allow_html=True)
    return step
