# -*- coding: utf-8 -*-
"""
Monitor del Banco de Alimentos de Costa Rica (bancodealimentos.or.cr)

Revisa la tienda cada X minutos y avisa por Telegram cuando aparece
un producto nuevo. Uso personal.

Modos:
    python monitor.py            -> ciclo infinito (uso normal)
    python monitor.py --test     -> una sola revisión, imprime lo que encuentra
    python monitor.py --debug    -> igual que --test pero guarda el HTML en debug_shop.html
"""

import json
import re
import socket
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / "productos_vistos.json"
LOG_FILE = BASE_DIR / "monitor.log"

# Consola de Windows a veces no soporta emojis; forzamos UTF-8 si se puede
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def log(msg):
    linea = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(linea, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def cargar_config():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        return json.load(f)


def cargar_estado():
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_estado(estado):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- sesión

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 120  # el servidor del banco es lento (a veces tarda más de un minuto)


def get_con_reintentos(sesion, url, intentos=3):
    """GET con reintentos porque el servidor a veces tarda en responder."""
    ultimo_error = None
    for i in range(intentos):
        try:
            return sesion.get(url, timeout=TIMEOUT)
        except requests.RequestException as e:
            ultimo_error = e
            if i < intentos - 1:
                log(f"Reintentando ({i + 2}/{intentos}) {url} ...")
                time.sleep(5)
    raise ultimo_error


def iniciar_sesion(cfg):
    """Inicia sesión en el portal Odoo y devuelve la sesión de requests."""
    s = requests.Session()
    s.headers.update(HEADERS)

    r = get_con_reintentos(s, cfg["sitio"]["login_url"])
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    datos = {
        "login": cfg["sitio"]["usuario"],
        "password": cfg["sitio"]["password"],
        "redirect": "/en_US/shop",
    }
    csrf = soup.find("input", {"name": "csrf_token"})
    if csrf and csrf.get("value"):
        datos["csrf_token"] = csrf["value"]

    r = s.post(cfg["sitio"]["login_url"], data=datos, timeout=TIMEOUT)
    r.raise_for_status()

    # Si seguimos en la página de login, las credenciales fallaron
    if "/web/login" in r.url:
        soup2 = BeautifulSoup(r.text, "html.parser")
        alerta = soup2.find(class_="alert-danger")
        detalle = alerta.get_text(strip=True) if alerta else "sin detalle"
        raise RuntimeError(f"Login rechazado: {detalle}")

    log("Sesión iniciada correctamente.")
    return s


def sesion_expirada(html, url_final):
    return "/web/login" in url_final or 'action="/web/login"' in html


# ---------------------------------------------------------------- scraping

PATRON_PRODUCTO = re.compile(r"/shop/(?:product/)?[^/?#]*?-(\d+)(?:[/?#]|$)")


def extraer_productos(html, base_url):
    """Extrae productos de una página del shop. Devuelve dict id -> info."""
    soup = BeautifulSoup(html, "html.parser")
    productos = {}

    # Estrategia 1: celdas de producto estándar de Odoo
    celdas = soup.select(".oe_product, .oe_product_cart, [data-publish]")

    # Estrategia 2 (respaldo): cualquier enlace que parezca de producto
    enlaces = celdas if celdas else [soup]

    for contenedor in enlaces:
        for a in contenedor.find_all("a", href=True):
            m = PATRON_PRODUCTO.search(a["href"])
            if not m:
                continue
            pid = m.group(1)
            nombre = a.get_text(strip=True) or a.get("content", "").strip()
            if not nombre:
                img = a.find("img")
                if img:
                    nombre = (img.get("alt") or "").strip()
            if not nombre:
                continue
            url = a["href"]
            if url.startswith("/"):
                url = base_url + url

            precio = ""
            celda = a.find_parent(class_=re.compile("oe_product|o_wsale_product"))
            if celda:
                p = celda.find(class_="oe_currency_value")
                if p:
                    precio = p.get_text(strip=True)

            if pid not in productos or len(nombre) > len(productos[pid]["nombre"]):
                productos[pid] = {"nombre": nombre, "url": url, "precio": precio}

    return productos


def url_pagina(shop_url, n):
    if n == 1:
        return shop_url
    base, sep, query = shop_url.partition("?")
    return f"{base}/page/{n}{sep}{query}"


def revisar_tienda(sesion, cfg, guardar_html=False):
    """Recorre la tienda (con paginación) y devuelve todos los productos."""
    base_url = cfg["sitio"]["base_url"]
    shop_url = cfg["sitio"]["shop_url"]
    todos = {}

    for n in range(1, cfg.get("max_paginas", 10) + 1):
        r = get_con_reintentos(sesion, url_pagina(shop_url, n))
        if sesion_expirada(r.text, r.url):
            raise PermissionError("Sesión expirada")
        r.raise_for_status()

        if guardar_html and n == 1:
            (BASE_DIR / "debug_shop.html").write_text(r.text, encoding="utf-8")
            log("HTML guardado en debug_shop.html")

        encontrados = extraer_productos(r.text, base_url)
        nuevos_en_pagina = {k: v for k, v in encontrados.items() if k not in todos}
        todos.update(encontrados)

        # Si la página no aportó productos nuevos, se acabó la paginación
        if not nuevos_en_pagina:
            break

    return todos


# ---------------------------------------------------------------- avisos

def enviar_ntfy(cfg, texto):
    """Notificación push gratuita vía ntfy.sh (app 'ntfy' en el teléfono)."""
    topic = cfg.get("ntfy", {}).get("topic", "")
    r = requests.post(
        f"https://ntfy.sh/{topic}",
        data=texto.encode("utf-8"),
        headers={
            "Title": "Banco de Alimentos",
            "Priority": "high",
            "Tags": "shopping_cart",
            "Click": cfg["sitio"]["shop_url"],
        },
        timeout=30,
    )
    if r.status_code != 200:
        log(f"Error enviando ntfy: {r.status_code} {r.text[:200]}")
        return False
    return True


def enviar_whatsapp(cfg, texto):
    """Envía un WhatsApp usando el servicio gratuito CallMeBot."""
    wa = cfg.get("whatsapp", {})
    r = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": wa["phone"], "text": texto, "apikey": wa["apikey"]},
        timeout=60,
    )
    if r.status_code != 200 or "error" in r.text.lower():
        log(f"Error enviando WhatsApp: {r.status_code} {r.text[:200]}")
        return False
    return True


def enviar_telegram(cfg, texto):
    tg = cfg.get("telegram", {})
    r = requests.post(
        f"https://api.telegram.org/bot{tg['bot_token']}/sendMessage",
        data={
            "chat_id": tg["chat_id"],
            "text": texto,
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    if r.status_code != 200:
        log(f"Error enviando Telegram: {r.status_code} {r.text[:200]}")
        return False
    return True


def notificar(cfg, texto):
    """Manda el aviso por los canales que estén configurados."""
    enviado = False
    if cfg.get("ntfy", {}).get("topic"):
        enviado = enviar_ntfy(cfg, texto) or enviado
    wa = cfg.get("whatsapp", {})
    if wa.get("phone") and wa.get("apikey"):
        enviado = enviar_whatsapp(cfg, texto) or enviado
    tg = cfg.get("telegram", {})
    if tg.get("bot_token") and tg.get("chat_id"):
        enviado = enviar_telegram(cfg, texto) or enviado
    if not enviado:
        log("(Aviso NO enviado: ningún canal configurado)")
    return enviado


def construir_mensaje(cfg, nuevos, reaparecidos):
    lineas = []
    if nuevos:
        lineas.append("🚨 ¡NUEVO en el Banco de Alimentos!")
        for info in nuevos.values():
            precio = f" — {info['precio']}" if info["precio"] else ""
            lineas.append(f"• {info['nombre']}{precio}")
    if reaparecidos:
        if lineas:
            lineas.append("")
        lineas.append("🔄 Disponible de nuevo:")
        for info in reaparecidos.values():
            precio = f" — {info['precio']}" if info["precio"] else ""
            lineas.append(f"• {info['nombre']}{precio}")
    lineas.append("")
    lineas.append(f"Entre rápido 👉 {cfg['sitio']['shop_url']}")
    return "\n".join(lineas)


# ---------------------------------------------------------------- ciclo

def una_revision(cfg, sesion, estado, primera_vez):
    productos = revisar_tienda(sesion, cfg)
    ahora = datetime.now()
    ids_actuales = set(productos)

    # Novedad por PRESENCIA (no por tiempo): esto es robusto aunque las
    # revisiones no sean parejas (ej. GitHub gratis corre a ratos).
    #   - nuevo       = nunca antes visto
    #   - reaparecido = estaba marcado como ausente y ahora volvió
    nuevos = {}
    reaparecidos = {}
    for pid, info in productos.items():
        previo = estado.get(pid)
        if previo is None:
            nuevos[pid] = info
        elif previo.get("presente") is False:
            reaparecidos[pid] = info

    # Los que están ahora → presentes; los que estaban y ya no → ausentes.
    for pid, info in productos.items():
        estado[pid] = {
            "nombre": info["nombre"],
            "url": info["url"],
            "visto": ahora.isoformat(timespec="seconds"),
            "presente": True,
        }
    for pid in estado:
        if pid not in ids_actuales:
            estado[pid]["presente"] = False
    guardar_estado(estado)

    if primera_vez:
        log(f"Primera revisión: {len(productos)} productos registrados como base "
            "(no se notifica lo que ya estaba).")
        if productos:
            notificar(
                cfg,
                f"✅ Monitor iniciado. Hay {len(productos)} productos en la tienda "
                "ahora mismo. Le avisaré cuando aparezca algo nuevo.",
            )
    elif nuevos or reaparecidos:
        detalle = ", ".join(
            i["nombre"] for i in list(nuevos.values()) + list(reaparecidos.values())
        )
        log(f"¡Novedades! {len(nuevos)} nuevo(s), {len(reaparecidos)} de vuelta: {detalle}")
        notificar(cfg, construir_mensaje(cfg, nuevos, reaparecidos))
    else:
        log(f"Sin novedades ({len(productos)} productos en tienda).")

    return productos


def main():
    modo_test = "--test" in sys.argv or "--debug" in sys.argv
    guardar_html = "--debug" in sys.argv

    # Candado: evita que corran dos monitores a la vez (daría avisos dobles).
    # Mientras este proceso viva, el puerto queda ocupado.
    if not modo_test:
        global _candado
        _candado = socket.socket()
        try:
            _candado.bind(("127.0.0.1", 47653))
        except OSError:
            print("Ya hay otro monitor corriendo. Esta copia se cierra.")
            sys.exit(3)

    cfg = cargar_config()
    estado = cargar_estado()
    primera_vez = not estado

    log("=== Monitor Banco de Alimentos ===")
    sesion = iniciar_sesion(cfg)

    if modo_test:
        productos = revisar_tienda(sesion, cfg, guardar_html=guardar_html)
        log(f"Productos encontrados: {len(productos)}")
        for pid, info in productos.items():
            precio = f" — {info['precio']}" if info["precio"] else ""
            log(f"  [{pid}] {info['nombre']}{precio}")
        return

    while True:
        try:
            # Releer la config en cada ciclo: así los cambios (ej. la clave
            # de WhatsApp) se aplican sin reiniciar el monitor
            cfg = cargar_config()
            una_revision(cfg, sesion, estado, primera_vez)
            primera_vez = False
        except PermissionError:
            log("Sesión expirada, iniciando sesión de nuevo...")
            try:
                sesion = iniciar_sesion(cfg)
            except Exception as e:
                log(f"No se pudo reiniciar sesión: {e}")
        except requests.RequestException as e:
            log(f"Error de red (se reintenta en el próximo ciclo): {e}")
        except Exception:
            log("Error inesperado:\n" + traceback.format_exc())
        time.sleep(cfg.get("intervalo_segundos", 180))


if __name__ == "__main__":
    main()
