import json
import pathlib
import re
import time
import unicodedata

PALAVRAS_IGNORADAS = [
    "questões comentadas", "questoes comentadas",
    "lista de questões", "lista de questoes",
    "questões", "questoes", "gabarito", "resumo", "simulado",
]


def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]", "", sem_acento).lower()


def deve_ignorar(texto: str) -> bool:
    norm = normalizar_texto(texto)
    return any(normalizar_texto(t) in norm for t in PALAVRAS_IGNORADAS)


def limpar_nome_topico(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    return re.sub(r"^\d+[\)\.\-\s]+\s*", "", texto).strip()


def ajustar_topicos(lista: list) -> list:
    lista = sorted(lista, key=lambda x: (int(x.get("Pagina_Inicial", 0) or 0),))
    saida, ultimo_fim = [], 0

    for item in lista:
        topico = item.get("Topico_Interno", "") or ""
        try:
            p_ini = int(item.get("Pagina_Inicial", 0) or 0)
        except Exception:
            p_ini = 0
        try:
            p_fim = int(item.get("Pagina_Final", 0) or 0)
        except Exception:
            p_fim = 0

        if deve_ignorar(topico):
            if saida and p_ini > 0:
                saida[-1]["Pagina_Final"] = min(saida[-1]["Pagina_Final"], p_ini - 1)
                ultimo_fim = saida[-1]["Pagina_Final"]
            continue

        if ultimo_fim > 0 and p_ini <= ultimo_fim:
            p_ini = ultimo_fim + 1
        if p_fim < p_ini:
            continue

        saida.append({
            "Topico_Interno": topico,
            "Pagina_Inicial": p_ini,
            "Pagina_Final": p_fim,
            "Complexidade": item.get("Complexidade", "Média"),
            "Tempo_Estimado": item.get("Tempo_Estimado", "10 min"),
        })
        ultimo_fim = p_fim

    return saida


PROMPT = """
Analise APENAS o sumário e considere SOMENTE conteúdo teórico.

OBJETIVO: Mapear os tópicos teóricos e seus intervalos de páginas.

REGRAS:
1. Ignore itens como: Resumo, Questões, Questões Comentadas, Lista de Questões, Gabarito, Simulado.
2. O intervalo dos tópicos teóricos deve terminar antes desses blocos.
3. Retorne apenas conteúdo teórico.

SAÍDA JSON:
[
    {
        "Topico_Interno": "Nome Limpo",
        "Pagina_Inicial": 5,
        "Pagina_Final": 11,
        "Complexidade": "Média",
        "Tempo_Estimado": "20 min"
    }
]
"""


def analisar_pdf(
    caminho: str,
    dados_web: dict,
    api_key: str,
    model_name: str = "models/gemini-2.5-flash",
    log_fn=None,
) -> list[dict]:
    def log(msg):
        if log_fn:
            log_fn(msg)

    import os
    nome_arq = os.path.basename(caminho)
    # Usa o caminho COMPLETO como chave única para evitar que PDFs de pastas
    # diferentes (disciplinas distintas) com o mesmo nome sejam mesclados no groupby
    caminho_completo = os.path.abspath(caminho)

    if not dados_web:
        dados_web = {"Disciplina_Site": "Indefinida", "Nome_Arquivo_Sugerido": nome_arq, "Link_Aula": "", "Descricao_Conteudo_Site": ""}

    if deve_ignorar(nome_arq) or deve_ignorar(dados_web.get("Descricao_Conteudo_Site", "")):
        log(f"⏭️ Ignorado (conteúdo não teórico): {nome_arq[:55]}")
        return []

    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    try:
        pdf_bytes = pathlib.Path(caminho).read_bytes()
    except Exception as e:
        log(f"❌ Erro lendo arquivo: {e}")
        return []

    pdf_blob = {"mime_type": "application/pdf", "data": pdf_bytes}

    for tentativa in range(4):
        try:
            response = model.generate_content([PROMPT, pdf_blob])
            if not response.text:
                continue

            texto = response.text.replace("```json", "").replace("```", "").strip()
            try:
                lista = json.loads(texto)
            except Exception:
                start, end = texto.find("["), texto.rfind("]") + 1
                if start != -1 and end > start:
                    lista = json.loads(texto[start:end])
                else:
                    continue

            if isinstance(lista, dict):
                lista = [lista]

            lista = ajustar_topicos(lista)
            saida = []

            for item in lista:
                try:
                    p_ini = int(item.get("Pagina_Inicial", 0))
                    p_fim = int(item.get("Pagina_Final", 0))
                except Exception:
                    continue

                if p_fim < p_ini:
                    continue

                topico = limpar_nome_topico(item.get("Topico_Interno", "Geral"))
                if deve_ignorar(topico):
                    continue

                saida.append({
                    "Disciplina": dados_web.get("Disciplina_Site", "Indefinida"),
                    "Arquivo": caminho_completo,   # caminho completo = chave única por PDF
                    "Nome_Arquivo": nome_arq,       # nome curto para exibição
                    "Nome_Arquivo_Sugerido": dados_web.get("Nome_Arquivo_Sugerido", nome_arq),
                    "Assunto_Geral": topico,
                    "Descricao_Conteudo_Site": dados_web.get("Descricao_Conteudo_Site", ""),
                    "Topico_Interno": topico,
                    "Pgs_Teoria": (p_fim - p_ini) + 1,
                    "Detalhe_Intervalo": f"Começou na página {p_ini} e terminou na página {p_fim}",
                    "Complexidade": item.get("Complexidade", "Média"),
                    "Tempo_Estimado": item.get("Tempo_Estimado", "10 min"),
                    "Link_Aula": dados_web.get("Link_Aula", ""),
                })

            if saida:
                log(f"✅ {nome_arq[:45]} → {len(saida)} tópicos")
                return saida

        except Exception as e:
            erro = str(e)
            if "429" in erro:
                log("⏳ Quota atingida, aguardando 30s...")
                time.sleep(30)
            elif "503" in erro or "500" in erro:
                espera = 20 * (tentativa + 1)
                log(f"⏳ Serviço indisponível, aguardando {espera}s...")
                time.sleep(espera)
            else:
                log(f"⚠️ Tentativa {tentativa+1} falhou: {e}")
                time.sleep(5)

    log(f"❌ Falha permanente: {nome_arq[:55]}")
    return []
