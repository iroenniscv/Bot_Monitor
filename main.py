from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)
# ... los imports anteriores se mantienen

# Estados
GETTING_API_ID, GETTING_API_HASH = range(2)

class SessionGeneratorBot:
    def __init__(self, token):
        self.token = token
        self.user_data = {}
        self.application = Application.builder().token(self.token).build()

        # Conversación para generación
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('generate', self.start_generate)],
            states={
                GETTING_API_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_api_id)],
                GETTING_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_api_hash)],
            },
            fallbacks=[],
        )

        # Agrega handlers
        self.application.add_handler(CommandHandler('start', self.start))
        self.application.add_handler(conv_handler)
        self.application.add_handler(CallbackQueryHandler(self.button))
        self.application.add_error_handler(self.error_handler)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"Hola {user.first_name}!\n\n"
            "Soy un bot generador de sesiones de Telethon.\n\n"
            "Usa /generate para comenzar."
        )

    async def start_generate(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        self.user_data[chat_id] = {}
        await update.message.reply_text("Envía tu API_ID (solo números):")
        return GETTING_API_ID

    async def get_api_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text

        try:
            self.user_data[chat_id]['api_id'] = int(text)
            await update.message.reply_text("✅ API_ID recibido. Ahora envía tu API_HASH:")
            return GETTING_API_HASH
        except ValueError:
            await update.message.reply_text("⚠️ El API_ID debe ser un número. Intenta nuevamente.")
            return GETTING_API_ID

    async def get_api_hash(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        self.user_data[chat_id]['api_hash'] = update.message.text

        # Genera la sesión
        await self.generate_session(update, chat_id)
        return ConversationHandler.END

    async def generate_session(self, update: Update, chat_id: int):
        user_data = self.user_data.get(chat_id, {})
        if not user_data or 'api_id' not in user_data or 'api_hash' not in user_data:
            await update.message.reply_text("⚠️ Datos incompletos. Usa /generate para reiniciar.")
            return

        try:
            with TelegramClient(StringSession(), user_data['api_id'], user_data['api_hash']) as client:
                session_string = client.session.save()
                await update.message.reply_text(
                    f"✅ Sesión generada:\n`{session_string}`\n\nGuárdala bien.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error al generar la sesión: {e}")

        self.user_data.pop(chat_id, None)

    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        if update.callback_query.data == 'generate':
            await self.start_generate(update, context)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error("Error:", exc_info=context.error)
        if update and update.effective_message:
            await update.effective_message.reply_text("⚠️ Ocurrió un error inesperado.")

    def run(self):
        self.application.run_polling()