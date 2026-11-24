import os
import sqlite3
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "udaburon_talaba.db")

# Conversation states
ROLE, NAME, PHONE, CITY, STUDY, JOB_TITLE, JOB_DESC, JOB_PAY, JOB_TYPE = range(9)

def db():
    return sqlite3.connect(DB_PATH)

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS users (
            tg_id INTEGER PRIMARY KEY, role TEXT, name TEXT, phone TEXT,
            city TEXT, study TEXT, created_at TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, employer_id INTEGER,
            employer_name TEXT, title TEXT, description TEXT, pay TEXT,
            job_type TEXT, city TEXT, status TEXT DEFAULT 'active',
            created_at TEXT
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER,
            student_id INTEGER, student_name TEXT, created_at TEXT,
            UNIQUE(job_id, student_id)
        )""")

def main_menu(role=None):
    rows = [
        [KeyboardButton("🔎 Ish qidirish"), KeyboardButton("👤 Profilim")],
        [KeyboardButton("📄 Arizalarim"), KeyboardButton("ℹ️ Yordam")]
    ]
    if role == "employer":
        rows.insert(1, [KeyboardButton("➕ Ish joylashtirish")])
    else:
        rows.insert(1, [KeyboardButton("🏢 Ish beruvchi bo‘lish")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def get_user(tg_id):
    with db() as con:
        return con.execute("SELECT role,name,phone,city,study FROM users WHERE tg_id=?", (tg_id,)).fetchone()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(update.effective_user.id)
    if user:
        await update.message.reply_text(
            f"Assalomu alaykum, {user[1]}! 🎓\nUDABURON TALABA platformasiga xush kelibsiz.",
            reply_markup=main_menu(user[0])
        )
        return ConversationHandler.END
    keyboard = [["🎓 Talabaman", "🏢 Ish beruvchiman"]]
    await update.message.reply_text(
        "Assalomu alaykum! 🎓\nUDABURON TALABA botiga xush kelibsiz.\n\n"
        "Davom etish uchun rolingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ROLE

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🎓 Talabaman":
        context.user_data["role"] = "student"
    elif text == "🏢 Ish beruvchiman":
        context.user_data["role"] = "employer"
    else:
        await update.message.reply_text("Iltimos, tugmalardan birini tanlang.")
        return ROLE
    await update.message.reply_text("Ism-familiyangizni kiriting:")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text.strip()[:100]
    await update.message.reply_text(
        "Telefon raqamingizni yuboring yoki +998 bilan yozing:",
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("📱 Raqamni yuborish", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.contact.phone_number if update.message.contact else update.message.text.strip()
    context.user_data["phone"] = phone[:30]
    await update.message.reply_text("Qaysi shahar yoki tumandasiz?")
    return CITY

async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()[:80]
    if context.user_data["role"] == "student":
        await update.message.reply_text("Qayerda o‘qiysiz? (OTM yoki kollej nomi)")
        return STUDY
    context.user_data["study"] = ""
    save_user(update.effective_user.id, context.user_data)
    await update.message.reply_text("Ro‘yxatdan o‘tish yakunlandi! ✅", reply_markup=main_menu("employer"))
    return ConversationHandler.END

async def get_study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["study"] = update.message.text.strip()[:120]
    save_user(update.effective_user.id, context.user_data)
    await update.message.reply_text("Ro‘yxatdan o‘tish yakunlandi! ✅", reply_markup=main_menu("student"))
    return ConversationHandler.END

def save_user(tg_id, data):
    with db() as con:
        con.execute("""INSERT OR REPLACE INTO users
            (tg_id,role,name,phone,city,study,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (tg_id, data["role"], data["name"], data["phone"], data["city"],
             data.get("study",""), datetime.now().isoformat(timespec="seconds")))

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Avval /start orqali ro‘yxatdan o‘ting.")
        return
    role = "Talaba" if u[0] == "student" else "Ish beruvchi"
    await update.message.reply_text(
        f"👤 Profilingiz\nTuri: {role}\nIsm: {u[1]}\nTelefon: {u[2]}\n"
        f"Shahar: {u[3]}\nO‘qish joyi: {u[4] or 'Ko‘rsatilmagan'}"
    )

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Avval /start orqali ro‘yxatdan o‘ting.")
        return
    with db() as con:
        rows = con.execute("""SELECT id,title,description,pay,job_type,city,employer_name
            FROM jobs WHERE status='active' ORDER BY id DESC LIMIT 15""").fetchall()
    if not rows:
        await update.message.reply_text("Hozircha faol ish e’lonlari yo‘q. Keyinroq yana tekshiring.")
        return
    for job in rows:
        text = (f"💼 {job[1]}\n📍 {job[5]}\n⏰ {job[4]}\n💰 {job[3]}\n"
                f"🏢 {job[6]}\n\n{job[2]}")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📩 Ariza yuborish", callback_data=f"apply:{job[0]}")]])
        await update.message.reply_text(text, reply_markup=keyboard)

async def apply_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id)
    if not u or u[0] != "student":
        await q.message.reply_text("Ariza yuborish uchun avval talaba sifatida ro‘yxatdan o‘ting: /start")
        return
    job_id = int(q.data.split(":")[1])
    try:
        with db() as con:
            con.execute("INSERT INTO applications(job_id,student_id,student_name,created_at) VALUES(?,?,?,?)",
                        (job_id, q.from_user.id, u[1], datetime.now().isoformat(timespec="seconds")))
        await q.message.reply_text("Arizangiz ish beruvchiga yuborildi! ✅")
    except sqlite3.IntegrityError:
        await q.message.reply_text("Siz bu ishga avval ariza yuborgansiz.")

async def begin_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u or u[0] != "employer":
        await update.message.reply_text("Ish joylashtirish uchun ish beruvchi sifatida ro‘yxatdan o‘ting.")
        return ConversationHandler.END
    await update.message.reply_text("Ish nomini kiriting:")
    return JOB_TITLE

async def job_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_title"] = update.message.text.strip()[:100]
    await update.message.reply_text("Ish haqida batafsil ma’lumot yozing:")
    return JOB_DESC

async def job_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_desc"] = update.message.text.strip()[:1500]
    await update.message.reply_text("Maoshni kiriting (masalan: kuniga 150 000 so‘m):")
    return JOB_PAY

async def job_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_pay"] = update.message.text.strip()[:100]
    await update.message.reply_text("Ish turini kiriting (kunlik, yarim kunlik yoki to‘liq):")
    return JOB_TYPE

async def job_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    job_type_text = update.message.text.strip()[:80]
    with db() as con:
        con.execute("""INSERT INTO jobs
            (employer_id,employer_name,title,description,pay,job_type,city,status,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (update.effective_user.id, u[1], context.user_data["job_title"],
             context.user_data["job_desc"], context.user_data["job_pay"],
             job_type_text, u[3], "active", datetime.now().isoformat(timespec="seconds")))
    await update.message.reply_text("Ish e’loningiz joylashtirildi! ✅", reply_markup=main_menu("employer"))
    return ConversationHandler.END

async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        rows = con.execute("""SELECT j.title,a.created_at FROM applications a
            JOIN jobs j ON j.id=a.job_id WHERE a.student_id=? ORDER BY a.id DESC LIMIT 15""",
            (update.effective_user.id,)).fetchall()
    if not rows:
        await update.message.reply_text("Siz hali hech qanday ishga ariza yubormagansiz.")
        return
    for title, created in rows:
        await update.message.reply_text(f"📄 {title}\nYuborilgan vaqt: {created}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Yordam\nIsh qidirish — faol e’lonlarni ko‘rish.\n"
        "Ish joylashtirish — ish beruvchilar uchun.\n"
        "Profilim — ro‘yxatdan o‘tgan ma’lumotlaringiz.\n"
        "Muammo bo‘lsa, loyiha administratoriga murojaat qiling."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Amal bekor qilindi.", reply_markup=main_menu())
    return ConversationHandler.END

def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. Tokenni muhit o‘zgaruvchisiga kiriting.")
    init_db()
    app = Application.builder().token(TOKEN).build()

    registration = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_role)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            PHONE: [MessageHandler((filters.TEXT | filters.CONTACT) & ~filters.COMMAND, get_phone)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            STUDY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_study)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    posting = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Ish joylashtirish$"), begin_job)],
        states={
            JOB_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_title)],
            JOB_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_desc)],
            JOB_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_pay)],
            JOB_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
        app.add_handler(registration)
    app.add_handler(posting)
    app.add_handler(CallbackQueryHandler(apply_job, pattern=r"^apply:\d+$"))
    app.add_handler(MessageHandler(filters.Regex("^🔎 Ish qidirish$"), jobs))
    app.add_handler(MessageHandler(filters.Regex("^👤 Profilim$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^📄 Arizalarim$"), my_applications))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Yordam$"), help_cmd))
    print("UDABURON TALABA bot ishga tushdi...")
    import asyncio
    asyncio.set_event_loop(asyncio.new_event_loop())

    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
        url_path=TOKEN,
        webhook_url=f"{os.environ['RENDER_EXTERNAL_URL']}/{TOKEN}",
        drop_pending_updates=True,
        bootstrap_retries=5
    )
if __name__ == "__main__":
    main()
