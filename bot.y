import json
import time
import re
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
    data.setdefault("chats", {})  # per chat config

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
                "welcome": True,
                "mute_on_3": True,
                "kick_on_5": True
            }
        }
    return data["chats"][cid]

# ===== RATE LIMIT (ANTI SPAM) =====
user_msgs = defaultdict(lambda: deque(maxlen=5))

# ===== ADMIN CHECK =====
async def is_admin(chat, user_id):
    m = await chat.get_member(user_id)
    return m.status in ["administrator", "creator"]

# ===== MODERATION CORE =====
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat = msg.chat
    user = msg.from_user
    text = msg.text
    text_l = text.lower()
    cfg = get_chat_cfg(chat.id)

    # skip admin
    if await is_admin(chat, user.id):
        return

    # rate limit (5 msg / 3 detik)
    now = time.time()
    q = user_msgs[user.id]
    q.append(now)
    if len(q) >= 5 and (q[-1] - q[0]) < 3:
        await msg.delete()
        return

    # anti repeat
    if cfg["settings"]["anti_repeat"]:
        last = context.user_data.get("last_text")
        if last == text_l:
            await msg.delete()
            return
        context.user_data["last_text"] = text_l

    # anti caps
    if cfg["settings"]["anti_caps"]:
        if text.isupper() and len(text) > 6:
            await msg.delete()
            await chat.send_message(f"🔠 Jangan caps lock, {user.first_name}")
            return

    # bad words (regex word boundary)
    if cfg["settings"]["sensor"]:
        for w in cfg["bad_words"]:
            if re.search(rf"\b{re.escape(w)}\b", text_l):
                await msg.delete()

                uid = str(user.id)
                cfg["warnings"][uid] = cfg["warnings"].get(uid, 0) + 1
                warn = cfg["warnings"][uid]
                save_data(data)

                await chat.send_message(
                    f"⚠️ {user.first_name} melanggar\nWarning: {warn}/5"
                )

                # mute
                if warn == 3 and cfg["settings"]["mute_on_3"]:
                    await chat.restrict_member(
                        user.id,
                        ChatPermissions(can_send_messages=False),
                        until_date=int(time.time()) + 60
                    )
                    await chat.send_message(f"🔇 {user.first_name} di-mute 1 menit")

                # kick
                if warn >= 5 and cfg["settings"]["kick_on_5"]:
                    await chat.ban_member(user.id)
                    await chat.send_message(f"💀 {user.first_name} di-kick")

                return

    # anti link
    if cfg["settings"]["anti_link"]:
        if "http://" in text_l or "https://" in text_l or "t.me/" in text_l:
            await msg.delete()
            await chat.send_message(f"🚫 Link dilarang, {user.first_name}")

# ===== WELCOME =====
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return
    cfg = get_chat_cfg(msg.chat.id)
    if not cfg["settings"]["welcome"]:
        return

    for u in msg.new_chat_members:
        await msg.reply_text(f"👋 Welcome {u.first_name}!")

# ===== MENU =====
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📛 Kata", callback_data="words")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Toggle Link", callback_data="tgl_link")],
        [InlineKeyboardButton("🔠 Toggle Caps", callback_data="tgl_caps")],
        [InlineKeyboardButton("🔁 Toggle Repeat", callback_data="tgl_repeat")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])

# ===== COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot aktif", reply_markup=main_menu())

async def addbad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("pakai: /addbad kata")

    chat = update.effective_chat
    if not await is_admin(chat, update.effective_user.id):
        return await update.message.reply_text("admin only")

    cfg = get_chat_cfg(chat.id)
    w = context.args[0].lower()
    if w not in cfg["bad_words"]:
        cfg["bad_words"].append(w)
        save_data(data)
    await update.message.reply_text(f"ditambah: {w}")

# ===== BUTTON =====
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat = q.message.chat
    cfg = get_chat_cfg(chat.id)

    if q.data == "words":
        await q.message.reply_text("\n".join(cfg["bad_words"]))

    elif q.data == "settings":
        await q.message.reply_text("⚙️ Settings", reply_markup=settings_menu())

    elif q.data == "tgl_link":
        cfg["settings"]["anti_link"] = not cfg["settings"]["anti_link"]
        save_data(data)
        await q.message.reply_text(f"Anti link: {cfg['settings']['anti_link']}")

    elif q.data == "tgl_caps":
        cfg["settings"]["anti_caps"] = not cfg["settings"]["anti_caps"]
        save_data(data)
        await q.message.reply_text(f"Caps: {cfg['settings']['anti_caps']}")

    elif q.data == "tgl_repeat":
        cfg["settings"]["anti_repeat"] = not cfg["settings"]["anti_repeat"]
        save_data(data)
        await q.message.reply_text(f"Repeat: {cfg['settings']['anti_repeat']}")

    elif q.data == "back":
        await q.message.reply_text("Menu", reply_markup=main_menu())

# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addbad", addbad))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))

print("🚀 BOT PRODUCTION READY")
app.run_polling()
