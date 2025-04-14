import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from datetime import datetime
import re
import os
from threading import Thread
from flask import Flask

# Configuración
TOKEN = "7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8"
ADMIN_ID = 1759969205
DB_NAME = "website_monitor.db"
CHECK_INTERVAL = 30  # 30 segundos para pruebas (cambiar a 300 en producción)
PORT = int(os.environ.get('PORT', 8080))  # Para Render

# Emojis
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_WARNING = "⚠️"
EMOJI_LIST = "📋"
EMOJI_ADD = "➕"
EMOJI_TRASH = "🗑️"
EMOJI_TIME = "⏱️"

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Base de datos
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            last_status TEXT,
            last_checked TEXT,
            response_time REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Funciones de monitorización
def check_website(url):
    try:
        response = requests.get(url, timeout=10)
        return {
            "status": "UP" if response.status_code == 200 else "DOWN",
            "status_code": response.status_code,
            "response_time": response.elapsed.total_seconds()
        }
    except Exception as e:
        return {"status": "DOWN", "error": str(e)}

def monitor_websites(context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, name FROM websites")
    websites = cursor.fetchall()
    
    for website in websites:
        id, url, name = website
        result = check_website(url)
        
        cursor.execute('''
            UPDATE websites
            SET last_status = ?,
                last_checked = ?,
                response_time = ?
            WHERE id = ?
        ''', (
            result["status"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            result.get("response_time", 0),
            id
        ))
        
        if result["status"] == "DOWN":
            alert_msg = (
                f"{EMOJI_WARNING} *ALERTA*: {name} ({url}) está *INACCESIBLE*\n"
                f"Error: {result.get('error', 'Desconocido')}\n"
                f"Última verificación: {datetime.now().strftime('%H:%M:%S')}"
            )
            context.bot.send_message(
                chat_id=ADMIN_ID,
                text=alert_msg,
                parse_mode="Markdown"
            )
    
    conn.commit()
    conn.close()

# Comandos del bot
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🌐 *Monitor de Websites*\n\n"
        "Comandos disponibles:\n"
        f"/add {EMOJI_ADD} - Añadir nuevo sitio\n"
        f"/list {EMOJI_LIST} - Listar sitios monitoreados\n"
        f"/status - Ver estado actual\n"
        f"/delete - Eliminar un sitio",
        parse_mode="Markdown"
    )

def add_website(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("ℹ️ Formato: /add <nombre> <url>\nEjemplo: /add MiSitio https://ejemplo.com")
        return
    
    name = " ".join(args[:-1])
    url = args[-1]
    
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    # Validación básica de URL
    if not re.match(r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url):
        update.message.reply_text("❌ URL inválida. Debe comenzar con http:// o https://")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO websites (url, name) VALUES (?, ?)", (url, name))
        conn.commit()
        update.message.reply_text(
            f"{EMOJI_ADD} *{name}* añadido al monitor:\n`{url}`",
            parse_mode="Markdown"
        )
    except sqlite3.IntegrityError:
        update.message.reply_text("⚠️ Este sitio ya está siendo monitoreado")
    finally:
        conn.close()

def list_websites(update: Update, context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, last_status, last_checked, response_time FROM websites")
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        update.message.reply_text("ℹ️ No hay sitios monitoreados actualmente")
        return
    
    message = f"{EMOJI_LIST} *Sitios Monitoreados:*\n\n"
    for name, url, status, checked, resp_time in websites:
        status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
        time_str = f"{resp_time:.2f}s" if resp_time else "N/A"
        message += (
            f"{status_emoji} *{name}*\n"
            f"🔗 `{url}`\n"
            f"{EMOJI_TIME} {time_str} | 📅 {checked}\n\n"
        )
    
    update.message.reply_text(message, parse_mode="Markdown")

# Servidor web para Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de monitoreo activo", 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Inicialización del bot
def main():
    # Iniciar servidor Flask en segundo plano
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    
    # Tarea periódica
    job_queue = updater.job_queue
    job_queue.run_repeating(monitor_websites, interval=CHECK_INTERVAL, first=0)
    
    # Iniciar bot
    updater.start_polling()
    logger.info("Bot iniciado en modo polling")
    updater.idle()

if __name__ == "__main__":
    main()