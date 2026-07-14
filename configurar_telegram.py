# -*- coding: utf-8 -*-
"""
Asistente para configurar Telegram.

Antes de correr esto:
  1. En Telegram, busque el contacto @BotFather y escríbale: /newbot
  2. Póngale un nombre (ej: "Monitor Banco Alimentos") y un usuario
     que termine en "bot" (ej: banco_alimentos_avisos_bot)
  3. BotFather le da un TOKEN (algo como 123456789:AAH4x...). Cópielo.
  4. Abra el chat de su bot nuevo y mándele cualquier mensaje (ej: "hola").
  5. Corra este script: python configurar_telegram.py
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

    token = cfg["telegram"].get("bot_token", "").strip()
    if not token:
        token = input("Pegue aquí el token que le dio @BotFather: ").strip()
    if not token:
        print("No se ingresó ningún token. Saliendo.")
        return

    # Verificar el token
    r = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=30)
    if r.status_code != 200:
        print("El token no es válido. Revise que lo copió completo.")
        print(r.text[:300])
        return
    bot = r.json()["result"]
    print(f"Bot encontrado: @{bot['username']}")

    # Buscar el chat_id (requiere que usted le haya escrito al bot)
    r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
    updates = r.json().get("result", [])
    chat_id = None
    for u in reversed(updates):
        msg = u.get("message") or u.get("edited_message")
        if msg and msg.get("chat"):
            chat_id = str(msg["chat"]["id"])
            quien = msg["chat"].get("first_name", "")
            print(f"Chat detectado: {quien} (id {chat_id})")
            break

    if not chat_id:
        print()
        print("⚠ No encontré ningún mensaje. Abra Telegram, entre al chat de")
        print(f"  su bot @{bot['username']}, mándele 'hola' y corra esto de nuevo.")
        return

    cfg["telegram"]["bot_token"] = token
    cfg["telegram"]["chat_id"] = chat_id
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print("Configuración guardada en config.json")

    # Mensaje de prueba
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": "✅ ¡Prueba exitosa! Este bot le avisará "
              "cuando haya productos nuevos en el Banco de Alimentos."},
        timeout=30,
    )
    if r.status_code == 200:
        print("✅ Mensaje de prueba enviado. ¡Revise su Telegram!")
    else:
        print(f"No se pudo enviar el mensaje de prueba: {r.text[:300]}")


if __name__ == "__main__":
    main()
