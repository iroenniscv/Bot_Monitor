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
CHECK_INTERVAL = 30  # 30 segundos para pruebas
PORT = int(os.environ.get('PORT', 8080))  # Para Render

# Emojis
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_WARNING = "⚠️"
EMOJI_LIST = "📋"
EMOJI_ADD = "➕"
EMOJI_TRASH = "🗑️"
EMOJI_TIME = "⏱️"
EMOJI_LOADING = "🔄"
EMOJI_HELP = "❓"
EMOJI_ID = "🆔"

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
    help_command(update, context)

def help_command(update: Update, context: CallbackContext):
    help_text = (
        f"{EMOJI_HELP} *COMANDOS DISPONIBLES*\n\n"
        f"/start - Muestra este mensaje de ayuda\n"
        f"/help - Muestra los comandos disponibles\n"
        f"/add <nombre> <url> {EMOJI_ADD} - Añadir nuevo sitio web\n"
        f"/list {EMOJI_LIST} - Mostrar todos los sitios monitoreados\n"
        f"/status - Ver estado actual en tiempo real\n"
        f"/delete <id> {EMOJI_TRASH} - Eliminar un sitio por su ID\n"
        f"/monitor - Activar monitoreo automático\n"
        f"/stop - Detener monitoreo automático\n\n"
        f"Ejemplo para añadir sitio:\n"
        f"`/add Google https://google.com`\n\n"
        f"Para eliminar un sitio, primero usa `/list` para ver los IDs"
    )
    update.message.reply_text(help_text, parse_mode="Markdown")

def add_website(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("ℹ️ Formato: /add <nombre> <url>\nEjemplo: /add Google https://google.com")
        return
    
    name = " ".join(args[:-1])
    url = args[-1]
    
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
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
    cursor.execute("SELECT id, name, url, last_status, last_checked, response_time FROM websites")
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        update.message.reply_text("ℹ️ No hay sitios monitoreados actualmente")
        return
    
    message = f"{EMOJI_LIST} *Sitios Monitoreados (ID - Nombre):*\n\n"
    for id, name, url, status, checked, resp_time in websites:
        status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
        time_str = f"{resp_time:.2f}s" if resp_time else "N/A"
        message += (
            f"{EMOJI_ID} *{id}* - {status_emoji} *{name}*\n"
            f"🔗 `{url}`\n"
            f"{EMOJI_TIME} {time_str} | 📅 {checked}\n\n"
        )
    
    update.message.reply_text(message, parse_mode="Markdown")

def delete_website(update: Update, context: CallbackContext):
    if not context.args:
        list_websites(update, context)
        update.message.reply_text("\nℹ️ Usa: /delete <ID> para eliminar un sitio")
        return
    
    try:
        site_id = int(context.args[0])
    except ValueError:
        update.message.reply_text("❌ El ID debe ser un número. Usa /list para ver los IDs")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM websites WHERE id = ?", (site_id,))
    result = cursor.fetchone()
    
    if not result:
        update.message.reply_text("❌ No se encontró un sitio con ese ID")
        conn.close()
        return
    
    site_name = result[0]
    cursor.execute("DELETE FROM websites WHERE id = ?", (site_id,))
    conn.commit()
    conn.close()
    
    update.message.reply_text(
        f"{EMOJI_TRASH} Sitio eliminado correctamente:\n*{site_name}* (ID: {site_id})",
        parse_mode="Markdown"
    )

def status(update: Update, context: CallbackContext):
    loading_msg = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"{EMOJI_LOADING} Verificando estado de los sitios web...",
        parse_mode="Markdown"
    )
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, name FROM websites")
    websites = cursor.fetchall()
    
    if not websites:
        context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=loading_msg.message_id,
            text="ℹ️ No hay sitios monitoreados actualmente"
        )
        conn.close()
        return
    
    message = f"{EMOJI_LIST} *Estado Actual de los Sitios:*\n\n"
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
        
        status_emoji = EMOJI_UP if result["status"] == "UP" else EMOJI_DOWN
        time_str = f"{result.get('response_time', 0):.2f}s"
        message += (
            f"{EMOJI_ID} *{id}* - {status_emoji} *{name}*\n"
            f"🔗 `{url}`\n"
            f"{EMOJI_TIME} {time_str} | 📅 {datetime.now().strftime('%H:%M:%S')}\n"
            f"Estado: {'🟢 Activo' if result['status'] == 'UP' else '🔴 Inactivo'}\n\n"
        )
    
    conn.commit()
    conn.close()
    
    context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=loading_msg.message_id,
        text=message,
        parse_mode="Markdown"
    )

def monitor_command(update: Update, context: CallbackContext):
    if 'job' in context.chat_data:
        update.message.reply_text("ℹ️ El monitoreo automático ya está activado")
        return
    
    job = context.job_queue.run_repeating(
        monitor_websites,
        interval=CHECK_INTERVAL,
        first=0,
        context=update.message.chat_id
    )
    context.chat_data['job'] = job
    
    update.message.reply_text(
        f"✅ Monitoreo automático activado\n"
        f"Se verificará cada {CHECK_INTERVAL} segundos"
    )

def stop_command(update: Update, context: CallbackContext):
    if 'job' not in context.chat_data:
        update.message.reply_text("ℹ️ El monitoreo automático no está activado")
        return
    
    context.chat_data['job'].schedule_removal()
    del context.chat_data['job']
    
    update.message.reply_text("⏹️ Monitoreo automático detenido")

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
    flask_thread.daemon = True
    flask_thread.start()
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("delete", delete_website))
    dp.add_handler(CommandHandler("monitor", monitor_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    
    # Tarea periódica
    job_queue = updater.job_queue
    job_queue.run_repeating(monitor_websites, interval=CHECK_INTERVAL, first=0)
    
    # Iniciar bot
    updater.start_polling()
    logger.info("Bot iniciado en modo polling")
    updater.idle()

if __name__ == "__main__":
    main()