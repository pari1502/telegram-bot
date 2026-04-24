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
        "biadab","monyet","sialan"
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
            "whitelist": [],
            "stats": {},
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

# ===== ADMIN =====
async def is_admin(chat, user_id):
    try:
        m = await chat.get_member(user_id)
        return m.status in ["administrator", "creator"]
    except:
        return False

# ===== DELETE =====
async def safe_delete(msg):
    try:
        await msg.delete()
    except:
        pass

# ===== NORMALIZE TEXT =====
def normalize(text):
    text = text.lower()
    text = text.replace("0","o").replace("1","i")
    text = re.sub(r"(.)\1+", r"\1", text)
    return text

# ===== MODERATION =====
async def moderate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    if msg.chat.type == "private":
        return

    chat = msg.chat
    user = msg.from_user
    text = normalize(msg.text)

    cfg = get_chat_cfg(chat.id)

    if user.id in cfg["whitelist"]:
        return

    if await is_admin(chat, user.id):
        return

    # spam
    now = time.time()
    q = user_msgs[user.id]
    q.append(now)
    if len(q) >= 5 and (q[-1] - q[0]) < 3:
        await safe_delete(msg)
        return

    # repeat
    last = context.user_data.get("last")
    if last == text:
        await safe_delete(msg)
        return
    context.user_data["last"] = text

    # caps
    if msg.text.isupper() and len(msg.text) > 6:
        await safe_delete(msg)
        await chat.send_message("🔠 Jangan caps")
        return

    # bad words
    for w in cfg["bad_words"]:
        if w in text:
            await safe_delete(msg)

            uid = str(user.id)
            cfg["warnings"][uid] = cfg["warnings"].get(uid, 0) + 1
            cfg["stats"][uid] = cfg["stats"].get(uid, 0) + 1
            warn = cfg["warnings"][uid]
            save_data(data)

            await chat.send_message(f"⚠️ {user.first_name} Warning: {warn}/5")

            if warn == 3:
                try:
                    await chat.restrict_member(user.id, ChatPermissions(can_send_messages=False))
                except:
                    pass

            if warn >= 5:
                try:
                    await chat.ban_member(user.id)
                except:
                    pass
            return

    # link
    if "http://" in text or "https://" in text or "t.me/" in text:
        await safe_delete(msg)
        await chat.send_message("🚫 Link dilarang")

# ===== COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot Level Dewa Aktif")

async def addkata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Contoh: /addkata kata")

    chat = update.message.chat
    cfg = get_chat_cfg(chat.id)
    kata = context.args[0].lower()

    if kata not in cfg["bad_words"]:
        cfg["bad_words"].append(kata)
        save_data(data)

    await update.message.reply_text("✅ Ditambahkan")

async def delkata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return

    chat = update.message.chat
    cfg = get_chat_cfg(chat.id)
    kata = context.args[0].lower()

    if kata in cfg["bad_words"]:
        cfg["bad_words"].remove(kata)
        save_data(data)

    await update.message.reply_text("🗑️ Dihapus")

async def listkata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_chat_cfg(update.message.chat.id)
    await update.message.reply_text("\n".join(cfg["bad_words"]))

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.message.chat.ban_member(update.message.reply_to_message.from_user.id)

async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.message.chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=False)
        )

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        await update.message.chat.restrict_member(
            update.message.reply_to_message.from_user.id,
            ChatPermissions(can_send_messages=True)
        )

async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        cfg = get_chat_cfg(update.message.chat.id)
        uid = str(update.message.reply_to_message.from_user.id)
        cfg["warnings"][uid] = cfg["warnings"].get(uid, 0) + 1
        save_data(data)

async def resetwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        cfg = get_chat_cfg(update.message.chat.id)
        uid = str(update.message.reply_to_message.from_user.id)
        cfg["warnings"][uid] = 0
        save_data(data)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = get_chat_cfg(update.message.chat.id)
    text = "📊 Toxic:\n"
    for uid, val in cfg["stats"].items():
        text += f"{uid}: {val}\n"
    await update.message.reply_text(text)

async def whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.reply_to_message:
        cfg = get_chat_cfg(update.message.chat.id)
        cfg["whitelist"].append(update.message.reply_to_message.from_user.id)
        save_data(data)

# ===== MAIN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("addkata", addkata))
app.add_handler(CommandHandler("delkata", delkata))
app.add_handler(CommandHandler("listkata", listkata))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("resetwarn", resetwarn))
app.add_handler(CommandHandler("stats", stats))
app.add_handler(CommandHandler("whitelist", whitelist))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, moderate))

print("🔥 BOT LEVEL DEWA AKTIF")
app.run_polling()
