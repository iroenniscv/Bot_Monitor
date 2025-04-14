import logging
import sqlite3
import requests
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime

# Configuración
TOKEN = "7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8"  # Reemplaza con tu token de BotFather
DB_NAME = "monitor.db"
CHECK_INTERVAL = 60  # 1 minuto (chequeo de estado)
ALERT_INTERVAL = 60  # 1 minuto (notificaciones)

# Emojis para diseño
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_WARNING = "⚠️"
EMOJI_LIST = "📋"
EMOJI_ADD = "➕"
EMOJI_BELL = "🔔"
EMOJI_USER = "👤"
EMOJI_ID = "🆔"
EMOJI_LANG = "🌍"
EMOJI_TRASH = "🗑️"

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Decorador para comandos privados
def private_chat_only(func):
    def wrapper(update: Update, context: CallbackContext):
        if update.message.chat.type != "private":
            update.message.reply_text("🔒 Este bot solo funciona en chats privados.")
            return
        return func(update, context)
    return wrapper

# Base de datos
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
    cursor.execute("SELECT user_id, id, url, name FROM websites")
    websites = cursor.fetchall()
    
    for user_id, id, url, name in websites:
        result = check_website(url)
        
        cursor.execute('''
            UPDATE websites
            SET last_status = ?, last_checked = ?
            WHERE id = ?
        ''', (result["status"], datetime.now().strftime("%Y-%m-%d %H:%M:%S"), id))
        
        if result["status"] == "DOWN":
            alert_msg = (
                f"{EMOJI_WARNING} *ALERTA*: La web *{name}* está caída.\n"
                f"🔗 URL: `{url}`\n"
                f"📛 Error: {result.get('error', 'Código ' + str(result['status_code']))}"
            )
            context.bot.send_message(
                chat_id=user_id,
                text=alert_msg,
                parse_mode="MarkdownV2"
            )
    
    conn.commit()
    conn.close()

def send_status_alerts(context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM websites")
    users = cursor.fetchall()
    
    for (user_id,) in users:
        cursor.execute('''
            SELECT name, url, last_status FROM websites 
            WHERE user_id = ?
        ''', (user_id,))
        websites = cursor.fetchall()
        
        if not websites:
            continue
        
        message = f"{EMOJI_BELL} *Estado de tus webs* (Actualizado: {datetime.now().strftime('%H:%M:%S')}):\n\n"
        for name, url, status in websites:
            status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
            message += f"{status_emoji} *{name}*: `{url}`\n"
        
        try:
            context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="MarkdownV2",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error al enviar alerta a {user_id}: {e}")
    
    conn.close()

# Comandos del bot
@private_chat_only
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    update.message.reply_text(
        f"✨ *¡Hola {user.first_name}!* ✨\n\n"
        f"{EMOJI_USER} *Tu información*\n"
        f"{EMOJI_ID} ID: `{user.id}`\n"
        f"👤 Usuario: @{user.username if user.username else 'No tiene'}\n"
        f"{EMOJI_LANG} Idioma: {user.language_code or 'No detectado'}\n\n"
        f"🌐 *Monitor de Webs Privado*\n"
        f"• Añade páginas con /add <nombre> <url>\n"
        f"• Revisa tus sitios con /list\n"
        f"• Recibirás alertas automáticas cada minuto\n\n"
        f"📌 Ejemplo:\n"
        f"`/add MiWeb https://ejemplo.com`",
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

@private_chat_only
def add_website(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    args = context.args
    
    if len(args) < 2:
        update.message.reply_text(
            "ℹ️ Uso: /add <nombre> <url>\nEjemplo: /add Google https://google.com",
            parse_mode="MarkdownV2"
        )
        return
    
    name, url = " ".join(args[:-1]), args[-1]
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO websites (user_id, url, name) VALUES (?, ?, ?)",
        (user_id, url, name)
    )
    conn.commit()
    conn.close()
    
    update.message.reply_text(
        f"{EMOJI_ADD} *{name}* añadido a tu lista privada.",
        parse_mode="MarkdownV2"
    )

@private_chat_only
def list_websites(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, url, last_status, last_checked FROM websites WHERE user_id = ?",
        (user_id,)
    )
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        update.message.reply_text("📭 No tienes webs monitoreadas. Usa /add para añadir una.")
        return
    
    message = f"{EMOJI_LIST} *Tus webs monitoreadas:*\n\n"
    for name, url, status, checked in websites:
        status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
        message += f"{status_emoji} *{name}*\n🔗 `{url}`\n🕒 Última verificación: {checked or 'Nunca'}\n\n"
    
    update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
        disable_web_page_preview=True
    )

# Configuración del bot
def main():
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    
    # Tareas periódicas
    job_queue = updater.job_queue
    job_queue.run_repeating(monitor_websites, interval=CHECK_INTERVAL, first=0)
    job_queue.run_repeating(send_status_alerts, interval=ALERT_INTERVAL, first=0)
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()