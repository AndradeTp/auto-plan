import os
import time
import tempfile
import streamlit as st

from core.scraper import executar_scraping
from core.analyzer import analisar_pdf, normalizar_texto
from core.planner import gerar_planilha
from core.drive_client import upload_excel

# ──────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Auto Plan",
    page_icon="https://img.icons8.com/ios/50/8B6F47/document--v1.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# DESIGN TOKENS
# ──────────────────────────────────────────────
# Cores do tema (espelhadas do HTML original)
OFF_WHITE = "#F7F5F2"
OFF_WHITE_DARK = "#EFEDE9"
PAPER = "#FAF9F7"
INK_DARK = "#1A1916"
INK_MID = "#4A4843"
INK_LIGHT = "#8A8784"
BORDER = "#E2DDD8"
BORDER_MID = "#CBC5BE"
ACCENT = "#8B6F47"
ACCENT_HOVER = "#7A6040"
SUCCESS = "#3DAA73"
SUCCESS_BG = "rgba(61,170,115,0.08)"
SUCCESS_BORDER = "rgba(61,170,115,0.25)"

# ──────────────────────────────────────────────
# AUTENTICAÇÃO POR TOKEN
# ──────────────────────────────────────────────
def _checar_token():
    tokens_validos = st.secrets.get("TOKENS_VALIDOS", [])

    if st.session_state.get("autenticado"):
        return

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=DM+Sans:wght@300;400;500&display=swap');
        .stApp {{ background-color: {OFF_WHITE}; }}
        .login-wrap {{
            max-width: 400px;
            margin: 100px auto 0 auto;
            text-align: center;
        }}
        .login-logo {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 28px;
            font-weight: 600;
            color: {INK_DARK};
            letter-spacing: -0.02em;
            margin-bottom: 32px;
        }}
        .login-logo em {{
            font-style: italic;
            color: {ACCENT};
        }}
        .login-card {{
            background: {PAPER};
            border: 1px solid {BORDER};
            border-radius: 8px;
            padding: 40px 36px;
            text-align: left;
        }}
        .login-title {{
            font-family: 'Playfair Display', Georgia, serif;
            font-size: 24px;
            font-weight: 500;
            color: {INK_DARK};
            margin-bottom: 4px;
        }}
        .login-sub {{
            font-family: 'DM Sans', sans-serif;
            font-size: 14px;
            color: {INK_LIGHT};
            margin-bottom: 28px;
            font-weight: 300;
            line-height: 1.6;
        }}
    </style>
    <div class="login-wrap">
        <div class="login-logo">Auto<em>Plan</em></div>
        <div class="login-card">
            <div class="login-title">Acesso restrito</div>
            <div class="login-sub">Insira seu token para continuar.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    token_input = st.text_input("Token de acesso", type="password", placeholder="Token de acesso", label_visibility="collapsed")
    entrar = st.button("Entrar", type="primary", use_container_width=True)

    if entrar:
        if token_input in tokens_validos:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Token invalido. Contate o administrador.")

    st.stop()


_checar_token()

# ──────────────────────────────────────────────
# CSS GLOBAL
# ──────────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=DM+Sans:wght@300;400;500&display=swap');

    html, body, [class*="css"] {{
        font-family: 'DM Sans', sans-serif;
        color: {INK_DARK};
    }}

    /* ── Fundo geral ── */
    .stApp {{
        background-color: {OFF_WHITE};
    }}

    /* ── Sidebar ── */
    section[data-testid="stSidebar"] {{
        background-color: {PAPER};
        border-right: 1px solid {BORDER};
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown span {{
        color: {INK_MID};
    }}

    /* ── Headings ── */
    h1 {{
        font-family: 'Playfair Display', Georgia, serif !important;
        font-weight: 500 !important;
        color: {INK_DARK} !important;
        letter-spacing: -0.025em !important;
    }}
    h3 {{
        font-family: 'DM Sans', sans-serif !important;
        font-size: 11px !important;
        font-weight: 500 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        color: {INK_LIGHT} !important;
    }}

    /* ── Dividers ── */
    hr {{
        border-color: {BORDER} !important;
    }}

    /* ── Inputs ── */
    input, textarea, select {{
        background: #fff !important;
        color: {INK_DARK} !important;
        border: 1px solid {BORDER_MID} !important;
        border-radius: 4px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 15px !important;
    }}
    input:focus, textarea:focus, select:focus {{
        border-color: {ACCENT} !important;
        box-shadow: none !important;
    }}

    /* ── Botão principal ── */
    div.stButton > button[kind="primary"],
    div.stButton > button[data-testid="stBaseButton-primary"] {{
        background: {ACCENT} !important;
        color: #fff !important;
        border: none !important;
        border-radius: 4px !important;
        padding: 14px 28px !important;
        font-size: 15px !important;
        font-weight: 400 !important;
        font-family: 'DM Sans', sans-serif !important;
        letter-spacing: -0.01em !important;
        transition: opacity 0.15s !important;
    }}
    div.stButton > button[kind="primary"]:hover,
    div.stButton > button[data-testid="stBaseButton-primary"]:hover {{
        background: {ACCENT_HOVER} !important;
        opacity: 0.9 !important;
    }}

    /* ── Botão secundário ── */
    div.stButton > button[kind="secondary"],
    div.stButton > button[data-testid="stBaseButton-secondary"],
    div.stDownloadButton > button {{
        background: none !important;
        color: {INK_DARK} !important;
        border: 1px solid {BORDER_MID} !important;
        border-radius: 4px !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 14px !important;
        transition: border-color 0.15s !important;
    }}
    div.stDownloadButton > button:hover {{
        border-color: {ACCENT} !important;
    }}

    /* ── Métricas ── */
    div[data-testid="metric-container"] {{
        background: {PAPER};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 16px 20px;
    }}
    div[data-testid="metric-container"] label {{
        color: {INK_LIGHT} !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-family: 'DM Sans', sans-serif !important;
        font-weight: 500 !important;
    }}
    div[data-testid="metric-container"] [data-testid="metric-value"] {{
        color: {INK_DARK} !important;
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 28px !important;
        font-weight: 500 !important;
    }}

    /* ── DataFrame / tabela ── */
    .stDataFrame {{
        border: 1px solid {BORDER} !important;
        border-radius: 6px !important;
    }}

    /* ── Expander ── */
    .streamlit-expanderHeader {{
        font-family: 'DM Sans', sans-serif !important;
        font-size: 13px !important;
        color: {INK_MID} !important;
        font-weight: 500 !important;
    }}

    /* ── Slider ── */
    .stSlider > div > div {{
        color: {INK_LIGHT} !important;
    }}

    /* ── Sidebar labels ── */
    .sidebar-label {{
        font-family: 'DM Sans', sans-serif;
        font-size: 11px;
        font-weight: 500;
        color: {INK_LIGHT};
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }}

    /* ── Log de execucao ── */
    .log-container {{
        display: flex;
        flex-direction: column;
        gap: 2px;
    }}
    .log-line {{
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 16px;
        border-radius: 4px;
        transition: background 0.3s;
    }}
    .log-line:last-child {{
        background: {OFF_WHITE_DARK};
    }}
    .log-line .log-icon {{
        flex-shrink: 0;
        margin-top: 2px;
        color: {INK_LIGHT};
    }}
    .log-line:last-child .log-icon {{
        color: {ACCENT};
    }}
    .log-line .log-text {{
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        color: {INK_DARK};
        line-height: 1.4;
    }}
    .log-line .log-detail {{
        font-size: 12px;
        color: {INK_LIGHT};
        margin-top: 2px;
    }}

    /* ── Status banners ── */
    .status-running {{
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 16px;
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {INK_LIGHT};
        font-weight: 500;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}
    .status-done {{
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 20px 24px;
        background: {SUCCESS_BG};
        border: 1px solid {SUCCESS_BORDER};
        border-radius: 6px;
    }}
    .status-done .check-circle {{
        width: 28px;
        height: 28px;
        border-radius: 50%;
        background: rgba(61,170,115,0.15);
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}
    .status-done .status-text {{
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        font-weight: 500;
        color: {INK_DARK};
    }}
    .status-done .status-sub {{
        font-size: 12px;
        color: {INK_LIGHT};
        margin-top: 3px;
    }}

    /* ── Progress bar ── */
    .progress-wrap {{
        margin-bottom: 28px;
    }}
    .progress-header {{
        display: flex;
        justify-content: space-between;
        margin-bottom: 10px;
    }}
    .progress-label {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {INK_LIGHT};
        font-weight: 500;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}
    .progress-pct {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {INK_DARK};
        font-weight: 500;
    }}
    .progress-track {{
        height: 3px;
        background: {BORDER};
        border-radius: 100px;
        overflow: hidden;
    }}
    .progress-fill {{
        height: 100%;
        background: {ACCENT};
        border-radius: 100px;
        transition: width 0.6s ease;
    }}

    /* ── Info panel (como funciona) ── */
    .info-panel {{
        background: {PAPER};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 36px;
    }}
    .info-panel-title {{
        font-family: 'Playfair Display', Georgia, serif;
        font-style: italic;
        color: {ACCENT};
        font-size: 21px;
        margin-bottom: 20px;
    }}
    .info-step {{
        display: flex;
        gap: 20px;
        padding: 20px 0;
        border-bottom: 1px solid {BORDER};
    }}
    .info-step:last-child {{
        border-bottom: none;
    }}
    .info-step-num {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 13px;
        font-weight: 600;
        color: {ACCENT};
        flex-shrink: 0;
        margin-top: 2px;
        opacity: 0.7;
    }}
    .info-step-title {{
        font-family: 'DM Sans', sans-serif;
        font-size: 14px;
        font-weight: 500;
        color: {INK_DARK};
        margin-bottom: 6px;
    }}
    .info-step-desc {{
        font-family: 'DM Sans', sans-serif;
        font-size: 13px;
        color: {INK_LIGHT};
        line-height: 1.6;
    }}
    .info-footer {{
        margin-top: 20px;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        color: {INK_LIGHT};
        line-height: 1.7;
    }}

    /* ── Badge ── */
    .badge {{
        display: inline-block;
        font-family: 'DM Sans', sans-serif;
        font-size: 12px;
        color: {INK_LIGHT};
        font-weight: 400;
        letter-spacing: 0.04em;
    }}

    /* ── Spinner SVG ── */
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .spin {{ animation: spin 1s linear infinite; }}

    /* ── Check SVG ── */
    .check-svg {{ color: {INK_LIGHT}; }}
    .check-svg-done {{ color: {SUCCESS}; }}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:12px 0 20px 0;">
        <span style="font-family:'Playfair Display',Georgia,serif;font-size:20px;font-weight:600;color:{INK_DARK};letter-spacing:-0.02em;">
            Auto<em style="font-style:italic;color:{ACCENT};">Plan</em>
        </span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Link do curso
    st.markdown(f"""<div class="sidebar-label">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 4H4a3 3 0 000 6h2M10 4h2a3 3 0 010 6h-2M5.5 8h5" stroke="{INK_LIGHT}" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        Link do curso
    </div>""", unsafe_allow_html=True)
    url_pacote = st.text_input(
        "URL do Pacote",
        placeholder="https://www.estrategiaconcursos.com.br/...",
        label_visibility="collapsed",
    )

    # Pasta do Drive
    st.markdown(f"""<div class="sidebar-label" style="margin-top:20px;">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 4.5A1.5 1.5 0 013.5 3h3l1.5 2H13a1.5 1.5 0 011.5 1.5v5A1.5 1.5 0 0113 13H3a1.5 1.5 0 01-1.5-1.5v-7z" stroke="{INK_LIGHT}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        Pasta no Drive
    </div>""", unsafe_allow_html=True)
    drive_folder = st.text_input("Pasta de destino", value="Auto Plan", label_visibility="collapsed")

    # Nome do arquivo
    st.markdown(f"""<div class="sidebar-label" style="margin-top:20px;">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M9 2H4a1.5 1.5 0 00-1.5 1.5v9A1.5 1.5 0 004 14h8a1.5 1.5 0 001.5-1.5V6.5L9 2z" stroke="{INK_LIGHT}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M9 2v4.5H13.5" stroke="{INK_LIGHT}" stroke-width="1.4" stroke-linecap="round"/>
        </svg>
        Nome da planilha
    </div>""", unsafe_allow_html=True)
    output_filename = st.text_input("Nome do arquivo", value="plano_estudos.xlsx", label_visibility="collapsed")

    st.divider()

    with st.expander("Configuracoes avancadas"):
        max_paginas = st.slider("Max. paginas por bloco", 20, 100, 50)
        sufixo = st.text_input("Sufixo das disciplinas", value=" - Eng. Petro. Petrobras")
        model_name = st.selectbox(
            "Modelo de analise",
            ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"],
            label_visibility="collapsed",
        )

    st.divider()
    st.markdown(f'<div class="badge">Por: Thiago Paiva</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# LAYOUT PRINCIPAL — 2 colunas
# ──────────────────────────────────────────────
col_main, col_info = st.columns([3, 2], gap="large")

with col_main:
    # Titulo
    st.markdown(f"""
    <div style="margin-bottom:8px;">
        <h1 style="font-size:clamp(28px,3vw,40px) !important;line-height:1.15 !important;margin:0 !important;">
            Novo plano<br>
            <em style="font-style:italic;color:{ACCENT};">de estudos</em>
        </h1>
        <p style="margin-top:12px;font-size:15px;color:{INK_LIGHT};line-height:1.6;font-weight:300;">
            Preencha os parametros na barra lateral e clique em gerar.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # Botao principal
    iniciar = st.button("Gerar plano", type="primary", disabled=not url_pacote, use_container_width=True)

    # Placeholders
    progress_placeholder = st.empty()
    status_placeholder = st.empty()
    log_placeholder = st.empty()

    # Metricas
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    m1, m2, m3, m4 = st.columns(4)
    metric_pdfs    = m1.empty()
    metric_topicos = m2.empty()
    metric_blocos  = m3.empty()
    metric_status  = m4.empty()

    # Resultado
    resultado_placeholder = st.empty()

with col_info:
    st.markdown(f"""
    <div class="info-panel">
        <div class="info-panel-title">Como funciona</div>

        <div class="info-step">
            <span class="info-step-num">01</span>
            <div>
                <div class="info-step-title">Link do curso</div>
                <div class="info-step-desc">Cole o link do curso na plataforma Estrategia Concursos. O script extrai toda a estrutura de aulas.</div>
            </div>
        </div>

        <div class="info-step">
            <span class="info-step-num">02</span>
            <div>
                <div class="info-step-title">Pasta no Drive</div>
                <div class="info-step-desc">Informe o caminho da pasta onde o plano sera salvo no Google Drive.</div>
            </div>
        </div>

        <div class="info-step">
            <span class="info-step-num">03</span>
            <div>
                <div class="info-step-title">Nome da planilha</div>
                <div class="info-step-desc">Defina o nome do arquivo .xlsx que sera gerado. Use nomes descritivos para facil localizacao.</div>
            </div>
        </div>

        <div class="info-footer">
            O plano gerado tera blocos de estudo por volta de 50 paginas.<br>
            Ao fim, lhe sera enviado o link do seu plano.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# HELPERS DE LOG VISUAL
# ──────────────────────────────────────────────
CHECK_SVG = '<svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M2.5 7l3.5 3.5 5.5-6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>'
SPIN_SVG = f'<svg class="spin" width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="{INK_LIGHT}" stroke-width="1.5" stroke-opacity="0.2"/><path d="M8 2a6 6 0 016 6" stroke="{ACCENT}" stroke-width="1.5" stroke-linecap="round"/></svg>'

def render_log_html(steps: list[dict], is_done: bool = False) -> str:
    """Renderiza log como lista de etapas com checkmarks."""
    html = '<div class="log-container">'
    for i, step in enumerate(steps):
        is_last = i == len(steps) - 1
        if is_done and is_last:
            icon_class = "check-svg-done"
        elif is_last and not is_done:
            icon_class = ""
            icon = SPIN_SVG
        else:
            icon_class = "check-svg"

        if not (is_last and not is_done):
            icon = f'<span class="{icon_class}">{CHECK_SVG}</span>'

        bg = f"background:{OFF_WHITE_DARK};" if is_last and not is_done else ""
        html += f"""
        <div class="log-line" style="{bg}">
            <span class="log-icon">{icon}</span>
            <div>
                <div class="log-text">{step['label']}</div>
                <div class="log-detail">{step.get('detail', '')}</div>
            </div>
        </div>"""

    if not is_done and steps:
        html += f"""
        <div class="log-line">
            <span class="log-icon">{SPIN_SVG}</span>
            <div class="log-text" style="color:{INK_LIGHT};font-size:13px;">Processando...</div>
        </div>"""

    html += '</div>'
    return html


def render_progress_html(pct: int) -> str:
    return f"""
    <div class="progress-wrap">
        <div class="progress-header">
            <span class="progress-label">Progresso</span>
            <span class="progress-pct">{pct}%</span>
        </div>
        <div class="progress-track">
            <div class="progress-fill" style="width:{pct}%;"></div>
        </div>
    </div>"""


def render_success_html(drive_link: str = "") -> str:
    link_text = ""
    if drive_link:
        link_text = f'<div class="status-sub">Disponivel em: <a href="{drive_link}" target="_blank" style="color:{ACCENT};text-decoration:none;">Link do Drive</a></div>'

    return f"""
    <div class="status-done">
        <div class="check-circle">
            <span class="check-svg-done">{CHECK_SVG}</span>
        </div>
        <div>
            <div class="status-text">Plano criado com sucesso</div>
            {link_text}
        </div>
    </div>"""


# ──────────────────────────────────────────────
# EXECUÇÃO
# ──────────────────────────────────────────────
if iniciar:
    try:
        email   = st.secrets["SEU_EMAIL"]
        senha   = st.secrets["SUA_SENHA"]
        api_key = st.secrets["GOOGLE_API_KEY"]
    except KeyError as e:
        st.error(f"Configuracao ausente: {e}. Verifique as variaveis de ambiente.")
        st.stop()

    log_steps = []
    total_steps = 6  # estimativa

    def log(msg: str):
        """Adiciona uma etapa visual ao log."""
        # Extrai label e detail da mensagem
        if " — " in msg:
            parts = msg.split(" — ", 1)
            label, detail = parts[0], parts[1]
        elif "=" in msg and len(msg) > 10 and msg.count("=") > 5:
            return  # Ignora linhas de separador
        elif msg.strip() == "":
            return
        else:
            label = msg.strip()
            detail = ""

        log_steps.append({"label": label, "detail": detail})
        pct = min(95, int(len(log_steps) / max(total_steps, len(log_steps) + 2) * 95))
        progress_placeholder.markdown(render_progress_html(pct), unsafe_allow_html=True)
        log_placeholder.markdown(render_log_html(log_steps, is_done=False), unsafe_allow_html=True)

    # Status inicial
    status_placeholder.markdown(
        f'<div class="status-running">{SPIN_SVG} <span>Processando...</span></div>',
        unsafe_allow_html=True,
    )
    progress_placeholder.markdown(render_progress_html(0), unsafe_allow_html=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        # ── FASE 1 ─────────────────────────────────
        log("Autenticando na plataforma — Estrategia Concursos")

        try:
            pdfs = executar_scraping(
                url_pacote=url_pacote,
                email=email,
                senha=senha,
                pasta_tmp=tmp_dir,
                log_fn=log,
            )
        except Exception as e:
            st.error(f"Erro no download: {e}")
            st.stop()

        metric_pdfs.metric("Arquivos", len(pdfs))
        log(f"{len(pdfs)} arquivos prontos — Para analise")

        # ── FASE 2 ─────────────────────────────────
        dados_finais = []
        total_topicos = 0

        for i, caminho in enumerate(pdfs):
            status_placeholder.markdown(
                f'<div class="status-running">{SPIN_SVG} <span>Analisando arquivo {i+1} de {len(pdfs)}...</span></div>',
                unsafe_allow_html=True,
            )
            dados_web = {
                "Disciplina_Site": os.path.basename(os.path.dirname(caminho)),
                "Nome_Arquivo_Sugerido": os.path.basename(caminho).replace(".pdf", ""),
                "Link_Aula": "",
                "Descricao_Conteudo_Site": "",
            }
            resultado = analisar_pdf(
                caminho=caminho,
                dados_web=dados_web,
                api_key=api_key,
                model_name=model_name,
                log_fn=log,
            )
            dados_finais.extend(resultado)
            total_topicos += len(resultado)
            metric_topicos.metric("Topicos", total_topicos)
            time.sleep(1)

        # ── FASE 3 ─────────────────────────────────
        log("Gerando planilha — Formatando colunas")

        output_path = os.path.join(tmp_dir, output_filename)

        df_final = gerar_planilha(
            dados_finais=dados_finais,
            arquivo_saida=output_path,
            sufixo_disciplina=sufixo,
            max_paginas=max_paginas,
        )

        total_blocos = len(df_final)
        metric_blocos.metric("Linhas", total_blocos)

        # ── FASE 4 ─────────────────────────────────
        log("Enviando para o Google Drive — Salvando arquivo")

        drive_link = ""
        try:
            drive_link = upload_excel(output_path, drive_folder, output_filename)
            log("Plano criado com sucesso! — Gerando link")
        except Exception as e:
            log(f"Upload para Drive falhou — {e}")

        # ── RESULTADO ──────────────────────────────
        progress_placeholder.markdown(render_progress_html(100), unsafe_allow_html=True)
        log_placeholder.markdown(render_log_html(log_steps, is_done=True), unsafe_allow_html=True)
        status_placeholder.markdown(render_success_html(drive_link), unsafe_allow_html=True)
        metric_status.metric("Status", "Concluido")

        with open(output_path, "rb") as f:
            excel_bytes = f.read()

    with resultado_placeholder.container():
        st.divider()
        st.markdown(f"""
        <h1 style="font-size:24px !important;">
            Resultado
        </h1>
        """, unsafe_allow_html=True)

        col_dl, col_drive = st.columns(2)
        with col_dl:
            st.download_button(
                label="Baixar planilha (.xlsx)",
                data=excel_bytes,
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_drive:
            if drive_link:
                st.link_button("Abrir no Google Drive", drive_link, use_container_width=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.dataframe(
            df_final[["Disciplina", "Assunto", "Páginas ou Minutos de Vídeo", "Referência", "Link de Estudo"]].head(20),
            use_container_width=True,
            hide_index=True,
        )
