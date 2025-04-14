.import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from datetime import datetime

# Configuración
TOKEN = "7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8"  # Reemplaza con el token de @BotFather
ADMIN_ID = 1759969205       # Reemplaza con tu ID de Telegram (para alertas)
DB_NAME = "website_monitor.db"
CHECK_INTERVAL = 60  # 5 minutos (en segundos)

# Emojis
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_WARNING = "⚠️"
EMOJI_LIST = "📋"
EMOJI_ADD = "➕"
EMOJI_TRASH = "🗑️"

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
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
            last_checked TEXT
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
            SET last_status = ?, last_checked = ?
            WHERE id = ?
        ''', (result["status"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id))
        
        if result["status"] == "DOWN":
            alert_msg = f"{EMOJI_WARNING} *ALERTA*: {name} ({url}) está *INACCESIBLE*.\nCódigo de error: {result.get('error', 'N/A')}"
            context.bot.send_message(chat_id=ADMIN_ID, text=alert_msg, parse_mode="Markdown")
    
    conn.commit()
    conn.close()

# Comandos del bot
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🌐 *Monitor de Websites*\n\n"
        "Usa /add para agregar una URL.\n"
        "Usa /list para ver tus sitios monitoreados.",
        parse_mode="Markdown"
    )

def add_website(update: Update, context: CallbackContext):
    args = context.args
    if len(args) < 2:
        update.message.reply_text("Uso: /add <nombre> <url>")
        return
    
    name, url = " ".join(args[:-1]), args[-1]
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO websites (url, name) VALUES (?, ?)", (url, name))
    conn.commit()
    conn.close()
    
    update.message.reply_text(f"{EMOJI_ADD} *{name}* ({url}) añadido al monitor.", parse_mode="Markdown")

def list_websites(update: Update, context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, last_status, last_checked FROM websites")
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        update.message.reply_text("No hay sitios monitoreados.")
        return
    
    message = f"{EMOJI_LIST} *Sitios Monitoreados:*\n\n"
    for name, url, status, checked in websites:
        status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
        message += f"{status_emoji} *{name}*: `{url}`\nÚltima verificación: {checked}\n\n"
    
    update.message.reply_text(message, parse_mode="Markdown")

# Inicialización del bot
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    
    # Tarea periódica de monitorización
    job_queue = updater.job_queue
    job_queue.run_repeating(monitor_websites, interval=CHECK_INTERVAL, first=0)
    
    # Iniciar bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
