"""
Scraper de eventos - Ciudad de Panamá
======================================
Recolecta eventos de fuentes ESTÁTICAS (HTML plano) y DINÁMICAS (renderizadas
con JS) para identificar oportunidades de activación de marca.

Fuentes:
  Estáticas -> requests + BeautifulSoup
    - micultura.gob.pa/agenda-cultural-2   (Ministerio de Cultura)
    - calendariodepanama.com/eventos

  Dinámicas -> Playwright (render de JS)
    - eventbrite.es/d/panama/events
    - planpty.com/eventos

Salida: eventos_panama.csv y eventos_panama.json
Cada registro: nombre, fecha, lugar, categoria, organizador/contacto,
email, telefono, url, fuente, tipo_fuente

NOTA: Los selectores CSS están basados en la estructura de cada sitio al
momento de escribir este script. Si un sitio rediseña su HTML, ajusta los
selectores marcados con "# SELECTOR:".
"""

import csv
import json
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin

import dateparser
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36"
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(\+?507[\s.-]?)?\(?\d{3,4}\)?[\s.-]?\d{4}")
HORIZONTE_MESES = 4


@dataclass
class Evento:
    nombre: str
    fecha: str = ""
    lugar: str = ""
    categoria: str = ""
    organizador: str = ""
    email: str = ""
    telefono: str = ""
    url: str = ""
    fuente: str = ""
    tipo_fuente: str = ""  # "estatica" | "dinamica"
    segmento: str = ""
    encaje_sanchito: str = ""
    ciudad_provincia: str = "Ciudad de Panama"
    nivel_confianza: str = "media"


def extraer_contacto(texto: str) -> tuple[str, str]:
    """Busca email y teléfono en un bloque de texto libre."""
    email = EMAIL_RE.search(texto)
    telefono = PHONE_RE.search(texto)
    return (email.group(0) if email else "", telefono.group(0).strip() if telefono else "")


MESES = {
    "ene": 1, "enero": 1, "jan": 1, "january": 1,
    "feb": 2, "febrero": 2, "february": 2,
    "mar": 3, "marzo": 3, "march": 3,
    "abr": 4, "abril": 4, "apr": 4, "april": 4,
    "may": 5, "mayo": 5,
    "jun": 6, "junio": 6, "june": 6,
    "jul": 7, "julio": 7, "july": 7,
    "ago": 8, "agosto": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "septiembre": 9, "september": 9,
    "oct": 10, "octubre": 10, "october": 10,
    "nov": 11, "noviembre": 11, "november": 11,
    "dic": 12, "diciembre": 12, "dec": 12, "december": 12,
}
FECHA_CORTA_RE = re.compile(
    r"\b(" + "|".join(MESES) + r")\s*[-/]?\s*(\d{1,2})"
    r"(?:\s*[,/-]?\s*(20\d{2}))?\b",
    re.IGNORECASE,
)
FECHA_NUMERICA_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")
FECHA_DIA_MES_RE = re.compile(
    r"\b(\d{1,2})\s+(" + "|".join(MESES) + r")\b", re.IGNORECASE
)


def extraer_fecha_desde_texto(texto: str, hoy: date | None = None) -> str:
    """Extrae fechas compactas como 'DIC 3' o '10 Sep' de una tarjeta."""
    inicio = hoy or date.today()
    numerica = FECHA_NUMERICA_RE.search(texto)
    if numerica:
        dia, mes, anio = map(int, numerica.groups())
        anio += 2000 if anio < 100 else 0
    else:
        coincidencia = FECHA_CORTA_RE.search(texto)
        invertida = FECHA_DIA_MES_RE.search(texto)
        if coincidencia:
            mes = MESES[coincidencia.group(1).lower()]
            dia = int(coincidencia.group(2))
            anio = int(coincidencia.group(3) or inicio.year)
        elif invertida:
            dia = int(invertida.group(1))
            mes = MESES[invertida.group(2).lower()]
            anio = inicio.year
        else:
            return ""
    try:
        fecha = date(anio, mes, dia)
    except ValueError:
        return ""
    if not numerica and (not coincidencia or not coincidencia.group(3)) and fecha < inicio:
        fecha = date(anio + 1, mes, dia)
    return fecha.isoformat()


def clasificar_evento(evento: Evento) -> Evento:
    """Clasifica el potencial B2B/B2C del evento para Sanchito Lunch."""
    if any(red in evento.url.lower() for red in ("facebook.com", "instagram.com", "tiktok.com")):
        evento.nivel_confianza = "no_verificado"
    texto = " ".join((evento.nombre, evento.categoria, evento.organizador)).lower()
    claves_b2b = ("negocio", "networking", "foro", "convencion", "convención",
                  "proveedor", "proyecto", "corporativ", "empresarial", "summit",
                  "expo", "comercial")
    claves_b2c = ("gastronom", "festival", "oktoberfest", "recreativ", "deport",
                  "familia", "concierto", "sabores", "feria")
    es_b2b = any(clave in texto for clave in claves_b2b)
    es_b2c = any(clave in texto for clave in claves_b2c)
    if es_b2b and es_b2c:
        evento.segmento = "Mixto"
    elif es_b2b:
        evento.segmento = "B2B"
    elif es_b2c:
        evento.segmento = "B2C"
    else:
        evento.segmento = "Por revisar"
    oportunidades = []
    if es_b2b:
        oportunidades.extend(("catering", "networking", "abastecimiento corporativo"))
    if es_b2c:
        oportunidades.extend(("venta directa", "degustacion", "stand", "patrocinio"))
    evento.encaje_sanchito = ", ".join(dict.fromkeys(oportunidades))
    return evento


def fecha_en_horizonte(fecha_texto: str, hoy: date | None = None) -> bool:
    """Devuelve si una fecha cae entre hoy y los próximos cuatro meses.

    Las fechas que una fuente no publica o que no se pueden interpretar se
    conservan para revisión manual, evitando descartar oportunidades válidas.
    """
    if not fecha_texto:
        return True

    inicio = hoy or date.today()
    referencia = datetime.combine(inicio, datetime.min.time())
    fecha = dateparser.parse(
        fecha_texto,
        languages=["es", "en"],
        settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": referencia},
    )
    if not fecha:
        return True

    limite = inicio + relativedelta(months=HORIZONTE_MESES)
    return inicio <= fecha.date() <= limite


def filtrar_por_horizonte(eventos: list[Evento]) -> list[Evento]:
    """Conserva eventos dentro de la ventana operativa de cuatro meses."""
    return [evento for evento in eventos if fecha_en_horizonte(evento.fecha)]


# ---------------------------------------------------------------------------
# FUENTES ESTÁTICAS
# ---------------------------------------------------------------------------

def scrape_micultura() -> list[Evento]:
    """Ministerio de Cultura de Panamá - Agenda Cultural (HTML estático)."""
    url = "https://micultura.gob.pa/agenda-cultural-2/"
    eventos: list[Evento] = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # SELECTOR: tarjetas/artículos de evento. Ajustar si cambia el theme (WordPress).
        tarjetas = soup.select("article, .event-item, .agenda-item")
        for t in tarjetas:
            titulo_tag = t.select_one("h2, h3, .entry-title")
            fecha_tag = t.select_one(".event-date, time, .fecha")
            lugar_tag = t.select_one(".event-location, .lugar")
            link_tag = t.select_one("a[href]")
            if not titulo_tag:
                continue
            texto_completo = t.get_text(" ", strip=True)
            email, tel = extraer_contacto(texto_completo)
            eventos.append(Evento(
                nombre=titulo_tag.get_text(strip=True),
                fecha=fecha_tag.get_text(strip=True) if fecha_tag else "",
                lugar=lugar_tag.get_text(strip=True) if lugar_tag else "",
                categoria="Cultural",
                organizador="Ministerio de Cultura de Panamá",
                email=email,
                telefono=tel or "",
                url=link_tag["href"] if link_tag else url,
                fuente="micultura.gob.pa",
                tipo_fuente="estatica",
            ))
    except requests.RequestException as e:
        print(f"[!] Error en micultura.gob.pa: {e}", file=sys.stderr)
    return eventos


def scrape_calendario_panama() -> list[Evento]:
    """calendariodepanama.com/eventos (HTML estático, filtrable por ciudad)."""
    url = "https://www.calendariodepanama.com/eventos"
    eventos: list[Evento] = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # SELECTOR: cada tarjeta de evento del listado
        tarjetas = soup.select(".event-card, .evento-card, li.event, article")
        for t in tarjetas:
            titulo_tag = t.select_one("h2, h3, .event-title, .titulo")
            fecha_tag = t.select_one(".event-date, .fecha, time")
            lugar_tag = t.select_one(".event-venue, .lugar, .ubicacion")
            categoria_tag = t.select_one(".event-category, .categoria, .tag")
            link_tag = t.select_one("a[href]")
            if not titulo_tag:
                continue
            texto_completo = t.get_text(" ", strip=True)
            email, tel = extraer_contacto(texto_completo)
            eventos.append(Evento(
                nombre=titulo_tag.get_text(strip=True),
                fecha=fecha_tag.get_text(strip=True) if fecha_tag else "",
                lugar=lugar_tag.get_text(strip=True) if lugar_tag else "Ciudad de Panamá",
                categoria=categoria_tag.get_text(strip=True) if categoria_tag else "",
                organizador="",
                email=email,
                telefono=tel,
                url=link_tag["href"] if link_tag and link_tag["href"].startswith("http")
                    else f"https://www.calendariodepanama.com{link_tag['href']}" if link_tag else url,
                fuente="calendariodepanama.com",
                tipo_fuente="estatica",
            ))
    except requests.RequestException as e:
        print(f"[!] Error en calendariodepanama.com: {e}", file=sys.stderr)
    return eventos


def scrape_panama_convention_center() -> list[Evento]:
    """Calendario oficial del Panama Convention Center."""
    url = "https://panamaconventions.com/"
    eventos: list[Evento] = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tarjeta in soup.select("div.event_listing"):
            titulo_tag = tarjeta.select_one(".wpem-event-title h3")
            link_tag = tarjeta.select_one("a[href*='/event/']")
            if not titulo_tag or not link_tag:
                continue
            texto = tarjeta.get_text(" ", strip=True)
            fecha = extraer_fecha_desde_texto(texto)
            categoria = " ".join(tarjeta.get("class", []))
            eventos.append(Evento(
                nombre=titulo_tag.get_text(" ", strip=True),
                fecha=fecha,
                lugar="Panama Convention Center",
                categoria=categoria,
                organizador="Panama Convention Center",
                url=urljoin(url, link_tag["href"]),
                fuente="panamaconventions.com",
                tipo_fuente="estatica",
                nivel_confianza="alta",
            ))
    except requests.RequestException as e:
        print(f"[!] Error en panamaconventions.com: {e}", file=sys.stderr)
    return eventos


# ---------------------------------------------------------------------------
# FUENTES DINÁMICAS (requieren JS render -> Playwright)
# ---------------------------------------------------------------------------

def scrape_eventbrite_panama() -> list[Evento]:
    """Eventbrite Panamá - el listado se hidrata con JS, se requiere Playwright."""
    from playwright.sync_api import sync_playwright

    url = "https://www.eventbrite.es/d/panama/events/"
    eventos: list[Evento] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, timeout=30000)
            page.wait_for_selector("li[data-testid='event-card']", timeout=15000)
            # Scroll para forzar carga de más tarjetas (lazy loading)
            for _ in range(4):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(800)

            tarjetas = page.query_selector_all("li[data-testid='event-card']")
            for t in tarjetas:
                nombre_el = t.query_selector("h3")
                fecha_el = t.query_selector("p[data-testid='event-date']") or t.query_selector("p")
                lugar_el = t.query_selector("p.event-card__clamp-line--2")
                link_el = t.query_selector("a[href]")

                nombre = nombre_el.inner_text().strip() if nombre_el else None
                if not nombre:
                    continue
                eventos.append(Evento(
                    nombre=nombre,
                    fecha=fecha_el.inner_text().strip() if fecha_el else "",
                    lugar=lugar_el.inner_text().strip() if lugar_el else "",
                    categoria="",
                    organizador="",  # se obtiene entrando al detalle del evento (ver enriquecer_contacto_eventbrite)
                    email="",
                    telefono="",
                    url=link_el.get_attribute("href") if link_el else url,
                    fuente="eventbrite.es",
                    tipo_fuente="dinamica",
                ))
            browser.close()
    except Exception as e:
        print(f"[!] Error en Eventbrite: {e}", file=sys.stderr)
    return eventos


def enriquecer_contacto_eventbrite(eventos: list[Evento], limite: int = 15) -> None:
    """Entra al detalle de cada evento de Eventbrite para sacar el organizador
    (Eventbrite rara vez publica email/teléfono directo; casi siempre es
    'Contactar al organizador' vía su plataforma)."""
    from playwright.sync_api import sync_playwright

    objetivo = [e for e in eventos if e.fuente == "eventbrite.es"][:limite]
    if not objetivo:
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            for ev in objetivo:
                try:
                    page.goto(ev.url, timeout=20000)
                    org_el = page.query_selector("a.descriptive-organizer-info-mobile__name") \
                        or page.query_selector("[data-testid='organizer-name']")
                    if org_el:
                        ev.organizador = org_el.inner_text().strip()
                    texto = page.inner_text("body")
                    email, tel = extraer_contacto(texto)
                    ev.email, ev.telefono = email, tel
                except Exception:
                    continue
            browser.close()
    except Exception as e:
        print(f"[!] Error enriqueciendo Eventbrite: {e}", file=sys.stderr)


def scrape_planpty() -> list[Evento]:
    """PlanPTY - listado renderizado con JS."""
    from playwright.sync_api import sync_playwright

    url = "https://planpty.com/eventos"
    eventos: list[Evento] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=HEADERS["User-Agent"])
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # PlanPTY actualmente publica los eventos como enlaces SSR.
            enlaces = page.query_selector_all("a[href*='/eventos/']")
            vistos: set[str] = set()
            for enlace in enlaces:
                href = enlace.get_attribute("href")
                nombre = enlace.inner_text().strip()
                if not href or not nombre or href in vistos:
                    continue
                vistos.add(href)
                email, tel = extraer_contacto(nombre)
                eventos.append(Evento(
                    nombre=nombre,
                    fecha=extraer_fecha_desde_texto(nombre),
                    lugar="",
                    categoria="",
                    organizador="",
                    email=email,
                    telefono=tel,
                    url=urljoin(url, href),
                    fuente="planpty.com",
                    tipo_fuente="dinamica",
                ))
            browser.close()
    except Exception as e:
        print(f"[!] Error en PlanPTY: {e}", file=sys.stderr)
    return eventos


# ---------------------------------------------------------------------------
# ORQUESTACIÓN Y EXPORTACIÓN
# ---------------------------------------------------------------------------

def recolectar_todo(incluir_dinamicas: bool = True) -> list[Evento]:
    eventos: list[Evento] = []

    print("-> Fuentes estáticas...")
    eventos += scrape_micultura()
    time.sleep(1)
    eventos += scrape_calendario_panama()
    eventos += scrape_panama_convention_center()

    if incluir_dinamicas:
        print("-> Fuentes dinámicas (Playwright)...")
        ev_brite = scrape_eventbrite_panama()
        enriquecer_contacto_eventbrite(ev_brite)
        eventos += ev_brite
        eventos += scrape_planpty()

    eventos = [clasificar_evento(evento) for evento in eventos]
    eventos = filtrar_por_horizonte(eventos)
    print(f"-> Ventana de monitoreo: próximos {HORIZONTE_MESES} meses ({len(eventos)} eventos)")
    return eventos


def exportar(eventos: list[Evento], base: str = "eventos_panama") -> None:
    if not eventos:
        print("[!] No se recolectó ningún evento.")
        return

    with open(f"{base}.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(eventos[0]).keys()))
        writer.writeheader()
        for ev in eventos:
            writer.writerow(asdict(ev))

    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump([asdict(e) for e in eventos], f, ensure_ascii=False, indent=2)

    print(f"[OK] {len(eventos)} eventos exportados -> {base}.csv / {base}.json")


if __name__ == "__main__":
    todos = recolectar_todo(incluir_dinamicas=True)
    exportar(todos)
