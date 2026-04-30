import os
import re
import glob
import time
import shutil
import requests
import streamlit as st
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).strip()[:140]


def iniciar_driver(download_dir: str):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-popup-blocking")
    options.add_argument(f"user-agent={USER_AGENT}")

    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True,
    }
    options.add_experimental_option("prefs", prefs)

    # Detecta ambiente: Streamlit Cloud usa Chromium do sistema
    # Em local, usa webdriver-manager como fallback
    CHROMIUM_PATHS = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    CHROMEDRIVER_PATHS = [
        "/usr/bin/chromedriver",
        "/usr/lib/chromium/chromedriver",
        "/usr/lib/chromium-browser/chromedriver",
    ]

    chromium_bin = next((p for p in CHROMIUM_PATHS if os.path.exists(p)), None)
    chromedriver_bin = next((p for p in CHROMEDRIVER_PATHS if os.path.exists(p)), None)

    if chromium_bin and chromedriver_bin:
        # Streamlit Cloud: usa binários do sistema
        options.binary_location = chromium_bin
        service = Service(chromedriver_bin)
    else:
        # Local: usa webdriver-manager
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())

    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(120)
    driver.execute_cdp_cmd(
        "Page.setDownloadBehavior",
        {"behavior": "allow", "downloadPath": download_dir},
    )
    return driver


def limpar_popups(driver):
    try:
        driver.execute_script("""
            document.querySelectorAll(
                '.modal,.modal-backdrop,.fade.in,[class*="overlay"],[class*="popup"],iframe,#intercom-container'
            ).forEach(e => e.remove());
            document.body.style.overflow = 'auto';
        """)
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass
    except Exception:
        pass


def scroll_pagina(driver, max_scrolls=8, pausa=1.5):
    last = driver.execute_script("return document.body.scrollHeight")
    for _ in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pausa)
        new = driver.execute_script("return document.body.scrollHeight")
        if new == last:
            break
        last = new


def realizar_login(driver, email: str, senha: str, url_login: str):
    driver.get(url_login)
    time.sleep(5)
    limpar_popups(driver)

    if "dashboard" in driver.current_url.lower():
        return

    email_el = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='email' or @name='email']"))
    )
    email_el.clear()
    email_el.send_keys(email)

    senha_el = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.XPATH, "//input[@type='password' or @name='password']"))
    )
    senha_el.clear()
    senha_el.send_keys(senha)

    btn = None
    for by, sel in [
        (By.XPATH, "//button[@type='submit']"),
        (By.XPATH, "//button[contains(.,'Entrar') or contains(.,'Continuar')]"),
    ]:
        els = driver.find_elements(by, sel)
        if els:
            btn = els[0]
            break

    if btn:
        driver.execute_script("arguments[0].click();", btn)
    else:
        senha_el.send_keys(Keys.ENTER)

    WebDriverWait(driver, 30).until(
        lambda d: "login" not in d.current_url.lower()
        or not d.find_elements(By.XPATH, "//input[@type='password']")
    )
    time.sleep(4)
    limpar_popups(driver)


def listar_disciplinas(driver, url_pacote: str) -> list[dict]:
    driver.get(url_pacote)
    time.sleep(5)
    limpar_popups(driver)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "containerCursos"))
        )
    except Exception:
        pass

    scroll_pagina(driver, max_scrolls=5)

    links = driver.find_elements(By.XPATH, "//div[contains(@class,'containerCursos')]//a[@href]")
    disciplinas, vistos = [], set()

    for link in links:
        try:
            url = (link.get_attribute("href") or "").strip()
            if not url or url in vistos:
                continue
            try:
                nome = link.find_element(By.XPATH, ".//div[contains(@class,'boxCurso')]//p").text.strip()
            except Exception:
                nome = (link.text or "").strip()
            if not nome:
                continue
            vistos.add(url)
            disciplinas.append({"nome": limpar_nome(nome), "url": url})
        except Exception:
            pass

    return disciplinas


def esperar_download(pasta: str, antes: set, timeout: int = 25) -> str | None:
    limite = time.time() + timeout
    while time.time() < limite:
        atuais = {p for p in glob.glob(os.path.join(pasta, "*")) if os.path.isfile(p)}
        novos = [p for p in (atuais - antes) if not p.endswith(".crdownload")]
        if novos:
            novos.sort(key=os.path.getmtime, reverse=True)
            cand = novos[0]
            if os.path.getsize(cand) > 1024:
                return cand
        time.sleep(1)
    return None


def baixar_pdf_requests(url: str, destino: str, driver) -> tuple[bool, str]:
    try:
        session = requests.Session()
        session.headers.update({"User-Agent": USER_AGENT})
        for c in driver.get_cookies():
            try:
                session.cookies.set(c["name"], c["value"])
            except Exception:
                pass

        with session.get(url, stream=True, timeout=(30, 120)) as r:
            if r.status_code != 200:
                return False, f"HTTP {r.status_code}"
            ct = r.headers.get("content-type", "").lower()
            if "pdf" not in ct and not r.content[:4].hex().startswith("25504446"):
                return False, "não é PDF"
            tmp = destino + ".part"
            total = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(262144):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            if total < 1024:
                os.remove(tmp)
                return False, "arquivo muito pequeno"
            os.replace(tmp, destino)
            return True, f"{round(total/1024,1)} KB"
    except Exception as e:
        return False, str(e)


def encontrar_link_pdf(aula_el):
    for el in aula_el.find_elements(By.XPATH, ".//a[@href]"):
        href = (el.get_attribute("href") or "").lower()
        texto = " ".join(filter(None, [el.text, el.get_attribute("title"), el.get_attribute("aria-label")])).lower()
        if "simplificado" in texto:
            continue
        if any(x in href for x in ["download", ".pdf", "/pdf", "material"]):
            return el
    for el in aula_el.find_elements(By.XPATH, ".//a | .//button"):
        texto = " ".join(filter(None, [el.text, el.get_attribute("title"), el.get_attribute("aria-label")])).lower()
        if "simplificado" in texto:
            continue
        if any(x in texto for x in ["baixar", "pdf", "download", "apostila", "material"]):
            return el
    return None


def baixar_pdfs_disciplina(
    driver, url_disciplina: str, pasta_tmp: str, log_fn=None
) -> list[str]:
    """Retorna lista de caminhos dos PDFs baixados."""
    def log(msg):
        if log_fn:
            log_fn(msg)

    driver.get(url_disciplina)
    time.sleep(4)
    limpar_popups(driver)

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "LessonList-item"))
        )
    except Exception:
        pass

    scroll_pagina(driver, max_scrolls=8)
    aulas = driver.find_elements(By.CLASS_NAME, "LessonList-item")
    pdfs_baixados = []

    for i in range(len(aulas)):
        try:
            aulas = driver.find_elements(By.CLASS_NAME, "LessonList-item")
            if i >= len(aulas):
                break
            aula = aulas[i]

            try:
                titulo = aula.find_element(By.CLASS_NAME, "SectionTitle").text.strip()
            except Exception:
                titulo = f"Aula_{i:02d}"

            subtitulo = ""
            try:
                subtitulo = aula.find_element(
                    By.XPATH, ".//div[contains(@class,'LessonCollapseHeader-title')]/p"
                ).text.strip()
            except Exception:
                pass

            nome_base = f"{i:02d}_{titulo} - {subtitulo}" if subtitulo else f"{i:02d}_{titulo}"
            nome_arquivo = f"{limpar_nome(nome_base)}.pdf"
            destino = os.path.join(pasta_tmp, nome_arquivo)

            if os.path.exists(destino) and os.path.getsize(destino) > 1024:
                log(f"⏭️ Já existe: {nome_arquivo[:55]}")
                pdfs_baixados.append(destino)
                continue

            link_el = encontrar_link_pdf(aula)
            if link_el is None:
                try:
                    btn = aula.find_element(By.CLASS_NAME, "Collapse-header")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    aulas = driver.find_elements(By.CLASS_NAME, "LessonList-item")
                    aula = aulas[i]
                    link_el = encontrar_link_pdf(aula)
                except Exception:
                    pass

            if link_el is None:
                log(f"⚠️ PDF não encontrado: {titulo[:55]}")
                continue

            href = (link_el.get_attribute("href") or "").strip()
            log(f"⬇️ Baixando: {nome_arquivo[:55]}")

            antes = {p for p in glob.glob(os.path.join(pasta_tmp, "*")) if os.path.isfile(p)}

            if href.startswith("http"):
                ok, msg = baixar_pdf_requests(href, destino, driver)
                if ok:
                    log(f"✅ {nome_arquivo[:45]} ({msg})")
                    pdfs_baixados.append(destino)
                    continue

            driver.execute_script("arguments[0].click();", link_el)
            baixado = esperar_download(pasta_tmp, antes)
            if baixado:
                if not baixado.lower().endswith(".pdf"):
                    novo = baixado + ".pdf"
                    os.rename(baixado, novo)
                    baixado = novo
                shutil.move(baixado, destino)
                log(f"✅ {nome_arquivo[:45]}")
                pdfs_baixados.append(destino)
            else:
                log(f"❌ Falha: {nome_arquivo[:45]}")

        except Exception as e:
            log(f"❌ Erro na aula {i:02d}: {e}")

    return pdfs_baixados


def executar_scraping(
    url_pacote: str,
    email: str,
    senha: str,
    pasta_tmp: str,
    log_fn=None,
) -> list[str]:
    """Executa login + scraping completo. Retorna lista de PDFs baixados."""

    URL_LOGIN = (
        "https://perfil.estrategia.com/login?source=legado-polvo"
        "&target=https%3A%2F%2Fwww.estrategiaconcursos.com.br%2Faccounts%2Flogin%2F%3F"
    )

    def log(msg):
        if log_fn:
            log_fn(msg)

    os.makedirs(pasta_tmp, exist_ok=True)
    driver = iniciar_driver(pasta_tmp)
    todos_pdfs = []

    try:
        log("🔐 Fazendo login...")
        realizar_login(driver, email, senha, URL_LOGIN)
        log("✅ Login efetuado")

        log("📋 Listando disciplinas...")
        disciplinas = listar_disciplinas(driver, url_pacote)
        log(f"✅ {len(disciplinas)} disciplinas encontradas")

        for idx, disc in enumerate(disciplinas):
            log(f"\n📚 [{idx+1}/{len(disciplinas)}] {disc['nome']}")
            pasta_disc = os.path.join(pasta_tmp, disc["nome"])
            os.makedirs(pasta_disc, exist_ok=True)
            pdfs = baixar_pdfs_disciplina(driver, disc["url"], pasta_disc, log_fn=log)
            todos_pdfs.extend(pdfs)

    finally:
        driver.quit()

    return todos_pdfs
