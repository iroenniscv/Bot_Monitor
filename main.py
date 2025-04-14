import logging
import sqlite3
import requests
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime

# Configuración
TOKEN = "7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8"  # Reemplázalo
DB_NAME = "monitor.db"
CHECK_INTERVAL = 60  # 1 minuto (en segundos) para alertas
ALERT_INTERVAL = 60  # Intervalo de notificaciones (60 segundos)

# Emojis
EMOJI_UP = "🟢"
EMOJI_DOWN = "🔴"
EMOJI_WARNING = "⚠️"
EMOJI_LIST = "📋"
EMOJI_ADD = "➕"
EMOJI_BELL = "🔔"

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Base de datos
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            name TEXT NOT NULL,
            last_status TEXT,
            last_checked TEXT
        )
    """)
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

def send_status_alerts(context: CallbackContext):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id FROM websites")
    users = cursor.fetchall()
    
    for (user_id,) in users:
        cursor.execute("""
            SELECT name, url, last_status FROM websites 
            WHERE user_id = ?
        """, (user_id,))
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
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error al enviar alerta a {user_id}: {e}")
    
    conn.close()

# Comando /start (mejorado)
@private_chat_only
def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    update.message.reply_text(
        f"✨ *¡Hola {user.first_name}!* ✨\n\n"
        f"🔔 Ahora recibirás actualizaciones cada *1 minuto* sobre el estado de tus webs.\n\n"
        f"📌 Usa /add para añadir una nueva página.\n"
        f"📋 Usa /list para ver tus sitios monitoreados.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

# (Los comandos /add y /list permanecen igual que en el código anterior)

# Configuración del bot
def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Comandos
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    
    # Tareas periódicas
    job_queue = updater.job_queue
    job_queue.run_repeating(
        monitor_websites, 
        interval=CHECK_INTERVAL, 
        first=0
    )
    job_queue.run_repeating(
        send_status_alerts, 
        interval=ALERT_INTERVAL, 
        first=0
    )
    
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
