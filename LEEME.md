# Monitor del Banco de Alimentos 🥫

Vigila la tienda de https://bancodealimentos.or.cr y le avisa al teléfono
(app **ntfy**) cuando aparece un producto nuevo o cuando algo agotado vuelve
a estar disponible.

## Cómo funciona

Cada ~3 minutos el programa entra a la tienda con su usuario, lee la lista de
productos y la compara con la revisión anterior. Si hay algo nuevo, le llega
una notificación al instante con el nombre del producto.

> Ojo: el servidor del banco es LENTO (cada revisión completa tarda 2–4 minutos).
> Es normal que el monitor se tome su tiempo entre revisiones.

## Paso 1 — Recibir los avisos en el teléfono (app ntfy, gratis y sin cuenta)

1. Instale la app **ntfy** (Play Store o App Store — gratis, sin registro).
2. Ábrala y toque el **+** (Subscribe to topic / Suscribirse a un tema).
3. Escriba EXACTO este código de canal:

   `TU-CANAL-NTFY`  ← (el código privado que solo usted conoce)

4. Listo. Ahí mismo debería aparecer el mensaje de prueba, y de ahora en
   adelante cada aviso le suena como notificación normal.

> El código exacto del canal NO se guarda en este repositorio (por seguridad);
> vive solo en el secreto `NTFY_TOPIC` de GitHub y en su app.
>
> Consejo: en la app, mantenga presionado el tema → ajustes → puede subirle
> la prioridad o el sonido para que no se le pase ningún aviso.
>
> WhatsApp (CallMeBot) y Telegram quedaron como canales opcionales: si algún
> día consigue la apikey de CallMeBot o crea un bot de Telegram, corra
> `configurar_whatsapp.bat` o `configurar_telegram.py` y avisará por ahí también.

## Paso 2 — El monitor

Ya quedó encendido. Si algún día hay que volver a arrancarlo (ej. después de
reiniciar la computadora): doble clic en **`iniciar_monitor.bat`** y deje la
ventana abierta (minimizada está bien).

- La primera vez registra los productos que ya existen (no avisa por esos).
- Después avisa SOLO por productos nuevos o que regresaron tras agotarse.
- La computadora debe quedar **encendida y con internet**.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `iniciar_monitor.bat` | Arranca el monitor (doble clic) |
| `configurar_whatsapp.bat` | Activa los avisos por WhatsApp (solo la primera vez) |
| `config.json` | Su usuario, contraseña, WhatsApp e intervalo |
| `productos_vistos.json` | Memoria de productos ya vistos (no tocar) |
| `monitor.log` | Historial de lo que ha hecho el monitor |

## Ajustes (config.json)

- `intervalo_segundos`: cada cuánto revisa (180 = 3 minutos). No lo baje de 120
  para no saturar el servidor del banco.
- También se puede agregar Telegram (sección `telegram` del config) si algún
  día lo quiere como segundo canal; `configurar_telegram.py` sigue ahí.

## Problemas comunes

- **No llegan avisos**: revise en la app ntfy que esté suscrito a su canal
  privado (el mismo código guardado en el secreto `NTFY_TOPIC` de GitHub),
  escrito sin espacios y tal cual.
- **"Login rechazado"** en el log: la contraseña del banco cambió;
  actualícela en `config.json`.
- **Errores de red en el log**: normal, el servidor del banco es lento;
  el monitor reintenta solo.
