# -*- coding: utf-8 -*-
"""
Una sola revisión de la tienda, pensada para correr en la nube
(GitHub Actions). No hace bucle: revisa una vez y termina.

Lee la configuración desde variables de entorno (GitHub Secrets):
    BDA_USER   -> usuario del banco
    BDA_PASS   -> contraseña del banco
    NTFY_TOPIC -> canal de ntfy donde llegan los avisos

El estado (productos ya vistos) se guarda en productos_vistos.json,
que el flujo de GitHub Actions vuelve a guardar (commit) en cada corrida
para que "recuerde" entre ejecuciones.
"""

import os
import sys

import monitor  # reutiliza toda la lógica ya probada

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def construir_config():
    return {
        "sitio": {
            "base_url": "https://bancodealimentos.or.cr",
            "login_url": "https://bancodealimentos.or.cr/web/login",
            "shop_url": "https://bancodealimentos.or.cr/en_US/shop",
            "usuario": os.environ["BDA_USER"],
            "password": os.environ["BDA_PASS"],
        },
        "ntfy": {"topic": os.environ.get("NTFY_TOPIC", "")},
        "max_paginas": 10,
    }


def main():
    cfg = construir_config()
    estado = monitor.cargar_estado()
    primera_vez = not estado

    monitor.log("=== Revisión (nube) ===")
    sesion = monitor.iniciar_sesion(cfg)
    monitor.una_revision(cfg, sesion, estado, primera_vez)
    monitor.log("Revisión terminada.")


if __name__ == "__main__":
    main()
