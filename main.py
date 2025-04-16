import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.utils.markdown import hbold
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import F
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("7725269349:AAFHd6AYWbFkUJ5OjSe2CjenMMjosD_JvD8")

bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Keyboard builder
def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="Hola")
    builder.button(text="Ayuda")
    builder.button(text="Foto")
    builder.button(text="Audio")
    builder.button(text="Sticker")
    builder.button(text="Documento")
    builder.button(text="Ubicación")
    builder.button(text="Contacto")
    builder.button(text="Video")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)

# Handlers
@dp.message(F.text == "/start")
async def start(message: Message):
    await message.answer(f"Hola, {hbold(message.from_user.first_name)}!", reply_markup=main_keyboard())

@dp.message(F.text.lower() == "hola")
async def hola(message: Message):
    await message.answer("¡Hola! ¿En qué puedo ayudarte?")

@dp.message(F.text.lower() == "ayuda")
async def ayuda(message: Message):
    await message.answer("Este es un bot de prueba. Puedes enviarme fotos, audios, stickers, documentos, ubicación, contactos y videos.")

@dp.message(F.text.lower() == "foto")
async def send_photo(message: Message):
    await bot.send_photo(message.chat.id, photo="https://placekitten.com/400/300", caption="Aquí tienes un gatito")

@dp.message(F.text.lower() == "audio")
async def send_audio(message: Message):
    await bot.send_audio(message.chat.id, audio="https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", caption="Aquí tienes un audio")

@dp.message(F.text.lower() == "sticker")
async def send_sticker(message: Message):
    await bot.send_sticker(message.chat.id, sticker="CAACAgIAAxkBAAEB0QJkZUSRAAGnZ0d6ZTujN6PvTeyx_gAC7AIAArVx2Uos37UEVXsEOi8E")

@dp.message(F.text.lower() == "documento")
async def send_document(message: Message):
    await bot.send_document(message.chat.id, document="https://file-examples.com/storage/fec0c01b3fd91c1e0f4b4bd/2017/10/file-sample_150kB.pdf", caption="Aquí tienes un documento")

@dp.message(F.text.lower() == "ubicación")
async def send_location(message: Message):
    await bot.send_location(message.chat.id, latitude=19.4326, longitude=-99.1332)

@dp.message(F.text.lower() == "contacto")
async def send_contact(message: Message):
    await bot.send_contact(message.chat.id, phone_number="+525512345678", first_name="Juan")

@dp.message(F.text.lower() == "video")
async def send_video(message: Message):
    await bot.send_video(message.chat.id, video="http://techslides.com/demos/sample-videos/small.mp4", caption="Aquí tienes un video")

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))