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

    data.setdefault("global_bad_words", [
        "anjing","babi","bangsat","kontol","memek","ngentot",
        "tolol","goblok","idiot","asu","kampret","brengsek",
        "tai","jancok","bajingan","keparat","setan","laknat",
        "biadab","monyet","sialan","puki","coli","pepek",
        "ngentod","kontlo","memex","anjir","anjay"
    ])

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

# ===== UTIL =====
user_msgs = defaultdict(lambda: deque(maxlen=5))

async def is_admin(chat, user_id):
    try:
        m = await chat.get_member(user_id)
        return m.status in ["administrator", "creator"]
    except:
        return False

async def safe_delete(msg):
    try:
        await msg.delete()
    except:
        pass

def normalize(text):
    text = text.lower()
    text = text.replace("0","o").replace("1","i").replace("3","e")
    text = re.sub(r"(.)\1+", r"\1", text)
    return text

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
    text_l = normalize(text)

    cfg = get_chat_cfg(chat.id)

    if await is_admin(chat, user.id):
        return

    # SPAM
    now = time.time()
    q = user_msgs[user.id]
    q.append(now)
    if len(q) >= 5 and (q[-1] - q[0]) < 3:
        await safe_delete(msg)
        return

    # REPEAT
    if cfg["settings"]["anti_repeat"]:
        last = context.user_data.get("last")
        if last == text_l:
            await safe_delete(msg)
            return
        context.user_data["last"] = text_l

    # CAPS
    if cfg["settings"]["anti_caps"]:
        if text.isupper() and len(text) > 6:
            await safe_delete(msg)
            await chat.send_message(f"🔠 Jangan caps {user.first_name}")
            return

    # SENSOR
    if cfg["settings"]["sensor"]:
        for w in cfg["bad_words"]:
            if w in text_l:
                await safe_delete(msg)

                uid = str(user.id)
                cfg["warnings"][uid] = cfg["warnings"].get(uid, 0) + 1
                warn = cfg["warnings"][uid]
                save_data(data)

                await chat.send_message(f"⚠️ {user.first_name}\nWarning: {warn}/5")

                if warn == 3:
                    await chat.restrict_member(
                        user.id,
                        ChatPermissions(can_send_messages=False),
                        until_date=int(time.time()) + 60
                    )
                    await chat.send_message("🔇 Dimute 1 menit")

                if warn >= 5:
                    await chat.ban_member(user.id)
                    await chat.send_message("💀 Dikick!")

                return

    # LINK
    if cfg["settings"]["anti_link"]:
        if "http" in text_l or "t.me/" in text_l:
            await safe_delete(msg)
            await chat.send_message(f"🚫 Link dilarang {user.first_name}")

# ===== MENU =====
def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📛 Kata", callback_data="words")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
        [InlineKeyboardButton("👮 Admin Panel", callback_data="admin")]
    ])

def settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Link", callback_data="link")],
        [InlineKeyboardButton("🔠 Caps", callback_data="caps")],
        [InlineKeyboardButton("🔁 Repeat", callback_data="repeat")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Warning", callback_data="warnlist")],
        [InlineKeyboardButton("♻️ Reset", callback_data="resetwarn")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 BOT LEVEL DEWA AKTIF", reply_markup=menu())

# ===== WELCOME =====
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for user in update.message.new_chat_members:
        keyboard = [
            [InlineKeyboardButton("📛 Kata Terlarang", callback_data="words")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
        await update.message.reply_text(
            f"👋 Selamat datang {user.mention_html()}!\n🚫 Jaga kata-kata ya!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    chat = q.message.chat
    cfg = get_chat_cfg(chat.id)

    if q.data == "words":
        await q.message.reply_text("\n".join(cfg["bad_words"][:20]))

    elif q.data == "settings":
        await q.message.reply_text("⚙️ Settings", reply_markup=settings_menu())

    elif q.data == "admin":
        if not await is_admin(chat, q.from_user.id):
            return await q.message.reply_text("❌ Khusus admin")
        await q.message.reply_text("👮 Admin Panel", reply_markup=admin_menu())

    elif q.data == "warnlist":
        text = "📊 Warning:\n"
        for uid, w in cfg["warnings"].items():
            text += f"{uid}: {w}\n"
        await q.message.reply_text(text)

    elif q.data == "resetwarn":
        cfg["warnings"] = {}
        save_data(data)
        await q.message.reply_text("♻️ Reset")

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

# ===== ADMIN COMMAND =====
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    user = update.message.reply_to_message.from_user
    chat = update.message.chat
    await chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))
    await update.message.reply_text("🔇 Dimute")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    user = update.message.reply_to_message.from_user
    chat = update.message.chat
    await chat.restrict_member(user.id, ChatPermissions(can_send_messages=True))
    await update.message.reply_text("🔊 Unmute")

async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        return
    user = update.message.reply_to_message.from_user
    chat = update.message.chat
    await chat.ban_member(user.id)
    await update.message.reply_text("💀 Dikick")

# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("kick", kick))

app.add_handler(CallbackQueryHandler(button))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome))

print("🚀 BOT DEWA AKTIF")
app.run_polling()
