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
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# AUTENTICAÇÃO POR TOKEN
# ──────────────────────────────────────────────
def _checar_token():
    tokens_validos = st.secrets.get("TOKENS_VALIDOS", [])

    if st.session_state.get("autenticado"):
        return  # já passou pela verificação nesta sessão

    st.markdown("## 🔐 Auto Plan — Acesso Restrito")
    st.markdown("Insira seu token de acesso para continuar.")
    token_input = st.text_input("Token de acesso", type="password", placeholder="••••••••")
    entrar = st.button("Entrar", type="primary")

    if entrar:
        if token_input in tokens_validos:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("❌ Token inválido. Contate o administrador.")

    st.stop()


_checar_token()

# ──────────────────────────────────────────────
# CSS CUSTOMIZADO
# ──────────────────────────────────────────────
st.markdown("""
<style>
    /* Fundo e fonte geral */
    .stApp { background-color: #0f1117; }
    section[data-testid="stSidebar"] { background-color: #161b27; }

    /* Cards de métricas */
    div[data-testid="metric-container"] {
        background: #1e2535;
        border: 1px solid #2d3748;
        border-radius: 12px;
        padding: 16px;
    }

    /* Botão principal */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 12px 28px;
        font-size: 16px;
        font-weight: 600;
        width: 100%;
        transition: opacity 0.2s;
    }
    div.stButton > button[kind="primary"]:hover { opacity: 0.88; }

    /* Log box */
    .log-box {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        color: #c9d1d9;
        height: 320px;
        overflow-y: auto;
        white-space: pre-wrap;
    }

    /* Título */
    h1 { color: #e2e8f0 !important; }
    h3 { color: #a0aec0 !important; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# SIDEBAR — CONFIGURAÇÕES
# ──────────────────────────────────────────────
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/books.png", width=64)
    st.title("Auto Plan")
    st.caption("Gerador de Planos de Estudo com IA")
    st.divider()

    st.subheader("📌 Curso")
    url_pacote = st.text_input(
        "URL do Pacote",
        placeholder="https://www.estrategiaconcursos.com.br/app/dashboard/pacote/...",
    )

    st.subheader("☁️ Google Drive")
    drive_folder = st.text_input("Pasta de destino no Drive", value="Auto Plan")
    output_filename = st.text_input("Nome do arquivo", value="plano_estudos.xlsx")

    st.divider()
    with st.expander("⚙️ Parâmetros avançados"):
        max_paginas = st.slider("Máx. páginas por bloco", 20, 100, 50)
        sufixo = st.text_input("Sufixo das disciplinas", value=" - Eng. Petro. Petrobras")
        model_name = st.selectbox(
            "Modelo Gemini",
            ["models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"],
        )

    st.divider()
    st.caption("🔒 Credenciais gerenciadas via Streamlit Secrets")

# ──────────────────────────────────────────────
# CABEÇALHO
# ──────────────────────────────────────────────
col_title, col_badge = st.columns([4, 1])
with col_title:
    st.title("📚 Auto Plan Generator")
    st.markdown("Gere planos de estudo completos a partir dos seus cursos no Estratégia Concursos.")
with col_badge:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**Powered by** `Gemini AI`")

st.divider()

# ──────────────────────────────────────────────
# ÁREA PRINCIPAL
# ──────────────────────────────────────────────
col_btn, col_status = st.columns([1, 3])

with col_btn:
    iniciar = st.button("🚀 Gerar Plano", type="primary", disabled=not url_pacote)

with col_status:
    status_placeholder = st.empty()

# Métricas
m1, m2, m3, m4 = st.columns(4)
metric_pdfs     = m1.empty()
metric_topicos  = m2.empty()
metric_blocos   = m3.empty()
metric_status   = m4.empty()

# Log
st.markdown("### 📋 Log de execução")
log_placeholder = st.empty()

# Resultado
resultado_placeholder = st.empty()

# ──────────────────────────────────────────────
# EXECUÇÃO
# ──────────────────────────────────────────────
if iniciar:
    # Valida secrets
    try:
        email  = st.secrets["SEU_EMAIL"]
        senha  = st.secrets["SUA_SENHA"]
        api_key = st.secrets["GOOGLE_API_KEY"]
    except KeyError as e:
        st.error(f"❌ Secret não encontrado: {e}. Verifique as configurações no Streamlit Cloud.")
        st.stop()

    log_lines = []

    def log(msg: str):
        log_lines.append(msg)
        log_placeholder.markdown(
            f'<div class="log-box">' + "<br>".join(log_lines[-40:]) + "</div>",
            unsafe_allow_html=True,
        )

    status_placeholder.info("⏳ Iniciando processamento...")
    metric_status.metric("Status", "🔄 Rodando")

    with tempfile.TemporaryDirectory() as tmp_dir:
        # ── FASE 1: Scraping ──────────────────────────────
        log("=" * 50)
        log("FASE 1 — Login e download de PDFs")
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
            st.error(f"❌ Erro no scraping: {e}")
            st.stop()

        metric_pdfs.metric("PDFs baixados", len(pdfs))
        log(f"\n✅ {len(pdfs)} PDFs prontos para análise")

        # ── FASE 2: Análise com Gemini ────────────────────
        log("\n" + "=" * 50)
        log("FASE 2 — Análise de PDFs com Gemini")
        log("=" * 50)

        # Monta índice web simplificado a partir dos nomes dos PDFs
        dados_finais = []
        total_topicos = 0

        for i, caminho in enumerate(pdfs):
            status_placeholder.info(f"⏳ Analisando PDF {i+1}/{len(pdfs)}...")
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
            metric_topicos.metric("Tópicos extraídos", total_topicos)
            time.sleep(1)  # respeita rate limit

        # ── FASE 3: Gerar planilha ────────────────────────
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
        log(f"✅ Planilha gerada: {total_blocos} linhas")

        # ── FASE 4: Upload Drive ──────────────────────────
        log("\n" + "=" * 50)
        log("FASE 4 — Enviando para o Google Drive")
        log("=" * 50)

        drive_link = ""
        try:
            drive_link = upload_excel(output_path, drive_folder, output_filename)
            log(f"✅ Arquivo salvo no Drive")
        except Exception as e:
            log(f"⚠️ Upload para Drive falhou: {e}")

        # ── RESULTADO ─────────────────────────────────────
        status_placeholder.success("✅ Concluído com sucesso!")
        metric_status.metric("Status", "✅ Pronto")

        log("\n🏁 Processo finalizado!")

        with open(output_path, "rb") as f:
            excel_bytes = f.read()

    # Exibe resultado fora do tempdir (já lemos os bytes)
    with resultado_placeholder.container():
        st.divider()
        st.markdown("### 🎉 Resultado")

        col_dl, col_drive = st.columns(2)
        with col_dl:
            st.download_button(
                label="⬇️ Baixar Planilha (.xlsx)",
                data=excel_bytes,
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with col_drive:
            if drive_link:
                st.link_button("☁️ Abrir no Google Drive", drive_link, use_container_width=True)

        st.markdown("### 👁️ Preview")
        st.dataframe(
            df_final[["Disciplina", "Assunto", "Páginas ou Minutos de Vídeo", "Referência", "Link de Estudo"]].head(20),
            use_container_width=True,
            hide_index=True,
        )
