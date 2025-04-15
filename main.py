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
    # Limpiar datos previos
    context.user_data.clear()
    await update.message.reply_text("Por favor, ingresa tu API_ID:")
    return API_ID

async def get_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el API_ID del usuario"""
    try:
        api_id = int(update.message.text)
        if api_id <= 0:
            raise ValueError
        context.user_data['api_id'] = api_id
        await update.message.reply_text("Ahora, ingresa tu API_HASH:")
        return API_HASH
    except ValueError:
        await update.message.reply_text("⚠️ El API_ID debe ser un número positivo. Intenta nuevamente.")
        return API_ID

async def get_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el API_HASH del usuario"""
    api_hash = update.message.text.strip()
    if len(api_hash) < 10:  # Validación básica
        await update.message.reply_text("⚠️ El API_HASH parece inválido. Intenta nuevamente.")
        return API_HASH
        
    context.user_data['api_hash'] = api_hash
    await update.message.reply_text(
        "Ingresa tu número de teléfono en formato internacional:\n"
        "(Ejemplo: +521234567890)"
    )
    return PHONE_NUMBER

async def get_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Obtiene el número de teléfono del usuario y envía el código de verificación"""
    phone = update.message.text.strip()
    if not phone.startswith('+'):
        await update.message.reply_text("⚠️ El número debe incluir código de país (Ejemplo: +521234567890)")
        return PHONE_NUMBER

    context.user_data['phone'] = phone
    
    try:
        client = TelegramClient(StringSession(), context.user_data['api_id'], context.user_data['api_hash'])
        await client.connect()
        
        if await client.is_user_authorized():
            await update.message.reply_text("⚠️ Ya hay una sesión activa para este número.")
            await client.disconnect()
            return ConversationHandler.END
            
        sent = await client.send_code_request(phone)
        context.user_data['client'] = client
        context.user_data['phone_code_hash'] = sent.phone_code_hash
        
        await update.message.reply_text(
            "📲 Se ha enviado un código de verificación a tu Telegram.\n"
            "Por favor, ingresa el código recibido (formato: 1 2 3 4 5):"
        )
        return CODE
        
    except Exception as e:
        logger.error(f"Error en get_phone_number: {str(e)}")
        await update.message.reply_text(f"⚠️ Error al enviar el código: {str(e)}")
        if 'client' in context.user_data:
            await context.user_data['client'].disconnect()
        return ConversationHandler.END

async def get_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica el código ingresado por el usuario"""
    code = update.message.text.strip().replace(' ', '')  # Elimina espacios si los puso
    
    if not code.isdigit() or len(code) != 5:
        await update.message.reply_text("⚠️ El código debe tener 5 dígitos numéricos. Intenta nuevamente.")
        return CODE

    client = context.user_data['client']
    
    try:
        # Versión corregida del sign_in con parámetros nombrados
        await client.sign_in(
            phone=context.user_data['phone'],
            code=code,
            phone_code_hash=context.user_data['phone_code_hash']
        )
        
        session_string = client.session.save()
        await update.message.reply_text(
            "✅ ¡Sesión generada con éxito!\n\n"
            f"`{session_string}`\n\n"
            "⚠️ *Guarda esta cadena en un lugar seguro y no la compartas con nadie.*\n"
            "Es válida hasta que hagas logout manualmente.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
        
    except SessionPasswordNeededError:
        await update.message.reply_text(
            "🔒 Tu cuenta tiene verificación en dos pasos.\n"
            "Por favor, ingresa tu contraseña:"
        )
        return PASSWORD
        
    except Exception as e:
        logger.error(f"Error en get_code: {str(e)}")
        await update.message.reply_text(f"⚠️ Error al verificar el código: {str(e)}")
        return await cleanup_session(context)

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verifica la contraseña de verificación en dos pasos"""
    password = update.message.text.strip()
    client = context.user_data['client']
    
    try:
        await client.sign_in(password=password)
        session_string = client.session.save()
        await update.message.reply_text(
            "✅ ¡Sesión generada con éxito!\n\n"
            f"`{session_string}`\n\n"
            "⚠️ *Guarda esta cadena en un lugar seguro y no la compartas con nadie.*\n"
            "Es válida hasta que hagas logout manualmente.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error en get_password: {str(e)}")
        await update.message.reply_text(f"⚠️ Error al verificar la contraseña: {str(e)}")
        return await cleanup_session(context)

async def cleanup_session(context: ContextTypes.DEFAULT_TYPE):
    """Limpia la sesión y desconecta el cliente"""
    if 'client' in context.user_data:
        await context.user_data['client'].disconnect()
        del context.user_data['client']
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación"""
    await cleanup_session(context)
    await update.message.reply_text("❌ Proceso cancelado. Usa /generate para intentarlo nuevamente.")
    return ConversationHandler.END

def main():
    """Inicia el bot"""
    application = Application.builder().token('7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8').build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('generate', generate)],
        states={
            API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_id)],
            API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_api_hash)],
            PHONE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone_number)],
            CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_code)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(conv_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()