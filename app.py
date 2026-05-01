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
    page_icon="https://img.icons8.com/ios/50/ffffff/document--v1.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# AUTENTICAÇÃO POR TOKEN
# ──────────────────────────────────────────────
def _checar_token():
    tokens_validos = st.secrets.get("TOKENS_VALIDOS", [])

    if st.session_state.get("autenticado"):
        return

    st.markdown("""
    <style>
        .login-card {
            max-width: 420px;
            margin: 80px auto 0 auto;
            background: #1e2535;
            border: 1px solid #2d3748;
            border-radius: 16px;
            padding: 40px 36px;
        }
        .login-title {
            font-size: 22px;
            font-weight: 700;
            color: #e2e8f0;
            margin-bottom: 6px;
        }
        .login-sub {
            font-size: 14px;
            color: #718096;
            margin-bottom: 28px;
        }
    </style>
    <div class="login-card">
        <div class="login-title">Auto Plan</div>
        <div class="login-sub">Acesso restrito. Insira seu token para continuar.</div>
    </div>
    """, unsafe_allow_html=True)

    token_input = st.text_input("Token de acesso", type="password", placeholder="••••••••", label_visibility="collapsed")
    entrar = st.button("Entrar", type="primary", use_container_width=True)

    if entrar:
        if token_input in tokens_validos:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Token inválido. Contate o administrador.")

    st.stop()


_checar_token()

# ──────────────────────────────────────────────
# CSS CUSTOMIZADO
# ──────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #161b27; border-right: 1px solid #2d3748; }

    /* Cards de métricas */
    div[data-testid="metric-container"] {
        background: #1e2535;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px;
    }
    div[data-testid="metric-container"] label { color: #718096 !important; font-size: 12px; text-transform: uppercase; letter-spacing: .05em; }
    div[data-testid="metric-container"] [data-testid="metric-value"] { color: #e2e8f0 !important; font-size: 24px; font-weight: 700; }

    /* Botão principal */
    div.stButton > button[kind="primary"] {
        background: #4f46e5;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 11px 28px;
        font-size: 14px;
        font-weight: 600;
        width: 100%;
        letter-spacing: .02em;
        transition: background 0.2s;
    }
    div.stButton > button[kind="primary"]:hover { background: #4338ca; }

    /* Log box */
    .log-box {
        background: #0d1117;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 16px 20px;
        font-family: 'Menlo', 'Courier New', monospace;
        font-size: 12px;
        color: #8b949e;
        height: 300px;
        overflow-y: auto;
        white-space: pre-wrap;
        line-height: 1.6;
    }

    /* Títulos */
    h1 { color: #e2e8f0 !important; font-weight: 700 !important; font-size: 24px !important; }
    h3 { color: #718096 !important; font-size: 13px !important; font-weight: 600 !important;
         text-transform: uppercase; letter-spacing: .08em; }

    /* Sidebar labels */
    .sidebar-label {
        font-size: 11px;
        font-weight: 600;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: .08em;
        margin-bottom: 6px;
    }

    /* Badge */
    .badge {
        display: inline-block;
        background: #1e2535;
        border: 1px solid #2d3748;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 12px;
        color: #718096;
        font-weight: 500;
    }

    /* Divider */
    hr { border-color: #2d3748 !important; }

    /* Inputs */
    input, textarea, select { background: #1e2535 !important; color: #e2e8f0 !important; border-color: #2d3748 !important; }

    /* Status banners */
    .status-running {
        background: #1e2535;
        border: 1px solid #4f46e5;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 13px;
        color: #a5b4fc;
        font-weight: 500;
    }
    .status-done {
        background: #0d2b1e;
        border: 1px solid #166534;
        border-radius: 8px;
        padding: 10px 16px;
        font-size: 13px;
        color: #4ade80;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="display:flex;align-items:center;gap:10px;padding:8px 0 16px 0;">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#4f46e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
        </svg>
        <span style="font-size:17px;font-weight:700;color:#e2e8f0;">Auto Plan</span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown('<div class="sidebar-label">Curso</div>', unsafe_allow_html=True)
    url_pacote = st.text_input(
        "URL do Pacote",
        placeholder="https://www.estrategiaconcursos.com.br/app/dashboard/pacote/...",
        label_visibility="collapsed",
    )

    st.markdown('<div class="sidebar-label" style="margin-top:16px;">Google Drive</div>', unsafe_allow_html=True)
    drive_folder = st.text_input("Pasta de destino", value="Auto Plan", label_visibility="collapsed")
    output_filename = st.text_input("Nome do arquivo", value="plano_estudos.xlsx", label_visibility="collapsed")

    st.divider()

    with st.expander("Configurações avançadas"):
        max_paginas = st.slider("Máx. páginas por bloco", 20, 100, 50)
        sufixo = st.text_input("Sufixo das disciplinas", value=" - Eng. Petro. Petrobras")
        model_name = st.selectbox(
            "Modelo de análise",
            ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"],
            label_visibility="collapsed",
        )

    st.divider()
    st.markdown('<div class="badge">Credenciais protegidas</div>', unsafe_allow_html=True)

# ──────────────────────────────────────────────
# CABEÇALHO
# ──────────────────────────────────────────────
col_title, col_badge = st.columns([5, 1])
with col_title:
    st.markdown("""
    <div style="padding: 8px 0 4px 0;">
        <div style="font-size:26px;font-weight:700;color:#e2e8f0;">Auto Plan</div>
        <div style="font-size:14px;color:#718096;margin-top:4px;">Geração automatizada de planos de estudo a partir de cursos online.</div>
    </div>
    """, unsafe_allow_html=True)
with col_badge:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="badge" style="float:right;">por Thiago Paiva</div>', unsafe_allow_html=True)

st.divider()

# ──────────────────────────────────────────────
# ÁREA PRINCIPAL
# ──────────────────────────────────────────────
col_btn, col_status = st.columns([1, 3])

with col_btn:
    iniciar = st.button("Gerar Plano", type="primary", disabled=not url_pacote)

with col_status:
    status_placeholder = st.empty()

# Métricas
m1, m2, m3, m4 = st.columns(4)
metric_pdfs    = m1.empty()
metric_topicos = m2.empty()
metric_blocos  = m3.empty()
metric_status  = m4.empty()

# Log
st.markdown("### Log de execução")
log_placeholder = st.empty()

# Resultado
resultado_placeholder = st.empty()

# ──────────────────────────────────────────────
# EXECUÇÃO
# ──────────────────────────────────────────────
if iniciar:
    try:
        email   = st.secrets["SEU_EMAIL"]
        senha   = st.secrets["SUA_SENHA"]
        api_key = st.secrets["GOOGLE_API_KEY"]
    except KeyError as e:
        st.error(f"Configuração ausente: {e}. Verifique as variáveis de ambiente.")
        st.stop()

    log_lines = []

    def log(msg: str):
        log_lines.append(msg)
        log_placeholder.markdown(
            '<div class="log-box">' + "<br>".join(log_lines[-40:]) + "</div>",
            unsafe_allow_html=True,
        )

    status_placeholder.markdown('<div class="status-running">Processando...</div>', unsafe_allow_html=True)
    metric_status.metric("Status", "Em andamento")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # ── FASE 1 ────────────────────────────────────────
        log("=" * 50)
        log("FASE 1 — Autenticação e download de materiais")
        log("=" * 50)

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

        metric_pdfs.metric("Arquivos baixados", len(pdfs))
        log(f"\n{len(pdfs)} arquivos prontos para análise")

        # ── FASE 2 ────────────────────────────────────────
        log("\n" + "=" * 50)
        log("FASE 2 — Análise de conteúdo")
        log("=" * 50)

        dados_finais = []
        total_topicos = 0

        for i, caminho in enumerate(pdfs):
            status_placeholder.markdown(
                f'<div class="status-running">Analisando arquivo {i+1} de {len(pdfs)}...</div>',
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
            metric_topicos.metric("Tópicos identificados", total_topicos)
            time.sleep(1)

        # ── FASE 3 ────────────────────────────────────────
        log("\n" + "=" * 50)
        log("FASE 3 — Gerando planilha")
        log("=" * 50)

        output_path = os.path.join(tmp_dir, output_filename)

        df_final = gerar_planilha(
            dados_finais=dados_finais,
            arquivo_saida=output_path,
            sufixo_disciplina=sufixo,
            max_paginas=max_paginas,
        )

        total_blocos = len(df_final)
        metric_blocos.metric("Linhas geradas", total_blocos)
        log(f"Planilha gerada: {total_blocos} linhas")

        # ── FASE 4 ────────────────────────────────────────
        log("\n" + "=" * 50)
        log("FASE 4 — Enviando para o Google Drive")
        log("=" * 50)

        drive_link = ""
        try:
            drive_link = upload_excel(output_path, drive_folder, output_filename)
            log("Arquivo salvo no Drive")
        except Exception as e:
            log(f"Aviso: Upload para Drive falhou — {e}")

        # ── RESULTADO ─────────────────────────────────────
        status_placeholder.markdown('<div class="status-done">Concluído com sucesso</div>', unsafe_allow_html=True)
        metric_status.metric("Status", "Concluído")

        log("\nProcesso finalizado.")

        with open(output_path, "rb") as f:
            excel_bytes = f.read()

    with resultado_placeholder.container():
        st.divider()
        st.markdown("### Resultado")

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

        st.markdown("### Preview")
        st.dataframe(
            df_final[["Disciplina", "Assunto", "Páginas ou Minutos de Vídeo", "Referência", "Link de Estudo"]].head(20),
            use_container_width=True,
            hide_index=True,
        )
