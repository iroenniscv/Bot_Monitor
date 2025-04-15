import logging
import sqlite3
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Chat
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
REQUIRED_CHANNEL = "@monitorinfobots"  # Canal requerido para usar el bot

# Emojis (se mantienen los mismos)
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

# ... (el resto de las configuraciones iniciales se mantienen igual)

# Nueva función para verificar membresía en canal
async def is_user_member(user_id: int, context: CallbackContext) -> bool:
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error verificando membresía: {e}")
        return False

# Mensaje de bienvenida mejorado
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    chat = update.effective_chat
    
    welcome_msg = (
        f"👋 ¡Hola {user.first_name}! {EMOJI_USER}\n\n"
        f"📋 *Información de tu cuenta:*\n"
        f"- Nombre: {user.full_name}\n"
        f"- ID: {user.id}\n"
        f"- Usuario: @{user.username if user.username else 'N/A'}\n\n"
        f"🤖 Soy un bot de monitoreo de sitios web. Puedo avisarte cuando tus sitios web están caídos.\n\n"
        f"📢 *Importante:* Para usar este bot debes unirte a nuestro canal oficial: {REQUIRED_CHANNEL}\n\n"
        f"📝 Usa /help para ver los comandos disponibles"
    )
    
    update.message.reply_text(welcome_msg, parse_mode="Markdown")
    
    # Verificar si el usuario está en el canal requerido
    context.job_queue.run_once(
        lambda ctx: check_channel_membership(ctx, user.id, chat.id),
        2  # Pequeño retraso para evitar flood
    )

async def check_channel_membership(context: CallbackContext, user_id: int, chat_id: int):
    if not await is_user_member(user_id, context):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Para usar este bot debes unirte a nuestro canal: {REQUIRED_CHANNEL}\n\n"
                 f"Por favor únete y vuelve a intentarlo.",
            parse_mode="Markdown"
        )
        return False
    return True

# Middleware para verificar membresía antes de procesar comandos
async def check_membership(update: Update, context: CallbackContext, next_handler):
    user_id = update.effective_user.id
    
    if not await is_user_member(user_id, context):
        await update.message.reply_text(
            f"❌ Debes unirte a nuestro canal {REQUIRED_CHANNEL} para usar este bot.\n\n"
            f"Por favor únete y vuelve a intentar el comando.",
            parse_mode="Markdown"
        )
        return
    
    return await next_handler(update, context)

# Modificación del handler de mensajes para detectar URLs automáticamente
def message_handler(update: Update, context: CallbackContext):
    # Primero verificar membresía
    if not check_membership(update, context, lambda u, c: True):
        return
    
    text = update.message.text
    urls = re.findall(r'https?://[^\s]+', text)
    
    if urls:
        context.user_data['detected_urls'] = urls
        update.message.reply_text(
            f"🔍 He detectado {len(urls)} URL(s) en tu mensaje:\n\n" +
            "\n".join([f"{i+1}. {url}" for i, url in enumerate(urls)]) +
            "\n\nPor favor responde con el nombre que quieres darle a este sitio web (ejemplo: 'Mi Sitio Web').",
            parse_mode="Markdown"
        )
    else:
        # Si el mensaje es texto plano (no comando) y parece ser un nombre para la URL
        if 'detected_urls' in context.user_data and not text.startswith('/'):
            url = context.user_data['detected_urls'][0]  # Tomamos la primera URL detectada
            name = text.strip()
            
            # Validar nombre
            if len(name) < 2 or len(name) > 50:
                update.message.reply_text("❌ El nombre debe tener entre 2 y 50 caracteres.")
                return
            
            # Proceder a agregar el sitio
            context.args = [name, url]  # Simulamos los argumentos del comando /add
            add_website(update, context)
            del context.user_data['detected_urls']

# Modificación del comando /add para usar el flujo interactivo
def add_website(update: Update, context: CallbackContext):
    # Verificar membresía primero
    if not check_membership(update, context, lambda u, c: True):
        return
    
    # Si no hay argumentos pero hay URLs detectadas
    if not context.args and 'detected_urls' in context.user_data:
        update.message.reply_text(
            "Por favor responde con el nombre que quieres darle a este sitio web.",
            parse_mode="Markdown"
        )
        return
    
    # Resto de la función original...
    args = context.args
    if len(args) < 2:
        update.message.reply_text(
            "ℹ️ Puedes:\n"
            "1. Escribir /add <nombre> <url>\n"
            "2. O simplemente enviar una URL y te guiaré para agregarla",
            parse_mode="Markdown"
        )
        return
    
    # ... (resto de la función add_website original)

# Modificar todos los handlers para incluir la verificación de membresía
def wrap_command(handler):
    async def wrapped(update: Update, context: CallbackContext):
        return await check_membership(update, context, handler)
    return wrapped

# Inicialización del bot (modificada para incluir el nuevo handler)
def main():
    # ... (configuración inicial igual)
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Handlers con verificación de membresía
    dp.add_handler(CommandHandler("start", wrap_command(start)))
    dp.add_handler(CommandHandler("help", wrap_command(help_command)))
    dp.add_handler(CommandHandler("add", wrap_command(add_website)))
    dp.add_handler(CommandHandler("list", wrap_command(list_websites)))
    dp.add_handler(CommandHandler("status", wrap_command(status)))
    dp.add_handler(CommandHandler("delete", wrap_command(delete_website)))
    dp.add_handler(CommandHandler("monitor", wrap_command(monitor_command)))
    dp.add_handler(CommandHandler("stop", wrap_command(stop_command)))
    dp.add_handler(CommandHandler("notifications", wrap_command(toggle_notifications)))
    
    # Handler para mensajes regulares (detectar URLs)
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, wrap_command(message_handler)))
    
    # ... (resto del código main igual)

if __name__ == "__main__":
    main()