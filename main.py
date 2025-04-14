import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from datetime import datetime, timedelta
import re

# Configuración
TOKEN = "7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8"  # Reemplaza con el token de @BotFather
ADMIN_ID = 1759969205       # Reemplaza con tu ID de Telegram (para alertas)
DB_NAME = "monitor_websites.db"
INTERVALO_VERIFICACION = 50  # 5 minutos (en segundos)
TIMEOUT = 10               # Tiempo máximo de espera para las peticiones

# Emojis
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_ALERTA = "⚠️"
EMOJI_LISTA = "📋"
EMOJI_AGREGAR = "➕"
EMOJI_ELIMINAR = "🗑️"
EMOJI_RELOJ = "⏱️"
EMOJI_CONFIG = "⚙️"

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Base de datos
def inicializar_bd():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sitios_web (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            nombre TEXT NOT NULL,
            ultimo_estado TEXT,
            ultima_verificacion TEXT,
            tiempo_respuesta REAL
        )
    ''')
    conn.commit()
    conn.close()

inicializar_bd()

# Funciones de monitorización
def verificar_sitio_web(url):
    try:
        respuesta = requests.get(url, timeout=TIMEOUT)
        return {
            "estado": "ACTIVO" if respuesta.status_code == 200 else "INACTIVO",
            "codigo_estado": respuesta.status_code,
            "tiempo_respuesta": respuesta.elapsed.total_seconds()
        }
    except Exception as e:
        return {"estado": "INACTIVO", "error": str(e)}

def monitorear_sitios(context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, nombre FROM sitios_web")
    sitios = cursor.fetchall()
    
    for sitio in sitios:
        id, url, nombre = sitio
        resultado = verificar_sitio_web(url)
        
        cursor.execute('''
            UPDATE sitios_web
            SET ultimo_estado = ?, 
                ultima_verificacion = ?,
                tiempo_respuesta = ?
            WHERE id = ?
        ''', (
            resultado["estado"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            resultado.get("tiempo_respuesta", 0),
            id
        ))
        
        if resultado["estado"] == "INACTIVO":
            mensaje_alerta = (
                f"{EMOJI_ALERTA} *ALERTA*: {nombre} ({url}) está *INACCESIBLE*\n"
                f"Error: {resultado.get('error', 'Desconocido')}\n"
                f"Última verificación: {datetime.now().strftime('%H:%M:%S')}"
            )
            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=mensaje_alerta,
                parse_mode="Markdown"
            )
    
    conn.commit()
    conn.close()

# Comandos del bot
def inicio(update: Update, context: CallbackContext):
    mensaje = (
        "🌐 *Monitor de Sitios Web*\n\n"
        "Puedes usar los siguientes comandos:\n\n"
        f"/agregar - {EMOJI_AGREGAR} Añadir un nuevo sitio web\n"
        f"/lista - {EMOJI_LISTA} Mostrar todos los sitios monitoreados\n"
        f"/eliminar - {EMOJI_ELIMINAR} Quitar un sitio del monitoreo\n"
        f"/estado - {EMOJI_RELOJ} Ver estado actual de todos los sitios\n"
        "\nRecibirás alertas automáticas cuando algún sitio no esté disponible."
    )
    update.message.reply_text(mensaje, parse_mode="Markdown")

def agregar_sitio(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            "ℹ️ Formato: /agregar <nombre> <url>\n\n"
            "Ejemplo: /agregar MiSitio https://misitio.com"
        )
        return
    
    nombre = " ".join(args[:-1])
    url = args[-1]
    
    # Asegurar que la URL tenga el protocolo
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    # Validar URL
    if not re.match(r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url):
        update.message.reply_text("❌ La URL proporcionada no es válida")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verificar si ya existe
    cursor.execute("SELECT 1 FROM sitios_web WHERE url = ?", (url,))
    if cursor.fetchone():
        update.message.reply_text("⚠️ Este sitio web ya está siendo monitoreado")
        conn.close()
        return
    
    cursor.execute(
        "INSERT INTO sitios_web (url, nombre) VALUES (?, ?)",
        (url, nombre)
    )
    conn.commit()
    conn.close()
    
    update.message.reply_text(
        f"{EMOJI_AGREGAR} *{nombre}* ({url}) ha sido añadido al monitor.",
        parse_mode="Markdown"
    )

def lista_sitios(update: Update, context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT nombre, url, ultimo_estado, ultima_verificacion, tiempo_respuesta 
        FROM sitios_web
    """)
    sitios = cursor.fetchall()
    conn.close()
    
    if not sitios:
        update.message.reply_text("ℹ️ No hay sitios web siendo monitoreados actualmente.")
        return
    
    mensaje = f"{EMOJI_LISTA} *Sitios Monitoreados:*\n\n"
    for nombre, url, estado, verificacion, tiempo_respuesta in sitios:
        emoji_estado = EMOJI_UP if estado == "ACTIVO" else EMOJI_DOWN
        tiempo_formateado = f"{tiempo_respuesta:.2f}s" if tiempo_respuesta else "N/A"
        
        mensaje += (
            f"{emoji_estado} *{nombre}*\n"
            f"🔗 `{url}`\n"
            f"⏱️ Tiempo respuesta: {tiempo_formateado}\n"
            f"🕒 Última verificación: {verificacion}\n\n"
        )
    
    update.message.reply_text(mensaje, parse_mode="Markdown")

def eliminar_sitio(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text(
            "ℹ️ Formato: /eliminar <id>\n"
            "Usa /lista para ver los IDs de los sitios"
        )
        return
    
    try:
        sitio_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ El ID debe ser un número")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Verificar si existe
    cursor.execute("SELECT nombre FROM sitios_web WHERE id = ?", (sitio_id,))
    resultado = cursor.fetchone()
    
    if not resultado:
        update.message.reply_text("❌ No se encontró un sitio con ese ID")
        conn.close()
        return
    
    nombre_sitio = resultado[0]
    cursor.execute("DELETE FROM sitios_web WHERE id = ?", (sitio_id,))
    conn.commit()
    conn.close()
    
    update.message.reply_text(f"{EMOJI_ELIMINAR} Sitio *{nombre_sitio}* eliminado del monitor.", parse_mode="Markdown")

def estado_actual(update: Update, context: CallbackContext):
    # Verificación inmediata de todos los sitios
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, nombre FROM sitios_web")
    sitios = cursor.fetchall()
    
    if not sitios:
        update.message.reply_text("ℹ️ No hay sitios web siendo monitoreados actualmente.")
        conn.close()
        return
    
    mensaje = "🔄 Verificando estado actual de los sitios...\n\n"
    update.message.reply_text(mensaje)
    
    mensaje_resultados = f"{EMOJI_RELOJ} *Estado Actual:*\n\n"
    
    for sitio in sitios:
        id, url, nombre = sitio
        resultado = verificar_sitio_web(url)
        
        emoji_estado = EMOJI_UP if resultado["estado"] == "ACTIVO" else EMOJI_DOWN
        tiempo_respuesta = f"{resultado.get('tiempo_respuesta', 0):.2f}s"
        
        mensaje_resultados += (
            f"{emoji_estado} *{nombre}*\n"
            f"🔗 `{url}`\n"
            f"⏱️ Tiempo: {tiempo_respuesta}\n"
            f"📊 Estado: {resultado['estado']}\n\n"
        )
        
        # Actualizar la base de datos
        cursor.execute('''
            UPDATE sitios_web
            SET ultimo_estado = ?, 
                ultima_verificacion = ?,
                tiempo_respuesta = ?
            WHERE id = ?
        ''', (
            resultado["estado"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            resultado.get("tiempo_respuesta", 0),
            id
        ))
    
    conn.commit()
    conn.close()
    update.message.reply_text(mensaje_resultados, parse_mode="Markdown")

# Inicialización del bot
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", inicio))
    dp.add_handler(CommandHandler("inicio", inicio))
    dp.add_handler(CommandHandler("agregar", agregar_sitio))
    dp.add_handler(CommandHandler("lista", lista_sitios))
    dp.add_handler(CommandHandler("eliminar", eliminar_sitio))
    dp.add_handler(CommandHandler("estado", estado_actual))
    
    # Comandos alternativos en inglés
    dp.add_handler(CommandHandler("add", agregar_sitio))
    dp.add_handler(CommandHandler("list", lista_sitios))
    dp.add_handler(CommandHandler("delete", eliminar_sitio))
    dp.add_handler(CommandHandler("status", estado_actual))
    
    # Tarea periódica de monitorización
    cola_tareas = updater.job_queue
    cola_tareas.run_repeating(
        monitorear_sitios, 
        interval=INTERVALO_VERIFICACION, 
        first=0
    )
    
    # Iniciar bot
    updater.start_polling()
    logger.info("Bot de monitoreo iniciado")
    updater.idle()

if __name__ == "__main__":
    main()