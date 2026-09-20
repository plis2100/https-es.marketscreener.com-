import hashlib
import json
import re
import time
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree

from bs4 import BeautifulSoup
from curl_cffi import requests
from zoneinfo import ZoneInfo


DOMINIO = "https://es.marketscreener.com"

ARCHIVO_RSS = Path("rss.xml")
ARCHIVO_ESTADO = Path("estado.json")

MAX_NOTICIAS = 2500


SECCIONES = {
    "Todas las noticias":
        "https://es.marketscreener.com/noticias/",

    "Macroeconomía":
        "https://es.marketscreener.com/noticias/temas/economia/",

    "Política":
        "https://es.marketscreener.com/noticias/temas/politico/",

    "Geopolítica":
        "https://es.marketscreener.com/noticias/temas/geopolitica/",

    "Tecnología":
        "https://es.marketscreener.com/noticias/temas/tecnologia/",

    "Comercio internacional":
        "https://es.marketscreener.com/noticias/temas/comercio-internacional/",

    "Conflictos militares":
        "https://es.marketscreener.com/noticias/temas/conflictos/",

    "Fiscalidad":
        "https://es.marketscreener.com/noticias/temas/fiscalidad/",

    "Desarrollo sostenible":
        "https://es.marketscreener.com/noticias/temas/desarrollo-sostenible/",

    "Legal y regulación":
        "https://es.marketscreener.com/noticias/temas/legal/",

    "Resultados financieros":
        "https://es.marketscreener.com/noticias/empresa/resultados-financieros/",

    "Recomendaciones de analistas":
        "https://es.marketscreener.com/noticias/empresa/recomendaciones/",

    "Transcripciones":
        "https://es.marketscreener.com/noticias/empresa/call-transcripts/",

    "Comunicados de prensa":
        "https://es.marketscreener.com/noticias/empresa/comunicados/",

    "Operaciones de iniciados":
        "https://es.marketscreener.com/noticias/empresa/transacciones-insider/",

    "Controversias":
        "https://es.marketscreener.com/noticias/empresa/controversias/",

    "Innovaciones y expansiones":
        "https://es.marketscreener.com/noticias/empresa/innovaciones-expansiones/",

    "OPV e IPO":
        "https://es.marketscreener.com/noticias/empresa/IPO/",

    "Rumores":
        "https://es.marketscreener.com/noticias/empresa/rumores/",

    "Activismo":
        "https://es.marketscreener.com/noticias/empresa/activismo/",

    "Sorpresas negativas":
        "https://es.marketscreener.com/noticias/empresa/negativo/",

    "Sorpresas positivas":
        "https://es.marketscreener.com/noticias/empresa/positivo/",

    "Nuevos contratos":
        "https://es.marketscreener.com/noticias/empresa/nuevos-contratos/",

    "Noticias de índices":
        "https://es.marketscreener.com/bolsa/indices/noticias/",

    "Noticias de divisas":
        "https://es.marketscreener.com/bolsa/divisas/noticias/",

    "Materias primas":
        "https://es.marketscreener.com/noticias/materia-prima/",

    "Criptomonedas":
        "https://es.marketscreener.com/bolsa/criptomonedas/noticias/",

    "ETF":
        "https://es.marketscreener.com/bolsa/etf/noticias/",

    "Tipos de interés":
        "https://es.marketscreener.com/noticias/tasas/",

    "Fondos":
        "https://es.marketscreener.com/noticias/fondos/",

    "Economía":
        "https://es.marketscreener.com/noticias/economia/",

    "Sectores":
        "https://es.marketscreener.com/noticias/sectores/",

    "Noticias más leídas":
        "https://es.marketscreener.com/noticias/mas-leidas/",

    "Noticias influyentes":
        "https://es.marketscreener.com/trading/noticias-influyentes",

    "Análisis":
        "https://es.marketscreener.com/analisis/",

    "Artículos imprescindibles":
        "https://es.marketscreener.com/analisis/imperdibles/",

    "Entrevistas":
        "https://es.marketscreener.com/analisis/entrevistas/",

    "Análisis de acciones":
        "https://es.marketscreener.com/analisis/acciones/",

    "Análisis de índices":
        "https://es.marketscreener.com/analisis/indices/",

    "Análisis de divisas":
        "https://es.marketscreener.com/analisis/divisas/",

    "Análisis de materias primas":
        "https://es.marketscreener.com/analisis/materia-prima/",

    "Análisis de ETF":
        "https://es.marketscreener.com/analisis/ETF/",

    "Análisis de criptomonedas":
        "https://es.marketscreener.com/analisis/criptomonedas/",

    "Análisis de tipos":
        "https://es.marketscreener.com/analisis/tasas/",
}


URLS_SECCIONES = {
    url.rstrip("/")
    for url in SECCIONES.values()
}


PALABRAS_EXCLUIDAS = {
    "conéctate",
    "suscribirse",
    "crear una cuenta",
    "más noticias",
    "más información",
    "todas",
    "inicio",
    "noticias",
    "acciones",
    "índices",
    "divisas",
    "materias primas",
    "criptomonedas",
    "fondos",
    "economía",
    "sectores",
    "análisis",
    "entrevistas",
}


def cargar_estado():
    if not ARCHIVO_ESTADO.exists():
        return []

    try:
        datos = json.loads(
            ARCHIVO_ESTADO.read_text(encoding="utf-8")
        )

        if isinstance(datos, list):
            return datos

    except (json.JSONDecodeError, OSError):
        pass

    return []


def guardar_estado(noticias):
    ARCHIVO_ESTADO.write_text(
        json.dumps(
            noticias,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def limpiar_texto(texto):
    if not texto:
        return ""

    return re.sub(
        r"\s+",
        " ",
        texto,
    ).strip()


def normalizar_url(url):
    url = url.split("#")[0]
    url = url.split("?")[0]

    if url.endswith("/"):
        return url

    return url


def es_url_valida(url, titulo):
    if not url:
        return False

    analizada = urlparse(url)

    if analizada.netloc not in {
        "es.marketscreener.com",
        "www.marketscreener.com",
    }:
        return False

    ruta = analizada.path.lower()

    if not (
        "/noticias/" in ruta
        or "/analisis/" in ruta
        or "/trading/noticias" in ruta
    ):
        return False

    if url.rstrip("/") in URLS_SECCIONES:
        return False

    titulo_minuscula = titulo.lower().strip()

    if titulo_minuscula in PALABRAS_EXCLUIDAS:
        return False

    if len(titulo) < 25:
        return False

    if titulo.startswith("Image:"):
        return False

    return True


def crear_identificador(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def buscar_bloque(enlace):
    bloque = enlace

    for _ in range(5):
        padre = bloque.parent

        if padre is None:
            break

        texto = limpiar_texto(
            padre.get_text(" ", strip=True)
        )

        if 40 <= len(texto) <= 1800:
            bloque = padre

        if padre.name in {
            "article",
            "li",
        }:
            bloque = padre
            break

    return bloque


def extraer_fecha(texto):
    ahora_madrid = datetime.now(
        ZoneInfo("Europe/Madrid")
    )

    patron_fecha = re.search(
        r"\b([0-3]?\d)[/-]([01]?\d)"
        r"(?:[/-](\d{2,4}))?\b",
        texto,
    )

    patron_hora = re.search(
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        texto,
    )

    anio = ahora_madrid.year
    mes = ahora_madrid.month
    dia = ahora_madrid.day
    hora = ahora_madrid.hour
    minuto = ahora_madrid.minute

    if patron_fecha:
        posible_dia = int(
            patron_fecha.group(1)
        )
        posible_mes = int(
            patron_fecha.group(2)
        )

        if 1 <= posible_dia <= 31:
            dia = posible_dia

        if 1 <= posible_mes <= 12:
            mes = posible_mes

        if patron_fecha.group(3):
            anio_texto = patron_fecha.group(3)

            if len(anio_texto) == 2:
                anio = 2000 + int(anio_texto)
            else:
                anio = int(anio_texto)

    if patron_hora:
        hora = int(
            patron_hora.group(1)
        )
        minuto = int(
            patron_hora.group(2)
        )

    try:
        fecha = datetime(
            anio,
            mes,
            dia,
            hora,
            minuto,
            tzinfo=ZoneInfo("Europe/Madrid"),
        )

        return fecha.astimezone(
            timezone.utc
        ).isoformat()

    except ValueError:
        return datetime.now(
            timezone.utc
        ).isoformat()


def descargar_seccion(sesion, nombre, url):
    print(
        f"Descargando sección: {nombre}"
    )

    respuesta = sesion.get(
        url,
        impersonate="chrome",
        timeout=45,
        allow_redirects=True,
        headers={
            "Accept-Language":
                "es-ES,es;q=0.9,en;q=0.7",
            "Referer":
                "https://es.marketscreener.com/",
        },
    )

    print(
        f"Respuesta {respuesta.status_code}: {url}"
    )

    if respuesta.status_code != 200:
        return []

    soup = BeautifulSoup(
        respuesta.text,
        "html.parser",
    )

    zona = soup.find("main") or soup

    noticias = []
    urls_vistas = set()

    for enlace in zona.find_all(
        "a",
        href=True,
    ):
        titulo = limpiar_texto(
            enlace.get_text(" ", strip=True)
        )

        href = enlace.get(
            "href",
            "",
        ).strip()

        url_noticia = normalizar_url(
            urljoin(
                DOMINIO,
                href,
            )
        )

        if not es_url_valida(
            url_noticia,
            titulo,
        ):
            continue

        if url_noticia in urls_vistas:
            continue

        bloque = buscar_bloque(enlace)

        descripcion = limpiar_texto(
            bloque.get_text(
                " ",
                strip=True,
            )
        )

        if len(descripcion) < len(titulo):
            descripcion = titulo

        if len(descripcion) > 1800:
            descripcion = descripcion[:1800]

        fecha = extraer_fecha(
            descripcion
        )

        noticias.append(
            {
                "id": crear_identificador(
                    url_noticia
                ),
                "titulo": titulo[:300],
                "descripcion": descripcion,
                "url": url_noticia,
                "fecha": fecha,
                "seccion": nombre,
            }
        )

        urls_vistas.add(url_noticia)

    print(
        f"Encontradas en {nombre}: "
        f"{len(noticias)}"
    )

    return noticias


def descargar_todo():
    sesion = requests.Session()

    noticias = []
    urls_vistas = set()
    secciones_correctas = 0

    for nombre, url in SECCIONES.items():
        try:
            noticias_seccion = descargar_seccion(
                sesion,
                nombre,
                url,
            )

            if noticias_seccion:
                secciones_correctas += 1

            for noticia in noticias_seccion:
                url_noticia = noticia["url"]

                if url_noticia in urls_vistas:
                    continue

                noticias.append(noticia)
                urls_vistas.add(url_noticia)

            time.sleep(0.35)

        except Exception as error:
            print(
                f"Error en {nombre}: {error}"
            )

    print(
        f"Secciones con noticias: "
        f"{secciones_correctas}"
    )

    print(
        f"Noticias nuevas detectadas: "
        f"{len(noticias)}"
    )

    if not noticias:
        raise RuntimeError(
            "No se encontró ninguna noticia "
            "en MarketScreener."
        )

    noticias.sort(
        key=lambda noticia: noticia["fecha"],
        reverse=True,
    )

    return noticias


def combinar_noticias(nuevas, antiguas):
    resultado = []
    urls_vistas = set()

    for noticia in nuevas + antiguas:
        url = noticia.get(
            "url",
            "",
        )

        if not url:
            continue

        if url in urls_vistas:
            continue

        resultado.append(noticia)
        urls_vistas.add(url)

    resultado.sort(
        key=lambda noticia: noticia.get(
            "fecha",
            "",
        ),
        reverse=True,
    )

    return resultado[:MAX_NOTICIAS]


def convertir_fecha_rss(fecha_iso):
    try:
        fecha = datetime.fromisoformat(
            fecha_iso.replace(
                "Z",
                "+00:00",
            )
        )

        if fecha.tzinfo is None:
            fecha = fecha.replace(
                tzinfo=timezone.utc
            )

        return format_datetime(
            fecha.astimezone(timezone.utc),
            usegmt=True,
        )

    except (TypeError, ValueError):
        return format_datetime(
            datetime.now(timezone.utc),
            usegmt=True,
        )


def crear_rss(noticias):
    rss = Element(
        "rss",
        {
            "version": "2.0",
            "xmlns:atom":
                "http://www.w3.org/2005/Atom",
        },
    )

    canal = SubElement(
        rss,
        "channel",
    )

    SubElement(
        canal,
        "title",
    ).text = (
        "MarketScreener España — Todas las noticias"
    )

    SubElement(
        canal,
        "link",
    ).text = (
        "https://es.marketscreener.com/noticias/"
    )

    SubElement(
        canal,
        "description",
    ).text = (
        "Noticias de todas las secciones y "
        "subdivisiones de MarketScreener España"
    )

    SubElement(
        canal,
        "language",
    ).text = "es"

    SubElement(
        canal,
        "lastBuildDate",
    ).text = format_datetime(
        datetime.now(timezone.utc),
        usegmt=True,
    )

    SubElement(
        canal,
        "ttl",
    ).text = "60"

    for noticia in noticias:
        item = SubElement(
            canal,
            "item",
        )

        SubElement(
            item,
            "title",
        ).text = noticia["titulo"]

        SubElement(
            item,
            "link",
        ).text = noticia["url"]

        guid = SubElement(
            item,
            "guid",
            {
                "isPermaLink": "true",
            },
        )

        guid.text = noticia["url"]

        SubElement(
            item,
            "pubDate",
        ).text = convertir_fecha_rss(
            noticia["fecha"]
        )

        SubElement(
            item,
            "category",
        ).text = noticia.get(
            "seccion",
            "MarketScreener",
        )

        descripcion = (
            "<p><strong>Sección: "
            + escape(
                noticia.get(
                    "seccion",
                    "MarketScreener",
                )
            )
            + "</strong></p>"
            + "<p>"
            + escape(
                noticia["descripcion"]
            )
            + "</p>"
            + '<p><a href="'
            + escape(noticia["url"])
            + '">Abrir en MarketScreener</a></p>'
        )

        SubElement(
            item,
            "description",
        ).text = descripcion

    ElementTree(rss).write(
        ARCHIVO_RSS,
        encoding="utf-8",
        xml_declaration=True,
    )


def main():
    antiguas = cargar_estado()
    nuevas = descargar_todo()

    noticias = combinar_noticias(
        nuevas,
        antiguas,
    )

    guardar_estado(noticias)
    crear_rss(noticias)

    print(
        f"Noticias encontradas ahora: "
        f"{len(nuevas)}"
    )

    print(
        f"Noticias conservadas: "
        f"{len(noticias)}"
    )


if __name__ == "__main__":
    main()
