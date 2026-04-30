import re
import unicodedata
import pandas as pd
from collections import defaultdict


COLUNAS_ALVO = [
    "Disciplina", "Assunto", "Páginas ou Minutos de Vídeo",
    "Minutos Expresso", "Minutos Regular", "Minutos Calma",
    "Dica", "Dica de Revisões", "Dica de Questões", "Referência",
    "Ordenação", "Peso de Resumos", "Peso de Revisões", "Peso de Questões",
    "Número de Questões", "Link de Estudo", "Link de Resumo",
    "Link de Questões", "Suplementar",
]

DICA_PADRAO = """🚀 PASSO A PASSO DA MISSÃO:

1. 4 a 5 respirações controladas, concentra e vamos começar!
2. Resolva 2 a 5 questões ANTES ler o PDF para ativar
3. Ao ler o PDF anote SÓ o difícil ou indicado
4. Reserve tempo para questões ao final.
5. Ao final tente lembrar do que estudou
6. Faça 10 a 20 questões. Regra: Resolva > Leia comentário > Anote > Siga.

🧠 Foco em contato e volume! A lapidação vem depois.
🔥 Registre seus acertos na plataforma!"""

DICA_REVISOES = """⚡ Missão: Revisão Ativa

🧠 Momento de organizar seus erros e anotações no material de revisão!

🎯 Passo a Passo:
• Recuperação: Passe pelos tópicos e tente lembrar do conceito antes de ler a anotação.
• Explique em voz alta para si mesmo, como se desse aula para uma criança.
• Memorização: Aproveite para alimentar seu baralho no Anki com os pontos mais difíceis.

⚠️ Alerta: O esforço de tentar lembrar sem olhar é o que fixa o saber!"""

DICA_QUESTOES = """⚡ É aqui que você aprende!

🎯 10 questões bem feitas valem mais que 50 no automático

🚀 No QConcursos:
1. Leia o enunciado e tente resolver justificando cada alternativa.
2. Leia o comentário
3. Errou? Identifique se foi falta de atenção ou teoria. Se for teoria, revise!
4. Anote no material de revisão o que aprendeu
5. Passe para a próxima Questão

🔥 Ação: Registre seu desempenho!"""


def normalizar_texto(texto: str) -> str:
    if not isinstance(texto, str):
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]", "", sem_acento).lower()


def limpar_texto(valor: str) -> str:
    if not isinstance(valor, str):
        return ""
    return re.sub(r"\s+", " ", valor).strip()


def extrair_intervalo(texto: str) -> tuple[int, int]:
    if not isinstance(texto, str):
        return 0, 0
    nums = [int(x) for x in re.findall(r"\d+", texto)]
    if len(nums) >= 2:
        return nums[0], nums[1]
    if len(nums) == 1:
        return nums[0], nums[0]
    return 0, 0


def extrair_aula(*textos) -> str:
    padroes = [
        r"(Aula\s*(?:\d+|única|unica|extra))",
        r"(AULA\s*(?:\d+|ÚNICA|UNICA|EXTRA))",
    ]
    for texto in textos:
        if not isinstance(texto, str):
            continue
        for padrao in padroes:
            match = re.search(padrao, texto, flags=re.IGNORECASE)
            if match:
                aula = re.sub(r"\s+", " ", match.group(1)).strip()
                return aula.replace("aula", "Aula").replace("AULA", "Aula")
    return "Aula"


def formatar_referencia(aula, inicio, fim, fim_total, dividida, topicos=None) -> str:
    sufixo = ""
    if dividida and topicos:
        nomes = [t for t in topicos if t][:3]
        if nomes:
            sufixo = " | " + " · ".join(nomes)

    if not dividida:
        return f"{aula} - Da Pag {inicio} até Pag {fim}"
    if fim >= fim_total:
        return f"{aula} - Da Pag {inicio} até o fim{sufixo}"
    return f"{aula} - Da Pag {inicio} até Pag {fim}{sufixo}"


def montar_blocos(df_aula: pd.DataFrame, max_paginas: int = 50) -> list[dict]:
    """Agrupa tópicos em blocos respeitando fronteiras — nunca corta tópico ao meio."""
    blocos = []
    bloco_inicio = bloco_fim = paginas = None
    topicos_bloco = []

    for _, row in df_aula.iterrows():
        inicio = int(row["Pagina_Inicial"])
        fim = int(row["Pagina_Final"])
        topico = str(row.get("Topico_Interno") or row.get("Assunto_Geral") or "").strip()

        if fim < inicio:
            continue

        pgs = (fim - inicio) + 1

        if bloco_inicio is None:
            bloco_inicio, bloco_fim, paginas = inicio, fim, pgs
            topicos_bloco = [topico] if topico else []
        elif paginas + pgs <= max_paginas:
            bloco_fim = fim
            paginas += pgs
            if topico and topico not in topicos_bloco:
                topicos_bloco.append(topico)
        else:
            blocos.append({"Pagina_Inicial": bloco_inicio, "Pagina_Final": bloco_fim, "Paginas": paginas, "Topicos": topicos_bloco})
            bloco_inicio, bloco_fim, paginas = inicio, fim, pgs
            topicos_bloco = [topico] if topico else []

    if bloco_inicio is not None:
        blocos.append({"Pagina_Inicial": bloco_inicio, "Pagina_Final": bloco_fim, "Paginas": paginas, "Topicos": topicos_bloco})

    return blocos


def gerar_planilha(
    dados_finais: list[dict],
    arquivo_saida: str,
    sufixo_disciplina: str = " - Eng. Petro. Petrobras",
    max_paginas: int = 50,
) -> pd.DataFrame:

    df = pd.DataFrame(dados_finais).copy()
    if df.empty:
        vazio = pd.DataFrame(columns=COLUNAS_ALVO)
        vazio.to_excel(arquivo_saida, index=False)
        return vazio

    for col in ["Disciplina", "Arquivo", "Nome_Arquivo_Sugerido", "Assunto_Geral",
                "Descricao_Conteudo_Site", "Topico_Interno", "Detalhe_Intervalo", "Link_Aula"]:
        if col not in df.columns:
            df[col] = ""

    def disciplina_fmt(v):
        v = limpar_texto(v)
        if not v or v == "Curso":
            v = "Disciplina"
        return v if v.endswith(sufixo_disciplina) else f"{v}{sufixo_disciplina}"

    def assunto_fmt(row):
        for col in ["Descricao_Conteudo_Site", "Nome_Arquivo_Sugerido", "Assunto_Geral", "Topico_Interno"]:
            v = limpar_texto(row.get(col, ""))
            if v:
                return re.sub(r"^Aula\s*\d+\s*-\s*", "", v, flags=re.IGNORECASE).strip()
        return "Assunto"

    df["Disciplina_Final"] = df["Disciplina"].apply(disciplina_fmt)
    df["Assunto_Final"] = df.apply(assunto_fmt, axis=1)
    df[["Pagina_Inicial", "Pagina_Final"]] = df["Detalhe_Intervalo"].apply(
        lambda x: pd.Series(extrair_intervalo(x))
    )
    df["Paginas_Calculadas"] = (df["Pagina_Final"] - df["Pagina_Inicial"] + 1).clip(lower=0)
    df["Aula_Ref"] = df.apply(
        lambda row: extrair_aula(row.get("Arquivo", ""), row.get("Nome_Arquivo_Sugerido", ""), row.get("Descricao_Conteudo_Site", "")),
        axis=1,
    )
    df["Ordem_Origem"] = range(len(df))
    df = df[df["Paginas_Calculadas"] > 0].copy()
    df.sort_values(by=["Disciplina_Final", "Arquivo", "Pagina_Inicial", "Ordem_Origem"], inplace=True)

    linhas_saida = []
    primeira_ordem = {}

    for chaves, df_aula in df.groupby(["Disciplina_Final", "Arquivo", "Aula_Ref", "Link_Aula"], sort=False):
        disciplina, arquivo, aula_ref, link_aula = chaves
        df_aula = df_aula.sort_values(by=["Pagina_Inicial", "Pagina_Final", "Ordem_Origem"]).copy()

        assunto = df_aula["Assunto_Final"].iloc[0] if len(df_aula) > 0 else "Assunto"
        blocos = montar_blocos(df_aula, max_paginas)
        if not blocos:
            continue

        inicio_grupo = int(df_aula["Ordem_Origem"].min())
        if disciplina not in primeira_ordem:
            primeira_ordem[disciplina] = inicio_grupo

        fim_total = max(int(b["Pagina_Final"]) for b in blocos)
        dividida = len(blocos) > 1

        for idx, bloco in enumerate(blocos):
            linhas_saida.append({
                "Disciplina": disciplina,
                "Assunto": assunto,
                "Páginas ou Minutos de Vídeo": int(bloco["Paginas"]),
                "Minutos Expresso": 1,
                "Minutos Regular": 2,
                "Minutos Calma": 3,
                "Dica": DICA_PADRAO,
                "Dica de Revisões": DICA_REVISOES,
                "Dica de Questões": DICA_QUESTOES,
                "Referência": formatar_referencia(
                    aula_ref, int(bloco["Pagina_Inicial"]), int(bloco["Pagina_Final"]),
                    fim_total, dividida, topicos=bloco.get("Topicos", [])
                ),
                "Ordenação": 0,
                "Peso de Resumos": 1,
                "Peso de Revisões": 1,
                "Peso de Questões": 2,
                "Número de Questões": 30,
                "Link de Estudo": limpar_texto(link_aula),
                "Link de Resumo": "",
                "Link de Questões": "",
                "Suplementar": "",
                "_ordem_disc": primeira_ordem[disciplina],
                "_ordem_arq": inicio_grupo,
                "_ordem_bloco": idx,
            })

    df_saida = pd.DataFrame(linhas_saida)
    if df_saida.empty:
        vazio = pd.DataFrame(columns=COLUNAS_ALVO)
        vazio.to_excel(arquivo_saida, index=False)
        return vazio

    df_saida.sort_values(by=["_ordem_disc", "Disciplina", "_ordem_arq", "Assunto", "_ordem_bloco"], inplace=True)

    contador = defaultdict(int)
    df_saida["Ordenação"] = [contador.__setitem__(d, contador[d] + 10) or contador[d] for d in df_saida["Disciplina"]]

    df_saida = df_saida[COLUNAS_ALVO]
    df_saida.to_excel(arquivo_saida, index=False)
    return df_saida
