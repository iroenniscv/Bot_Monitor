import logging
import sqlite3
import requests
from telegram import Update, Chat
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
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
REQUIRED_CHANNEL = "@monitorinfobots"  # Reemplaza con tu canal

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
EMOJI_BELL = "🔔"
EMOJI_BELL_SLASH = "🔕"
EMOJI_USER = "👤"
EMOJI_CHANNEL = "📢"

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
            response_time REAL,
            notifications_enabled BOOLEAN DEFAULT 1
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
    cursor.execute("SELECT id, url, name, notifications_enabled FROM websites")
    websites = cursor.fetchall()
    
    for website in websites:
        id, url, name, notifications_enabled = website
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
        
        if result["status"] == "DOWN" and notifications_enabled:
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

# Verificación de canal
async def is_user_member(user_id: int, context: CallbackContext) -> bool:
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error verificando membresía: {e}")
        return False

async def check_membership(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not await is_user_member(user_id, context):
        await update.message.reply_text(
            f"❌ Debes unirte a nuestro canal {REQUIRED_CHANNEL} para usar este bot.\n\n"
            f"Por favor únete y vuelve a intentar el comando.",
            parse_mode="Markdown"
        )
        return False
    return True

# Comandos del bot
async def start(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    user = update.effective_user
    welcome_msg = (
        f"👋 ¡Hola {user.first_name}! {EMOJI_USER}\n\n"
        f"📋 *Información de tu cuenta:*\n"
        f"- Nombre: {user.full_name}\n"
        f"- ID: {user.id}\n"
        f"- Usuario: @{user.username if user.username else 'N/A'}\n\n"
        f"🤖 Soy un bot de monitoreo de sitios web. Puedo avisarte cuando tus sitios web están caídos.\n\n"
        f"📢 *Importante:* Para usar este bot debes estar unido a: {REQUIRED_CHANNEL}\n\n"
        f"📝 Usa /help para ver los comandos disponibles"
    )
    await update.message.reply_text(welcome_msg, parse_mode="Markdown")

async def help_command(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    help_text = (
        f"{EMOJI_HELP} *COMANDOS DISPONIBLES*\n\n"
        f"/start - Muestra información de bienvenida\n"
        f"/help - Muestra esta ayuda\n"
        f"/add <nombre> <url> {EMOJI_ADD} - Añadir sitio web\n"
        f"O simplemente envía una URL y te guiaré\n"
        f"/list {EMOJI_LIST} - Mostrar sitios monitoreados\n"
        f"/status - Ver estado actual\n"
        f"/delete <id> {EMOJI_TRASH} - Eliminar un sitio\n"
        f"/monitor - Activar monitoreo automático\n"
        f"/stop - Detener monitoreo\n"
        f"/notifications <on/off> - Notificaciones\n\n"
        f"Ejemplo:\n`/add Google https://google.com`\n"
        f"O envía directamente:\n`https://google.com`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def add_website(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    args = context.args
    user_data = context.user_data
    
    # Flujo interactivo si se detectó URL previamente
    if 'detected_url' in user_data and not args:
        url = user_data['detected_url']
        name = update.message.text.strip()
        
        if len(name) < 2 or len(name) > 50:
            await update.message.reply_text("❌ El nombre debe tener entre 2 y 50 caracteres.")
            return
        
        # Validar URL
        if not re.match(r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url):
            await update.message.reply_text("❌ URL inválida. Debe comenzar con http:// o https://")
            return
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO websites (url, name) VALUES (?, ?)", (url, name))
            conn.commit()
            await update.message.reply_text(
                f"{EMOJI_ADD} *{name}* añadido al monitor:\n`{url}`",
                parse_mode="Markdown"
            )
            del user_data['detected_url']
        except sqlite3.IntegrityError:
            await update.message.reply_text("⚠️ Este sitio ya está siendo monitoreado")
        finally:
            conn.close()
        return
    
    # Flujo tradicional con comando /add
    if len(args) < 2:
        await update.message.reply_text(
            "ℹ️ Puedes:\n1. Usar /add <nombre> <url>\n"
            "2. O simplemente enviar una URL y te guiaré",
            parse_mode="Markdown"
        )
        return
    
    name = " ".join(args[:-1])
    url = args[-1]
    
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    
    if not re.match(r'^https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+', url):
        await update.message.reply_text("❌ URL inválida. Debe comenzar con http:// o https://")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        cursor.execute("INSERT INTO websites (url, name) VALUES (?, ?)", (url, name))
        conn.commit()
        await update.message.reply_text(
            f"{EMOJI_ADD} *{name}* añadido al monitor:\n`{url}`",
            parse_mode="Markdown"
        )
    except sqlite3.IntegrityError:
        await update.message.reply_text("⚠️ Este sitio ya está siendo monitoreado")
    finally:
        conn.close()

async def list_websites(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, url, last_status, last_checked, response_time, notifications_enabled FROM websites")
    websites = cursor.fetchall()
    conn.close()
    
    if not websites:
        await update.message.reply_text("ℹ️ No hay sitios monitoreados actualmente")
        return
    
    message = f"{EMOJI_LIST} *Sitios Monitoreados (ID - Nombre):*\n\n"
    for id, name, url, status, checked, resp_time, notifications_enabled in websites:
        status_emoji = EMOJI_UP if status == "UP" else EMOJI_DOWN
        time_str = f"{resp_time:.2f}s" if resp_time else "N/A"
        notification_status = f"{EMOJI_BELL} ON" if notifications_enabled else f"{EMOJI_BELL_SLASH} OFF"
        message += (
            f"{EMOJI_ID} *{id}* - {status_emoji} *{name}*\n"
            f"🔗 `{url}`\n"
            f"{EMOJI_TIME} {time_str} | 📅 {checked}\n"
            f"Notificaciones: {notification_status}\n\n"
        )
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def delete_website(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    if not context.args:
        await list_websites(update, context)
        await update.message.reply_text("\nℹ️ Usa: /delete <ID> para eliminar un sitio")
        return
    
    try:
        site_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número. Usa /list para ver los IDs")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM websites WHERE id = ?", (site_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ No se encontró un sitio con ese ID")
        conn.close()
        return
    
    site_name = result[0]
    cursor.execute("DELETE FROM websites WHERE id = ?", (site_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"{EMOJI_TRASH} Sitio eliminado correctamente:\n*{site_name}* (ID: {site_id})",
        parse_mode="Markdown"
    )

async def status(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    loading_msg = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"{EMOJI_LOADING} Verificando estado de los sitios web...",
        parse_mode="Markdown"
    )
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, name FROM websites")
    websites = cursor.fetchall()
    
    if not websites:
        await context.bot.edit_message_text(
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
    
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id,
        message_id=loading_msg.message_id,
        text=message,
        parse_mode="Markdown"
    )

async def monitor_command(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    if 'job' in context.chat_data:
        await update.message.reply_text("ℹ️ El monitoreo automático ya está activado")
        return
    
    job = context.job_queue.run_repeating(
        monitor_websites,
        interval=CHECK_INTERVAL,
        first=0,
        context=update.message.chat_id
    )
    context.chat_data['job'] = job
    
    await update.message.reply_text(
        f"✅ Monitoreo automático activado\n"
        f"Se verificará cada {CHECK_INTERVAL} segundos"
    )

async def stop_command(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    if 'job' not in context.chat_data:
        await update.message.reply_text("ℹ️ El monitoreo automático no está activado")
        return
    
    context.chat_data['job'].schedule_removal()
    del context.chat_data['job']
    
    await update.message.reply_text("⏹️ Monitoreo automático detenido")

async def toggle_notifications(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    if not context.args:
        await update.message.reply_text("ℹ️ Uso: /notifications <on/off> [id]\nSi no se especifica ID, afecta a todos")
        return
    
    action = context.args[0].lower()
    site_id = int(context.args[1]) if len(context.args) > 1 else None
    
    if action not in ['on', 'off']:
        await update.message.reply_text("❌ Opción inválida. Usa 'on' u 'off'")
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        if site_id:
            cursor.execute("SELECT name FROM websites WHERE id = ?", (site_id,))
            result = cursor.fetchone()
            
            if not result:
                await update.message.reply_text("❌ No se encontró un sitio con ese ID")
                return
            
            cursor.execute(
                "UPDATE websites SET notifications_enabled = ? WHERE id = ?",
                (1 if action == 'on' else 0, site_id)
            )
            conn.commit()
            
            await update.message.reply_text(
                f"{EMOJI_BELL if action == 'on' else EMOJI_BELL_SLASH} "
                f"Notificaciones {'activadas' if action == 'on' else 'desactivadas'} "
                f"para el sitio *{result[0]}* (ID: {site_id})",
                parse_mode="Markdown"
            )
        else:
            cursor.execute(
                "UPDATE websites SET notifications_enabled = ?",
                (1 if action == 'on' else 0,)
            )
            conn.commit()
            
            await update.message.reply_text(
                f"{EMOJI_BELL if action == 'on' else EMOJI_BELL_SLASH} "
                f"Notificaciones {'activadas' if action == 'on' else 'desactivadas'} "
                "para *todos* los sitios monitoreados",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error al cambiar notificaciones: {e}")
        await update.message.reply_text("❌ Ocurrió un error al actualizar las notificaciones")
    finally:
        conn.close()

async def message_handler(update: Update, context: CallbackContext):
    if not await check_membership(update, context):
        return
    
    text = update.message.text
    urls = re.findall(r'https?://[^\s]+', text)
    
    if urls and not text.startswith('/'):
        context.user_data['detected_url'] = urls[0]  # Tomamos la primera URL
        await update.message.reply_text(
            f"🔍 He detectado una URL en tu mensaje:\n\n{urls[0]}\n\n"
            "Por favor responde con el nombre que quieres darle a este sitio web "
            "(ejemplo: 'Mi Sitio Web')",
            parse_mode="Markdown"
        )

# Servidor web para Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot de monitoreo activo", 200

def run_flask():
    app.run(host='0.0.0.0', port=PORT)

# Inicialización del bot
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    updater = Updater(TOKEN)
    dp = updater.dispatcher
    
    # Handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("add", add_website))
    dp.add_handler(CommandHandler("list", list_websites))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("delete", delete_website))
    dp.add_handler(CommandHandler("monitor", monitor_command))
    dp.add_handler(CommandHandler("stop", stop_command))
    dp.add_handler(CommandHandler("notifications", toggle_notifications))
    
    # Handler para mensajes regulares
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
    
    # Tarea periódica
    job_queue = updater.job_queue
    job_queue.run_repeating(monitor_websites, interval=CHECK_INTERVAL, first=0)
    
    # Iniciar bot
    updater.start_polling()
    logger.info("Bot iniciado en modo polling")
    updater.idle()

if __name__ == "__main__":
    main()