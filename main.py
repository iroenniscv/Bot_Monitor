import logging
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de la conversación
API_ID, API_HASH, PHONE_NUMBER, CODE, PASSWORD = range(5)

# Diccionario para almacenar datos temporales de usuarios
user_data_temp = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra información del usuario al usar /start"""
    user = update.effective_user
    text = (
        f"👋 ¡Hola, {user.first_name}!\n\n"
        f"🆔 ID de usuario: `{user.id}`\n"
        f"👤 Nombre de usuario: @{user.username}\n"
        f"🗣 Nombre completo: {user.full_name}\n"
        f"🌐 Idioma: {user.language_code}\n\n"
        "Usa /generate para crear tu sesión de Telethon.\n"
        "⚠️ *No compartas tu sesión con nadie.*"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de generación de sesión"""
    await update.message.reply_text("Por favor, ingresa tu API_ID:")
    return API_ID

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el API_ID del usuario"""
    try:
        api_id = int(update.message.text)
        context.user_data['api_id'] = api_id
        await update.message.reply_text("Ahora, ingresa tu API_HASH:")
        return API_HASH
    except ValueError:
        await update.message.reply_text("⚠️ El API_ID debe ser un número. Intenta nuevamente.")
        return API_ID

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el API_HASH del usuario"""
    api_hash = update.message.text.strip()
    context.user_data['api_hash'] = api_hash
    await update.message.reply_text("Ingresa tu número de teléfono (incluye el código de país, por ejemplo, +521234567890):")
    return PHONE_NUMBER

async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el número de teléfono del usuario y envía el código de verificación"""
    phone = update.message.text.strip()
    context.user_data['phone'] = phone
    api_id = context.user_data['api_id']
    api_hash = context.user_data['api_hash']

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        try:
            sent = await client.send_code_request(phone)
            context.user_data['client'] = client
            context.user_data['phone_code_hash'] = sent.phone_code_hash
            await update.message.reply_text("Se ha enviado un código de verificación a tu Telegram. Por favor, ingresa el código:")
            return CODE
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error al enviar el código: {e}")
            await client.disconnect()
            return ConversationHandler.END
    else:
        await update.message.reply_text("Ya estás autorizado.")
        await client.disconnect()
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el código ingresado por el usuario"""
    code = update.message.text.strip()
    client = context.user_data['client']
    phone = context.user_data['phone']
    phone_code_hash = context.user_data['phone_code_hash']

    try:
        await client.sign_in(phone, phone_code_hash, code)
        session_string = client.session.save()
        await update.message.reply_text(
            f"✅ ¡Sesión generada con éxito!\n\n"
            f"`{session_string}`\n\n"
            "⚠️ *Guarda esta cadena en un lugar seguro y no la compartas con nadie.*",
            parse_mode='Markdown'
        )
        await client.disconnect()
        return ConversationHandler.END
    except SessionPasswordNeededError:
        await update.message.reply_text("Tu cuenta tiene habilitada la verificación en dos pasos. Por favor, ingresa tu contraseña:")
        return PASSWORD
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error al verificar el código: {e}")
        await client.disconnect()
        return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica la contraseña de verificación en dos pasos"""
    password = update.message.text.strip()
    client = context.user_data['client']

    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await update.message.reply_text(
            f"✅ ¡Sesión generada con éxito!\n\n"
            f"`{session_string}`\n\n"
            "⚠️ *Guarda esta cadena en un lugar seguro y no la compartas con nadie.*",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Error al verificar la contraseña: {e}")
    finally:
        await client.disconnect()
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación"""
    await update.message.reply_text("Proceso cancelado. Usa /generate para intentarlo nuevamente.")
    return ConversationHandler.END

def main():
    """Inicia el bot"""
    # Reemplaza 'TU_TOKEN_AQUI' con el token de tu bot
    application = Application.builder().token('7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', generate)],
        states={
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
            API_HASH: [MessageHandler(filters0