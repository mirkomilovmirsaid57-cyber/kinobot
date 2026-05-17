import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from database import db
from config import BOT_TOKEN, ADMIN_IDS

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# ─── START ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await db.add_user(user.id, user.username or "", user.full_name)

    keyboard = [
        [InlineKeyboardButton("🎬 Kino qidirish", callback_data="search_info")],
        [InlineKeyboardButton("💎 Obuna olish", callback_data="subscribe_info")],
        [InlineKeyboardButton("👤 Mening profilim", callback_data="profile")],
    ]
    if user.id in ADMIN_IDS:
        keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])

    await update.message.reply_text(
        f"🎬 *KinoBot*ga xush kelibsiz, {user.first_name}!\n\n"
        "📌 Kino kodini yuboring va filmni oling.\n"
        "💎 Premium kinolar uchun obuna kerak.\n\n"
        "Quyidagi tugmalardan foydalaning:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─── KINO KODI ORQALI QIDIRISH ───────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id

    # Kod formatini tekshirish (masalan: K1234)
    if text.upper().startswith("K") and text[1:].isdigit():
        movie_code = text.upper()
        movie = await db.get_movie_by_code(movie_code)

        if not movie:
            await update.message.reply_text(
                f"❌ *{movie_code}* kodi bilan kino topilmadi.\n"
                "Kodni to'g'ri kiritganingizni tekshiring.",
                parse_mode="Markdown"
            )
            return

        # Premium kinoni tekshirish
        if movie['is_premium']:
            has_sub = await db.check_subscription(user_id)
            if not has_sub:
                keyboard = [[InlineKeyboardButton("💎 Obuna olish", callback_data="subscribe_info")]]
                await update.message.reply_text(
                    f"🔒 *{movie['title']}* — bu premium kino!\n\n"
                    "Bu kinoni ko'rish uchun obuna kerak.\n"
                    "Obuna olish uchun quyidagi tugmani bosing:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return

        # Kinoni yuborish
        caption = (
            f"🎬 *{movie['title']}*\n"
            f"📅 Yil: {movie['year']}\n"
            f"🎭 Janr: {movie['genre']}\n"
            f"⭐ Reyting: {movie['rating']}\n"
            f"📝 {movie['description']}\n\n"
            f"{'💎 Premium kino' if movie['is_premium'] else '🆓 Bepul kino'}"
        )

        if movie['file_id']:
            await update.message.reply_video(
                video=movie['file_id'],
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                caption + f"\n\n🔗 Havola: {movie.get('link', 'Mavjud emas')}",
                parse_mode="Markdown"
            )

        await db.log_view(user_id, movie['id'])
    else:
        await update.message.reply_text(
            "📌 Kino kodini yuboring (masalan: *K1001*)\n"
            "Kod K harfi va raqamlardan iborat bo'ladi.",
            parse_mode="Markdown"
        )


# ─── CALLBACK HANDLERS ───────────────────────────────────────────────────────

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "profile":
        user = await db.get_user(user_id)
        sub = await db.get_subscription(user_id)
        sub_text = f"✅ Faol ({sub['expires_at'].strftime('%d.%m.%Y')} gacha)" if sub else "❌ Obuna yo'q"

        await query.edit_message_text(
            f"👤 *Mening profilim*\n\n"
            f"🆔 ID: `{user_id}`\n"
            f"👤 Ism: {query.from_user.full_name}\n"
            f"💎 Obuna: {sub_text}\n"
            f"🎬 Ko'rilgan kinolar: {user.get('views', 0)} ta",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Obuna olish", callback_data="subscribe_info")],
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
            ])
        )

    elif data == "subscribe_info":
        keyboard = [
            [InlineKeyboardButton("📅 1 oy — 30,000 so'm", callback_data="sub_1month")],
            [InlineKeyboardButton("📅 3 oy — 75,000 so'm", callback_data="sub_3month")],
            [InlineKeyboardButton("📅 1 yil — 250,000 so'm", callback_data="sub_1year")],
            [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")],
        ]
        await query.edit_message_text(
            "💎 *Premium obuna*\n\n"
            "Obuna orqali siz:\n"
            "✅ Barcha premium kinolarni ko'rishingiz\n"
            "✅ HD sifatda tomosha qilishingiz\n"
            "✅ Cheksiz yuklab olishingiz mumkin!\n\n"
            "📌 Tarif tanlang:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("sub_"):
        plans = {
            "sub_1month": ("1 oy", 30000, 30),
            "sub_3month": ("3 oy", 75000, 90),
            "sub_1year": ("1 yil", 250000, 365),
        }
        plan_name, price, days = plans[data]
        context.user_data['pending_sub'] = {'plan': data, 'days': days, 'price': price}

        await query.edit_message_text(
            f"💳 *To'lov ma'lumotlari*\n\n"
            f"📦 Tarif: {plan_name}\n"
            f"💰 Narx: {price:,} so'm\n\n"
            f"📌 To'lovni quyidagi karta raqamiga o'tkazing:\n"
            f"`8600 0000 0000 0000`\n\n"
            f"✅ To'lovdan so'ng chekni adminga yuboring:\n"
            f"@admin_username\n\n"
            f"Admin tasdiqlangandan so'ng obunangiz faollashadi.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="subscribe_info")]
            ])
        )

    elif data == "search_info":
        await query.edit_message_text(
            "🎬 *Kino qidirish*\n\n"
            "Kino kodini yuboring va filmni darhol oling!\n\n"
            "📌 Kod formati: *K* + raqam\n"
            "Masalan: `K1001`, `K2345`\n\n"
            "Kinolar ro'yxatini ko'rish uchun:\n"
            "/kinolar — barcha kinolar\n"
            "/premium — premium kinolar",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
            ])
        )

    elif data == "back_main":
        keyboard = [
            [InlineKeyboardButton("🎬 Kino qidirish", callback_data="search_info")],
            [InlineKeyboardButton("💎 Obuna olish", callback_data="subscribe_info")],
            [InlineKeyboardButton("👤 Mening profilim", callback_data="profile")],
        ]
        if user_id in ADMIN_IDS:
            keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin_panel")])

        await query.edit_message_text(
            "🎬 *KinoBot* — Asosiy menyu\n\n"
            "Kino kodini yuboring yoki quyidagi tugmalardan foydalaning:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "admin_panel" and user_id in ADMIN_IDS:
        stats = await db.get_stats()
        await query.edit_message_text(
            f"⚙️ *Admin panel*\n\n"
            f"📊 Statistika:\n"
            f"👥 Foydalanuvchilar: {stats['users']} ta\n"
            f"🎬 Kinolar: {stats['movies']} ta\n"
            f"💎 Premium foydalanuvchilar: {stats['premium_users']} ta\n"
            f"👁 Bugungi ko'rishlar: {stats['today_views']} ta\n\n"
            f"📌 Buyruqlar:\n"
            f"/addmovie — Kino qo'shish\n"
            f"/delmovie — Kino o'chirish\n"
            f"/givesub [user_id] [days] — Obuna berish\n"
            f"/users — Foydalanuvchilar ro'yxati",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]
            ])
        )


# ─── KINOLAR RO'YXATI ─────────────────────────────────────────────────────────

async def movie_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = await db.get_free_movies()
    if not movies:
        await update.message.reply_text("🎬 Hozircha bepul kinolar yo'q.")
        return

    text = "🎬 *Bepul kinolar ro'yxati:*\n\n"
    for m in movies[:20]:
        text += f"▫️ `{m['code']}` — *{m['title']}* ({m['year']})\n"
    text += "\nKodni yuboring va kinoni oling!"

    await update.message.reply_text(text, parse_mode="Markdown")


async def premium_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = await db.get_premium_movies()
    if not movies:
        await update.message.reply_text("💎 Hozircha premium kinolar yo'q.")
        return

    text = "💎 *Premium kinolar ro'yxati:*\n\n"
    for m in movies[:20]:
        text += f"▫️ `{m['code']}` — *{m['title']}* ({m['year']}) 🔒\n"
    text += "\nObuna oling va barcha kinolarni ko'ring!"

    keyboard = [[InlineKeyboardButton("💎 Obuna olish", callback_data="subscribe_info")]]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─── ADMIN BUYRUQLARI ─────────────────────────────────────────────────────────

async def add_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    await update.message.reply_text(
        "🎬 *Kino qo'shish*\n\n"
        "Quyidagi formatda yuboring:\n\n"
        "`/addmovie Kino nomi | Yil | Janr | Reyting | Tavsif | premium/free`\n\n"
        "Misol:\n"
        "`/addmovie Interstellar | 2014 | Sci-Fi | 8.6 | Kosmik sayohat haqida film | premium`",
        parse_mode="Markdown"
    )

    if len(context.args) == 0:
        return

    try:
        text = " ".join(context.args)
        parts = [p.strip() for p in text.split("|")]
        if len(parts) < 6:
            await update.message.reply_text("❌ Format noto'g'ri. Barcha maydonlarni to'ldiring.")
            return

        title, year, genre, rating, desc, ptype = parts[:6]
        is_premium = ptype.lower() == "premium"

        movie_id = await db.add_movie(title, year, genre, rating, desc, is_premium)
        code = f"K{movie_id:04d}"
        await db.set_movie_code(movie_id, code)

        await update.message.reply_text(
            f"✅ Kino qo'shildi!\n\n"
            f"🎬 *{title}*\n"
            f"📌 Kod: `{code}`\n"
            f"💎 Turi: {'Premium' if is_premium else 'Bepul'}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Xato: {e}")


async def give_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Format: `/givesub [user_id] [kun]`\nMisol: `/givesub 123456789 30`",
            parse_mode="Markdown"
        )
        return

    try:
        target_id = int(context.args[0])
        days = int(context.args[1])
        await db.give_subscription(target_id, days)

        await update.message.reply_text(
            f"✅ Foydalanuvchi `{target_id}` ga {days} kunlik obuna berildi!",
            parse_mode="Markdown"
        )

        try:
            await context.bot.send_message(
                target_id,
                f"🎉 Sizga *{days} kunlik* premium obuna berildi!\n"
                f"Endi barcha premium kinolardan foydalanishingiz mumkin! 🎬",
                parse_mode="Markdown"
            )
        except:
            pass

    except ValueError:
        await update.message.reply_text("❌ User ID va kunlar raqam bo'lishi kerak.")


async def del_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    if not context.args:
        await update.message.reply_text("Format: `/delmovie [KOD]`\nMisol: `/delmovie K1001`", parse_mode="Markdown")
        return

    code = context.args[0].upper()
    deleted = await db.delete_movie_by_code(code)
    if deleted:
        await update.message.reply_text(f"✅ `{code}` kodi bilan kino o'chirildi.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ `{code}` kodi bilan kino topilmadi.", parse_mode="Markdown")


async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    users = await db.get_all_users()
    text = f"👥 *Foydalanuvchilar ({len(users)} ta):*\n\n"
    for u in users[:30]:
        sub = "💎" if u.get('has_sub') else "👤"
        text += f"{sub} `{u['telegram_id']}` — {u['full_name']}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kinolar", movie_list))
    app.add_handler(CommandHandler("premium", premium_list))
    app.add_handler(CommandHandler("addmovie", add_movie))
    app.add_handler(CommandHandler("givesub", give_subscription))
    app.add_handler(CommandHandler("delmovie", del_movie))
    app.add_handler(CommandHandler("users", users_list))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
                
