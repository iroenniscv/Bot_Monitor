import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import logging

# Configuración básica de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados para la conversación
GETTING_API_ID, GETTING_API_HASH = range(2)

class SessionGeneratorBot:
    def __init__(self, token):
        self.token = token
        self.user_data = {}
        
        # Configura la aplicación
        self.application = Application.builder().token(self.token).build()
        
        # Maneja los comandos
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(CommandHandler('generate', self.start_generate))
        
        # Maneja los callbacks de los botones
        self.application.add_handler(CallbackQueryHandler(self.button))
        
        # Maneja los mensajes de texto
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Maneja errores
        self.application.add_error_handler(self.error_handler)
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Envía un mensaje de bienvenida cuando se usa el comando /start"""
        user = update.effective_user
        welcome_text = (
            f"Hola {user.first_name}!\n\n"
            "Soy un bot generador de sesiones de Telethon.\n\n"
            "Para generar una sesión, usa el comando /generate\n\n"
            "⚠️ **ADVERTENCIA**: Nunca compartas tu sesión con nadie."
        )
        
        await update.message.reply_text(welcome_text)
    
    async def start_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia el proceso de generación de sesión"""
        chat_id = update.effective_chat.id
        self.user_data[chat_id] = {}
        
        await update.message.reply_text(
            "Vamos a generar una sesión de Telethon.\n\n"
            "Por favor, envía tu **API_ID** (solo números):",
            parse_mode='Markdown'
        )
        
        return GETTING_API_ID
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los mensajes durante la conversación"""
        chat_id = update.effective_chat.id
        text = update.message.text
        
        if chat_id not in self.user_data:
            return
        
        if 'state' not in self.user_data[chat_id]:
            # Si estamos esperando el API_ID
            try:
                api_id = int(text)
                self.user_data[chat_id]['api_id'] = api_id
                self.user_data[chat_id]['state'] = GETTING_API_HASH
                
                await update.message.reply_text(
                    "✅ API_ID recibido correctamente.\n\n"
                    "Ahora envía tu **API_HASH**:",
                    parse_mode='Markdown'
                )
            except ValueError:
                await update.message.reply_text("⚠️ El API_ID debe ser un número. Por favor, inténtalo de nuevo.")
        elif self.user_data[chat_id]['state'] == GETTING_API_HASH:
            # Si estamos esperando el API_HASH
            self.user_data[chat_id]['api_hash'] = text
            self.user_data[chat_id]['state'] = None
            
            # Generamos la sesión
            await self.generate_session(update, chat_id)
    
    async def generate_session(self, update: Update, chat_id: int):
        """Genera la sesión de Telethon"""
        user_data = self.user_data.get(chat_id, {})
        
        if not user_data or 'api_id' not in user_data or 'api_hash' not in user_data:
            await update.message.reply_text("⚠️ Error: Datos incompletos. Por favor, inicia el proceso nuevamente con /generate")
            return
        
        try:
            api_id = user_data['api_id']
            api_hash = user_data['api_hash']
            
            with TelegramClient(StringSession(), api_id, api_hash) as client:
                session_string = client.session.save()
                
                response_text = (
                    "✅ **Sesión generada con éxito!**\n\n"
                    "🔐 **Tu sesión es:**\n"
                    f"`{session_string}`\n\n"
                    "⚠️ **ADVERTENCIA IMPORTANTE:**\n"
                    "- Nunca compartas esta cadena con nadie\n"
                    "- Quien tenga acceso a esta cadena puede controlar tu cuenta\n"
                    "- Si crees que tu sesión ha sido comprometida, revócala inmediatamente\n\n"
                    "Guarda esta sesión en un lugar seguro."
                )
                
                await update.message.reply_text(response_text, parse_mode='Markdown')
                
        except Exception as e:
            error_msg = f"⚠️ Error al generar la sesión: {str(e)}"
            logger.error(error_msg)
            await update.message.reply_text(error_msg)
        
        # Limpiamos los datos del usuario
        if chat_id in self.user_data:
            del self.user_data[chat_id]
    
    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los callbacks de los botones"""
        query = update.callback_query
        await query.answer()
        
        if query.data == 'generate':
            await self.start_generate(update, context)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Maneja los errores"""
        logger.error(msg="Error en el bot:", exc_info=context.error)
        
        if update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Ocurrió un error inesperado. Por favor, inténtalo de nuevo."
            )
    
    def run(self):
        """Inicia el bot"""
        self.application.run_polling()

if __name__ == '__main__':
    # Configura tu token de bot aquí
    BOT_TOKEN = '7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8'
    
    bot = SessionGeneratorBot(BOT_TOKEN)
    bot.run()