import json
import time
import re
import logging
from collections import defaultdict, deque
from telegram import (
    Update,
    ChatPermissions,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ===== LOGGING (ANTI CRASH) =====
logging.basicConfig(level=logging.INFO)

TOKEN = "8277850902:AAEqZvdZpGIvVQxQkpdD782K-qxcu1EVNbs"
DATA_FILE = "data.json"

# ===== DATABASE =====
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
    except:
        data = {}

    data.setdefault("global_bad_words", ["anjing", "babi"])
    data.setdefault("chats", {})

    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

data = load_data()

def get_chat_cfg(chat_id):
    cid = str(chat_id)
    if cid not in data["chats"]:
        data["chats"][cid] = {
            "bad_words": data["global_bad_words"][:],
            "warnings": {},
            "settings": {
                "sensor": True,
                "anti_link": True,
                "anti_caps": True,
                "anti_repeat": True,
                "mute_on_3": True,
                "kick_on_5": True
            }
        }
    return data["chats"][cid]

# ===== RATE LIMIT =====
user_msgs = defaultdict(lambda: deque(maxlen=5))

# ===== CEK ADMIN =====
async def is_admin(chat, user_id):
    try:
        m = await chat.get_member(user_id)
        return m.status in ["administrator", "creator"]
    except:
        return False

# ===== DELETE AMAN =====
async def safe_delete(msg):
    try:
        await msg.delete()
    except:
        pass

# ===== MODERASI =====
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    if msg.chat.type == "private":
        return

    chat = msg.chat
    user = msg.from_user
    text = msg.text
    text_l = text.lower()

    cfg = get_chat_cfg(chat.id)

    # skip admin
    if await is_admin(chat, user.id):
        return

    # ===== ANTI SPAM =====
    now = time.time()
    q = user_msgs[user.id]
    q.append(now)

    if len(q) >= 5 and (q[-1] - q[0]) < 3:
        await safe_delete(msg)
        return

    # ===== ANTI REPEAT =====
    if cfg["settings"]["anti_repeat"]:
        last = context.user_data.get("last")
        if last == text_l:
            await safe_delete(msg)
            return
        context.user_data["last"] = text_l

    # ===== ANTI CAPS =====
    if cfg["settings"]["anti_caps"]:
        if text.isupper() and len(text) > 6:
            await safe_delete(msg)
            await chat.send_message(f"🔠 Jangan caps {user.first_name}")
            return

    # ===== SENSOR KATA =====
    if cfg["settings"]["sensor"]:
        for w in cfg["bad_words"]:
            if re.search(rf"\b{re.escape(w)}\b", text_l):

                await safe_delete(msg)

                uid = str(user.id)
                cfg["warnings"][uid] = cfg["warnings"].get(uid, 0) + 1
                warn = cfg["warnings"][uid]
                save_data(data)

                await chat.send_message(
                    f"⚠️ {user.first_name}\nWarning: {warn}/5"
                )

                # ===== MUTE =====
                if warn == 3 and cfg["settings"]["mute_on_3"]:
                    try:
                        await chat.restrict_member(
                            user.id,
                            ChatPermissions(can_send_messages=False),
                            until_date=int(time.time()) + 60
                        )
                        await chat.send_message("🔇 Dimute 1 menit")
                    except:
                        pass

                # ===== KICK =====
                if warn >= 5 and cfg["settings"]["kick_on_5"]:
                    try:
                        await chat.ban_member(user.id)
                        await chat.send_message("💀 Dikick!")
                    except:
                        pass

                return

    # ===== ANTI LINK =====
    if cfg["settings"]["anti_link"]:
        if "http://" in text_l or "https://" in text_l or "t.me/" in text_l:
            await safe_delete(msg)
            await chat.send_message(f"🚫 Link dilarang {user.first_name}")

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📛 Kata", callback_data="words")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Link", callback_data="link")],
        [InlineKeyboardButton("🔠 Caps", callback_data="caps")],
        [InlineKeyboardButton("🔁 Repeat", callback_data="repeat")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])

# ===== COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot aktif", reply_markup=menu())

# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat = q.message.chat
    cfg = get_chat_cfg(chat.id)

    if q.data == "words":
        await q.message.reply_text("\n".join(cfg["bad_words"]))

    elif q.data == "settings":
        await q.message.reply_text("⚙️ Settings", reply_markup=settings_menu())

    elif q.data == "link":
        cfg["settings"]["anti_link"] = not cfg["settings"]["anti_link"]
        save_data(data)
        await q.message.reply_text(f"Link: {cfg['settings']['anti_link']}")

    elif q.data == "caps":
        cfg["settings"]["anti_caps"] = not cfg["settings"]["anti_caps"]
        save_data(data)
        await q.message.reply_text(f"Caps: {cfg['settings']['anti_caps']}")

    elif q.data == "repeat":
        cfg["settings"]["anti_repeat"] = not cfg["settings"]["anti_repeat"]
        save_data(data)
        await q.message.reply_text(f"Repeat: {cfg['settings']['anti_repeat']}")

    elif q.data == "back":
        await q.message.reply_text("Menu", reply_markup=menu())

# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))

print("🚀 BOT FINAL JALAN")
app.run_polling()
