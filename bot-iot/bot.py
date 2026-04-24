from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio
import random

TOKEN = "8277850902:AAG5dLPN2gSBHpd7bHOT9_m_vDlV7Nmr7k8"

gerak_aktif = False
users = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users.add(update.effective_chat.id)
    await update.message.reply_text("Halo! Bot kamu sudah aktif 👍")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot berjalan normal ✅")

async def gerak_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global gerak_aktif
    gerak_aktif = True
    await update.message.reply_text("Sensor gerak AKTIF 🚨")

async def gerak_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global gerak_aktif
    gerak_aktif = False
    await update.message.reply_text("Sensor gerak NONAKTIF ❌")

# 🔥 background task
async def deteksi_gerak(context: ContextTypes.DEFAULT_TYPE):
    if gerak_aktif:
        gerakan = random.choice([True, False])
        if gerakan:
            for user in users:
                await context.bot.send_message(chat_id=user, text="⚠️ Terdeteksi gerakan!")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("status", status))
app.add_handler(CommandHandler("gerak_on", gerak_on))
app.add_handler(CommandHandler("gerak_off", gerak_off))

# 🔥 jalan tiap 5 detik
app.job_queue.run_repeating(deteksi_gerak, interval=5)

print("Bot berjalan...")
app.run_polling()
