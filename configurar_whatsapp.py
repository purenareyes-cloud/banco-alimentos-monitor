# -*- coding: utf-8 -*-
"""
Asistente para configurar los avisos por WhatsApp (servicio gratuito CallMeBot).

ANTES de correr esto, haga este paso ÚNICO desde su teléfono:

  1. Guarde en sus contactos este número:  +34 644 44 21 48  (CallMeBot)
  2. Mándele por WhatsApp este mensaje EXACTO:

         I allow callmebot to send me messages

  3. En segundos le responde con su "apikey" (un número, ej: 123456).

Luego corra este script y pegue esa apikey.
"""

import json
import sys
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).parent / "config.json"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def main():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)

    wa = cfg.setdefault("whatsapp", {"phone": "", "apikey": ""})

    print("=== Configurar avisos por WhatsApp ===\n")
    print("¿Ya le mandó al +34 644 44 21 48 el mensaje")
    print('"I allow callmebot to send me messages" y recibió su apikey?')
    print("Si no, hágalo primero (vea las instrucciones arriba o en LEEME.md).\n")

    tel = input(f"Su número de WhatsApp con código de país [{wa.get('phone') or '+506...'}]: ").strip()
    if tel:
        if not tel.startswith("+"):
            tel = "+" + tel
        wa["phone"] = tel
    if not wa.get("phone"):
        print("Ocupo el número de teléfono. Saliendo.")
        return

    apikey = input("Pegue aquí la apikey que le mandó CallMeBot: ").strip()
    if not apikey:
        print("No se ingresó la apikey. Saliendo.")
        return
    wa["apikey"] = apikey

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("\nConfiguración guardada. Enviando mensaje de prueba...")

    r = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={
            "phone": wa["phone"],
            "apikey": apikey,
            "text": "✅ ¡Prueba exitosa! Le avisaré por aquí cuando haya "
                    "productos nuevos en el Banco de Alimentos.",
        },
        timeout=60,
    )
    if r.status_code == 200 and "error" not in r.text.lower():
        print("✅ Mensaje de prueba enviado. ¡Revise su WhatsApp!")
        print("El monitor usará WhatsApp automáticamente desde el próximo ciclo.")
    else:
        print(f"⚠ Algo falló ({r.status_code}): {r.text[:300]}")
        print("Revise que la apikey y el número estén bien y corra esto de nuevo.")


if __name__ == "__main__":
    main()
