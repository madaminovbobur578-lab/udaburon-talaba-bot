import os
import sqlite3
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "udaburon_talaba.db")

# Faqat shu uchta Telegram akkaunt admin bo'la oladi.
ADMIN_IDS = {8954923102, 8906314179, 641732276}

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

        # Eski ma'lumotlar bazasiga VIP ustunini xavfsiz qo'shish.
        columns = {
            row[1] for row in con.execute("PRAGMA table_info(jobs)").fetchall()
        }
        if "is_vip" not in columns:
            con.execute("ALTER TABLE jobs ADD COLUMN is_vip INTEGER DEFAULT 0")


def is_admin(tg_id):
    return tg_id in ADMIN_IDS


def main_menu(role=None, admin=False):
    rows = [
        [KeyboardButton("ð Ish qidirish"), KeyboardButton("ð¤ Profilim")],
        [KeyboardButton("ð Arizalarim"), KeyboardButton("â¹ï¸ Yordam")]
    ]
    if role == "employer":
        rows.insert(1, [KeyboardButton("â Ish joylashtirish"),
                        KeyboardButton("ð Mening eâlonlarim")])
    else:
        rows.insert(1, [KeyboardButton("ð¢ Ish beruvchi boâlish")])
    if admin:
        rows.append([KeyboardButton("ð Admin panel")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def get_user(tg_id):
    with db() as con:
        return con.execute(
            "SELECT role,name,phone,city,study FROM users WHERE tg_id=?",
            (tg_id,)
        ).fetchone()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id

    if is_admin(tg_id):
        await update.message.reply_text(
            "Assalomu alaykum, admin! 👑\n"
            "UDABURON TALABA boshqaruv paneliga xush kelibsiz.",
            reply_markup=main_menu(admin=True)
        )
        return ConversationHandler.END

    user = get_user(tg_id)
    if user:
        await update.message.reply_text(
            f"Assalomu alaykum, {user[1]}! 🎓\n"
            "UDABURON TALABA platformasiga xush kelibsiz.",
            reply_markup=main_menu(user[0])
        )
        return ConversationHandler.END

    keyboard = [["🎓 Talabaman", "🏢 Ish beruvchiman"]]
    await update.message.reply_text(
        "Assalomu alaykum! 🎓\nUDABURON TALABA botiga xush kelibsiz.\n\n"
        "Davom etish uchun rolingizni tanlang:",
        reply_markup=ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
    )
    return ROLE

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "ð Talabaman":
        context.user_data["role"] = "student"
    elif text == "ð¢ Ish beruvchiman":
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
            [[KeyboardButton("ð± Raqamni yuborish", request_contact=True)]],
            resize_keyboard=True, one_time_keyboard=True
        )
    )
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = (
        update.message.contact.phone_number
        if update.message.contact else update.message.text.strip()
    )
    context.user_data["phone"] = phone[:30]
    await update.message.reply_text("Qaysi shahar yoki tumandasiz?")
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()[:80]
    if context.user_data["role"] == "student":
        await update.message.reply_text("Qayerda oâqiysiz? (OTM yoki kollej nomi)")
        return STUDY

    context.user_data["study"] = ""
    save_user(update.effective_user.id, context.user_data)
    await update.message.reply_text(
        "Roâyxatdan oâtish yakunlandi! â",
        reply_markup=main_menu("employer", is_admin(update.effective_user.id))
    )
    return ConversationHandler.END


async def get_study(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["study"] = update.message.text.strip()[:120]
    save_user(update.effective_user.id, context.user_data)
    await update.message.reply_text(
        "Roâyxatdan oâtish yakunlandi! â",
        reply_markup=main_menu("student", is_admin(update.effective_user.id))
    )
    return ConversationHandler.END


def save_user(tg_id, data):
    with db() as con:
        con.execute("""INSERT OR REPLACE INTO users
            (tg_id,role,name,phone,city,study,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            (tg_id, data["role"], data["name"], data["phone"], data["city"],
             data.get("study", ""), datetime.now().isoformat(timespec="seconds")))


async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Avval /start orqali roâyxatdan oâting.")
        return
    role = "Talaba" if u[0] == "student" else "Ish beruvchi"
    await update.message.reply_text(
        f"ð¤ Profilingiz\nTuri: {role}\nIsm: {u[1]}\nTelefon: {u[2]}\n"
        f"Shahar: {u[3]}\nOâqish joyi: {u[4] or 'Koârsatilmagan'}"
    )


async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("Avval /start orqali roâyxatdan oâting.")
        return

    with db() as con:
        rows = con.execute("""SELECT id,title,description,pay,job_type,city,
            employer_name,is_vip FROM jobs
            WHERE status='active'
            ORDER BY is_vip DESC, id DESC LIMIT 30""").fetchall()

    if not rows:
        await update.message.reply_text(
            "Hozircha faol ish eâlonlari yoâq. Keyinroq yana tekshiring."
        )
        return

    for job in rows:
        vip_mark = "â­ VIP E'LON\n" if job[7] else ""
        text = (
            f"{vip_mark}ð¼ {job[1]}\nð {job[5]}\nâ° {job[4]}\n"
            f"ð° {job[3]}\nð¢ {job[6]}\n\n{job[2]}"
        )
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("ð© Ariza yuborish", callback_data=f"apply:{job[0]}")
        ]])
        await update.message.reply_text(text, reply_markup=keyboard)


async def apply_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = get_user(q.from_user.id)
    if not u or u[0] != "student":
        await q.message.reply_text(
            "Ariza yuborish uchun avval talaba sifatida roâyxatdan oâting: /start"
        )
        return

    job_id = int(q.data.split(":")[1])
    with db() as con:
        job = con.execute(
            "SELECT status FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not job or job[0] != "active":
            await q.message.reply_text("Bu eâlon endi faol emas.")
            return
        try:
            con.execute(
                """INSERT INTO applications
                (job_id,student_id,student_name,created_at) VALUES (?,?,?,?)""",
                (job_id, q.from_user.id, u[1],
                 datetime.now().isoformat(timespec="seconds"))
            )
            await q.message.reply_text("Arizangiz ish beruvchiga yuborildi! â")
        except sqlite3.IntegrityError:
            await q.message.reply_text("Siz bu ishga avval ariza yuborgansiz.")


async def begin_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    admin_add = context.user_data.pop("admin_adding_job", False)

    if not admin_add and (not u or u[0] != "employer"):
        await update.message.reply_text(
            "Ish joylashtirish uchun ish beruvchi sifatida roâyxatdan oâting."
        )
        return ConversationHandler.END

    context.user_data["posting_as_admin"] = admin_add
    await update.message.reply_text("Ish nomini kiriting:")
    return JOB_TITLE


async def job_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_title"] = update.message.text.strip()[:100]
    await update.message.reply_text("Ish haqida batafsil maâlumot yozing:")
    return JOB_DESC


async def job_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_desc"] = update.message.text.strip()[:1500]
    await update.message.reply_text("Maoshni kiriting (masalan: kuniga 150 000 soâm):")
    return JOB_PAY


async def job_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["job_pay"] = update.message.text.strip()[:100]
    await update.message.reply_text("Ish turini kiriting (kunlik, yarim kunlik yoki toâliq):")
    return JOB_TYPE


async def job_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    u = get_user(tg_id)
    admin_post = context.user_data.get("posting_as_admin", False)

    if admin_post:
        employer_id = tg_id
        employer_name = "UDABURON TALABA admini"
        city = "Koârsatilmagan"
    else:
        if not u or u[0] != "employer":
            await update.message.reply_text("Ish beruvchi profilingiz topilmadi.")
            return ConversationHandler.END
        employer_id, employer_name, city = tg_id, u[1], u[3]

    with db() as con:
        con.execute("""INSERT INTO jobs
            (employer_id,employer_name,title,description,pay,job_type,city,
             status,created_at,is_vip)
            VALUES (?,?,?,?,?,?,?,?,?,0)""",
            (employer_id, employer_name, context.user_data["job_title"],
             context.user_data["job_desc"], context.user_data["job_pay"],
             update.message.text.strip()[:80], city, "active",
             datetime.now().isoformat(timespec="seconds")))

    context.user_data["posting_as_admin"] = False
    await update.message.reply_text(
        "Ish eâloningiz joylashtirildi! â",
        reply_markup=main_menu(
            u[0] if u else None, is_admin(tg_id)
        )
    )
    return ConversationHandler.END


async def my_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u or u[0] != "employer":
        await update.message.reply_text("Bu boâlim ish beruvchilar uchun.")
        return

    with db() as con:
        rows = con.execute("""SELECT id,title,status,is_vip FROM jobs
            WHERE employer_id=? AND status!='deleted' ORDER BY id DESC LIMIT 30""",
            (update.effective_user.id,)).fetchall()

    if not rows:
        await update.message.reply_text("Siz hali eâlon joylashtirmagansiz.")
        return

    for job_id, title, status, vip in rows:
        status_text = {
            "active": "Faol",
            "closed": "Ish oârni toâldi"
        }.get(status, status)
        vip_text = " â­ VIP" if vip else ""
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("â Ish oârni toâldi" if status == "active" else "â»ï¸ Qayta ochish",
                                     callback_data=f"emstatus:{job_id}"),
                InlineKeyboardButton("ð Oâchirish", callback_data=f"emdelete:{job_id}")
            ]
        ])
        await update.message.reply_text(
            f"#{job_id} â {title}\nHolati: {status_text}{vip_text}",
            reply_markup=keyboard
        )


async def employer_job_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    parts = q.data.split(":")
    action, job_id = parts[0], int(parts[1])

    with db() as con:
        row = con.execute(
            "SELECT employer_id,status FROM jobs WHERE id=?", (job_id,)
        ).fetchone()
        if not row or row[0] != q.from_user.id:
            await q.message.reply_text("Bu eâlon sizga tegishli emas.")
            return

        if action == "emdelete":
            con.execute("UPDATE jobs SET status='deleted' WHERE id=?", (job_id,))
            await q.edit_message_text(f"ð Eâlon #{job_id} oâchirildi.")
        else:
            new_status = "closed" if row[1] == "active" else "active"
            con.execute("UPDATE jobs SET status=? WHERE id=?", (new_status, job_id))
            message = "Ish oârni toâldi deb belgilandi. â" if new_status == "closed" else "Eâlon qayta faollashtirildi. â"
            await q.edit_message_text(message)


async def my_applications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with db() as con:
        rows = con.execute("""SELECT j.title,a.created_at FROM applications a
            JOIN jobs j ON j.id=a.job_id WHERE a.student_id=?
            ORDER BY a.id DESC LIMIT 15""", (update.effective_user.id,)).fetchall()
    if not rows:
        await update.message.reply_text("Siz hali hech qanday ishga ariza yubormagansiz.")
        return
    for title, created in rows:
        await update.message.reply_text(f"ð {title}\nYuborilgan vaqt: {created}")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "â¹ï¸ Yordam\nIsh qidirish â faol eâlonlarni koârish.\n"
        "Ish joylashtirish â ish beruvchilar uchun.\n"
        "Mening eâlonlarim â eâlonlaringizni yopish yoki oâchirish.\n"
        "Profilim â roâyxatdan oâtgan maâlumotlaringiz."
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("â Sizda admin huquqi yoâq.")
        return

    keyboard = ReplyKeyboardMarkup([
        ["â Admin eâlon qoâshish"],
        ["ð Barcha eâlonlar", "ð Eâlon oâchirish"],
        ["â­ VIP boshqarish"],
        ["â¬ï¸ Asosiy menyu"]
    ], resize_keyboard=True)
    await update.message.reply_text("ð ADMIN PANEL\nKerakli amalni tanlang:", reply_markup=keyboard)

async def admin_add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Ruxsat yo‘q.")
        return ConversationHandler.END

    context.user_data["admin_adding_job"] = True
    context.user_data["posting_as_admin"] = True

    await update.message.reply_text(
        "➕ Yangi e’lon qo‘shish boshlanadi.\nIsh nomini kiriting:"
    )
    return JOB_TITLE



async def admin_list_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("â Ruxsat yoâq.")
        return
    with db() as con:
        rows = con.execute("""SELECT id,title,status,is_vip,employer_name
            FROM jobs WHERE status!='deleted' ORDER BY id DESC LIMIT 40""").fetchall()
    if not rows:
        await update.message.reply_text("Eâlonlar mavjud emas.")
        return
    for job_id, title, status, vip, employer in rows:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("ð Oâchirish", callback_data=f"addelete:{job_id}"),
            InlineKeyboardButton("â­ VIP yoqish/oâchirish", callback_data=f"vip:{job_id}")
        ]])
        await update.message.reply_text(
            f"#{job_id} {title}\nHolati: {status}\nVIP: {'Ha' if vip else 'Yoâq'}\n"
            f"Ish beruvchi: {employer}",
            reply_markup=keyboard
        )


async def admin_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("â Ruxsat yoâq.")
        return
    await admin_list_jobs(update, context)


async def admin_job_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        await q.message.reply_text("â Sizda admin huquqi yoâq.")
        return

    action, raw_id = q.data.split(":")
    job_id = int(raw_id)
    with db() as con:
        exists = con.execute("SELECT id FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not exists:
            await q.message.reply_text("Eâlon topilmadi.")
            return
        if action == "addelete":
            con.execute("UPDATE jobs SET status='deleted' WHERE id=?", (job_id,))
            await q.edit_message_text(f"ð Eâlon #{job_id} oâchirildi.")
        elif action == "vip":
            con.execute(
                "UPDATE jobs SET is_vip=CASE WHEN is_vip=1 THEN 0 ELSE 1 END WHERE id=?",
                (job_id,)
            )
            new_value = con.execute(
                "SELECT is_vip FROM jobs WHERE id=?", (job_id,)
            ).fetchone()[0]
            await q.edit_message_text(
                f"{'â­ VIP yoqildi' if new_value else 'VIP oâchirildi'} â eâlon #{job_id}."
            )


async def admin_vip_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("â Ruxsat yoâq.")
        return
    with db() as con:
        rows = con.execute("""SELECT id,title,is_vip FROM jobs
            WHERE status='active' ORDER BY id DESC LIMIT 40""").fetchall()
    if not rows:
        await update.message.reply_text("Faol eâlonlar yoâq.")
        return
    for job_id, title, vip in rows:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(
                "â­ VIPni oâchirish" if vip else "â­ VIP qilish",
                callback_data=f"vip:{job_id}"
            )
        ]])
        await update.message.reply_text(
            f"#{job_id} {title}\nVIP: {'Ha' if vip else 'Yoâq'}",
            reply_markup=keyboard
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["posting_as_admin"] = False
    context.user_data["admin_adding_job"] = False
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        "Amal bekor qilindi.",
        reply_markup=main_menu(u[0] if u else None, is_admin(update.effective_user.id))
    )
    return ConversationHandler.END


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    await update.message.reply_text(
        "Asosiy menyu.",
        reply_markup=main_menu(u[0] if u else None, is_admin(update.effective_user.id))
    )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi. Tokenni muhit oâzgaruvchisiga kiriting.")

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
        entry_points=[
            MessageHandler(filters.Regex("^â Ish joylashtirish$"), begin_job),
            MessageHandler(filters.Regex("^â Admin eâlon qoâshish$"), admin_add_entry),
        ],
        states={
            JOB_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_title)],
            JOB_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_desc)],
            JOB_PAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_pay)],
            JOB_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, job_type)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(registration)
    app.add_handler(posting)

    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(MessageHandler(filters.Regex("^ð Admin panel$"), admin_panel))
    app.add_handler(MessageHandler(filters.Regex("^ð Barcha eâlonlar$"), admin_list_jobs))
    app.add_handler(MessageHandler(filters.Regex("^ð Eâlon oâchirish$"), admin_delete_prompt))
    app.add_handler(MessageHandler(filters.Regex("^â­ VIP boshqarish$"), admin_vip_list))
    app.add_handler(MessageHandler(filters.Regex("^ð Mening eâlonlarim$"), my_jobs))
    app.add_handler(MessageHandler(filters.Regex("^â¬ï¸ Asosiy menyu$"), back_to_menu))

    app.add_handler(CallbackQueryHandler(apply_job, pattern=r"^apply:\d+$"))
    app.add_handler(CallbackQueryHandler(employer_job_action, pattern=r"^em(?:status|delete):\d+$"))
    app.add_handler(CallbackQueryHandler(admin_job_action, pattern=r"^(?:addelete|vip):\d+$"))

    app.add_handler(MessageHandler(filters.Regex("^ð Ish qidirish$"), jobs))
    app.add_handler(MessageHandler(filters.Regex("^ð¤ Profilim$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^ð Arizalarim$"), my_applications))
    app.add_handler(MessageHandler(filters.Regex("^â¹ï¸ Yordam$"), help_cmd))

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
