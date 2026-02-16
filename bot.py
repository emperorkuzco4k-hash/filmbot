import json
import os
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =======================
# تنظیمات
# =======================
BOT_TOKEN = os.environ.get("8341913444:AAG8jd4dcHvWQa1b2UIkXgkENjPPXqfNM1w")
ADMIN_ID = 1016313273  # آیدی عددی خودت از @userinfobot
DB_PATH = "db.json"

# منوی دائمی پایین
MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["فیلم", "سریال"],
        ["کارتون", "انیمیشن"],
        ["فیلم ایرانی", "سریال ایرانی"],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

# =======================
# DB helpers
# =======================
def load_db() -> dict:
    if not os.path.exists(DB_PATH):
        return {}
    with open(DB_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_db(db: dict) -> None:
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user and user.id == ADMIN_ID)

# ساختار DB:
# {
#   "SeriesName": {
#     "1": {
#        "0": {"file_id": "پوستر فصل 1", "title": "Poster"},
#        "1": {"file_id": "قسمت1", "title": "E01"},
#        "2": {"file_id": "قسمت2", "title": "E02"}
#     },
#     "2": {...}
#   }
# }

# =======================
# /start و منوی اصلی
# =======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام 👋\nاز منوی زیر انتخاب کن:", reply_markup=MAIN_MENU)

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    # فقط نمونه (می‌تونی بعداً اینجا رو هوشمند کنی)
    if text in ["فیلم", "سریال", "کارتون", "انیمیشن", "فیلم ایرانی", "سریال ایرانی"]:
        await update.message.reply_text(f"✅ انتخاب شد: {text}\nبرای لیست سریال‌ها: /list\nبرای دیدن فصل: /season نام 1", reply_markup=MAIN_MENU)
    else:
        await update.message.reply_text("از منو یکی رو انتخاب کن 👇", reply_markup=MAIN_MENU)

# =======================
# لیست سریال‌ها
# =======================
async def list_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not db:
        await update.message.reply_text("فعلاً چیزی اضافه نشده.", reply_markup=MAIN_MENU)
        return
    names = "\n".join([f"• {k}" for k in db.keys()])
    await update.message.reply_text(
        f"📺 لیست:\n{names}\n\nبرای ارسال فصل ۱:\n/season نام_سریال 1",
        reply_markup=MAIN_MENU
    )

# =======================
# ناوبری قسمت‌ها (اختیاری)
# =======================
def nav_keyboard(series: str, season: int, ep: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("⬅️ فصل قبل", callback_data=f"nav|{series}|{season-1}|1"),
            InlineKeyboardButton("فصل بعد ➡️", callback_data=f"nav|{series}|{season+1}|1"),
        ],
        [
            InlineKeyboardButton("⬅️ قسمت قبل", callback_data=f"nav|{series}|{season}|{ep-1}"),
            InlineKeyboardButton("قسمت بعد ➡️", callback_data=f"nav|{series}|{season}|{ep+1}"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)

async def send_episode(chat_id: int, context: ContextTypes.DEFAULT_TYPE, series: str, season: int, ep: int):
    db = load_db()
    s = db.get(series, {})
    season_str = str(season)
    ep_str = str(ep)

    if season < 1:
        season = 1
        season_str = "1"
    if ep < 1:
        ep = 1
        ep_str = "1"

    if season_str not in s:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ فصل {season} برای «{series}» پیدا نشد.")
        return

    if ep_str not in s[season_str]:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ قسمت {ep} از فصل {season} برای «{series}» پیدا نشد.")
        return

    file_id = s[season_str][ep_str]["file_id"]
    title = s[season_str][ep_str].get("title") or f"S{season:02d}E{ep:02d}"

    await context.bot.send_video(
        chat_id=chat_id,
        video=file_id,
        caption=f"🎬 {series}\nفصل {season} - قسمت {ep}\n{title}",
        reply_markup=nav_keyboard(series, season, ep)
    )

async def on_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    try:
        _, series, season_s, ep_s = (q.data or "").split("|")
        season = int(season_s)
        ep = int(ep_s)
    except Exception:
        await q.edit_message_text("خطا در ناوبری.")
        return

    await send_episode(chat_id=q.message.chat_id, context=context, series=series, season=season, ep=ep)

async def series_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("مثال:\n/series MySeries", reply_markup=MAIN_MENU)
        return
    series = " ".join(context.args).strip()
    await send_episode(chat_id=update.message.chat_id, context=context, series=series, season=1, ep=1)

# =======================
# ارسال فصل کامل + حذف بعد 60 ثانیه
# =======================
async def delete_sent_messages(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    message_ids = job_data["message_ids"]

    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

async def send_season_pack(chat_id: int, context: ContextTypes.DEFAULT_TYPE, series: str, season: int, ttl_seconds: int = 60):
    db = load_db()
    s = db.get(series, {})
    season_str = str(season)

    if season_str not in s:
        await context.bot.send_message(chat_id=chat_id, text="❌ این فصل موجود نیست.")
        return

    message_ids = []

    # پوستر فصل (قسمت 0)
    if "0" in s[season_str]:
        poster_id = s[season_str]["0"]["file_id"]
        m = await context.bot.send_photo(
            chat_id=chat_id,
            photo=poster_id,
            caption=f"📌 {series} — پوستر فصل {season}\n⏳ تا {ttl_seconds} ثانیه دیگه حذف می‌شه."
        )
        message_ids.append(m.message_id)

    # اپیزودها (1..)
    eps = []
    for k in s[season_str].keys():
        if k.isdigit() and int(k) >= 1:
            eps.append(int(k))
    eps.sort()

    if not eps:
        m = await context.bot.send_message(chat_id=chat_id, text="❌ برای این فصل هیچ قسمتی ثبت نشده.")
        message_ids.append(m.message_id)
    else:
        for ep in eps:
            ep_data = s[season_str][str(ep)]
            file_id = ep_data["file_id"]
            title = ep_data.get("title") or f"S{season:02d}E{ep:02d}"

            m = await context.bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=f"🎬 {series}\nفصل {season} - قسمت {ep}\n{title}\n⏳ تا {ttl_seconds} ثانیه دیگه حذف می‌شه."
            )
            message_ids.append(m.message_id)

    # زمان‌بندی حذف
    context.job_queue.run_once(
        delete_sent_messages,
        when=ttl_seconds,
        data={"chat_id": chat_id, "message_ids": message_ids},
        name=f"del_{chat_id}_{series}_{season}"
    )

async def season_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # مثال: /season Breaking Bad 1
    if len(context.args) < 2:
        await update.message.reply_text("مثال:\n/season Breaking Bad 1", reply_markup=MAIN_MENU)
        return

    series = " ".join(context.args[:-1]).strip()
    try:
        season = int(context.args[-1])
    except ValueError:
        await update.message.reply_text("شماره فصل باید عدد باشد.", reply_markup=MAIN_MENU)
        return

    await send_season_pack(update.message.chat_id, context, series, season, ttl_seconds=60)

# =======================
# آپلود (ادمین) - ویدیو یا عکس
# =======================
ASK_SERIES, ASK_SEASON, ASK_EP, ASK_MEDIA, ASK_TITLE = range(5)

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("این بخش فقط برای ادمین است.")
        return ConversationHandler.END
    await update.message.reply_text("اسم سریال رو بفرست (مثلاً: Breaking Bad):")
    return ASK_SERIES

async def add_series(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["series"] = (update.message.text or "").strip()
    await update.message.reply_text("شماره فصل رو بفرست (مثلاً 1):")
    return ASK_SEASON

async def add_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["season"] = int((update.message.text or "1").strip())
    except ValueError:
        context.user_data["season"] = 1
    await update.message.reply_text("شماره قسمت رو بفرست (مثلاً 1) — برای پوستر فصل، قسمت 0 بزن:")
    return ASK_EP

async def add_ep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["ep"] = int((update.message.text or "1").strip())
    except ValueError:
        context.user_data["ep"] = 1
    await update.message.reply_text("حالا ویدیو یا عکس رو بفرست (پوستر=عکس / قسمت=ویدیو):")
    return ASK_MEDIA

async def add_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    photo = update.message.photo

    if not video and not photo:
        await update.message.reply_text("❌ ویدیو یا عکس ارسال کن.")
        return ASK_MEDIA

    if video:
        file_id = video.file_id
        media_type = "video"
    else:
        file_id = photo[-1].file_id  # بهترین کیفیت
        media_type = "photo"

    context.user_data["file_id"] = file_id
    context.user_data["media_type"] = media_type

    await update.message.reply_text("یک عنوان کوتاه بفرست (یا فقط - بزن):")
    return ASK_TITLE

async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = (update.message.text or "").strip()
    if title == "-":
        title = ""

    series = context.user_data["series"]
    season = context.user_data["season"]
    ep = context.user_data["ep"]
    file_id = context.user_data["file_id"]
    media_type = context.user_data.get("media_type", "video")

    db = load_db()
    db.setdefault(series, {})
    db[series].setdefault(str(season), {})
    db[series][str(season)][str(ep)] = {"file_id": file_id, "title": title, "type": media_type}
    save_db(db)

    if ep == 0:
        msg = f"✅ پوستر ذخیره شد:\n{series} - فصل {season} (پوستر)"
    else:
        msg = f"✅ قسمت ذخیره شد:\n{series} - فصل {season} - قسمت {ep}"

    await update.message.reply_text(
        msg + "\n\nبرای ارسال فصل کامل (حذف بعد 60 ثانیه):\n/season " + series + f" {season}",
        reply_markup=MAIN_MENU
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("کنسل شد.", reply_markup=MAIN_MENU)
    return ConversationHandler.END

# =======================
# main
# =======================
def main():
    # اگر db.json نبود بساز
    if not os.path.exists(DB_PATH):
        save_db({})

    app = Application.builder().token(BOT_TOKEN).build()

    # عمومی
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    # دستورات
    app.add_handler(CommandHandler("list", list_series))
    app.add_handler(CommandHandler("series", series_cmd))
    app.add_handler(CommandHandler("season", season_cmd))

    # ناوبری اینلاین
    app.add_handler(CallbackQueryHandler(on_nav, pattern=r"^nav\|"))

    # افزودن (ادمین)
    conv = ConversationHandler(
        entry_points=[CommandHandler("add", add_start)],
        states={
            ASK_SERIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_series)],
            ASK_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_season)],
            ASK_EP: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ep)],
            ASK_MEDIA: [MessageHandler(filters.VIDEO | filters.PHOTO, add_media)],
            ASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
