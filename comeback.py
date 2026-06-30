"""
comeback.py
Single-file Telegram Stars bot — Project Comeback
Features:
- Stars payment with auto delivery
- Invoice link generator (/invoice)
- Payment log sent to admin in DM
- Subscriber list (/subscribers)
- Stats (/stats)
- Add/edit products from bot (/addproduct)
"""

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from telegram import (
    Update, LabeledPrice, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    PreCheckoutQueryHandler, MessageHandler, ContextTypes, filters
)

# ═══════════════════════════════════════════════════════════════
#  CONFIG — edit these
# ═══════════════════════════════════════════════════════════════
BOT_TOKEN    = "8863197109:AAHyPGDMXjmiXUQfb-ePB3Ty1BD8LDXKreQ"
ADMIN_IDS    = [8249985938]           # your Telegram user ID
BOT_USERNAME = "@Sjsjksmn_nbot"           # your bot username

# ═══════════════════════════════════════════════════════════════
#  PRODUCTS — add as many as you want
# ═══════════════════════════════════════════════════════════════
PRODUCTS = {
    "access": {
        "name": "500+ categories | 100,000+ videos  | 80,000+ photo  | 1000+Groups",
        "description": "Get premium access instantly",
        "stars": 300,
        "type": "One-time",
        "delivery": (
            "✅ *Payment Confirmed!*\n\n"
            "Dm @supplierteens for collection 📂 🖇️\n\n"
            "Thank you for your purchase! 🙏"
        ),
    },
}

# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════
DB = "comeback.db"

def db_init():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        first_name TEXT,
        product TEXT,
        stars INTEGER,
        payload TEXT UNIQUE,
        charge_id TEXT,
        paid_at TEXT
    )""")
    con.execute("""CREATE TABLE IF NOT EXISTS subscribers (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        product TEXT,
        stars_paid INTEGER,
        subscribed_at TEXT
    )""")
    con.commit()
    con.close()

def db_save(user_id, username, first_name, product, stars, payload, charge_id):
    con = sqlite3.connect(DB)
    con.execute(
        "INSERT OR IGNORE INTO payments (user_id,username,first_name,product,stars,payload,charge_id,paid_at) VALUES (?,?,?,?,?,?,?,?)",
        (user_id, username, first_name, product, stars, payload, charge_id, datetime.now(timezone.utc).isoformat())
    )
    con.execute(
        "INSERT OR REPLACE INTO subscribers (user_id,username,first_name,product,stars_paid,subscribed_at) VALUES (?,?,?,?,?,?)",
        (user_id, username, first_name, product, stars, datetime.now(timezone.utc).isoformat())
    )
    con.commit()
    con.close()

def db_total():
    con = sqlite3.connect(DB)
    r = con.execute("SELECT COALESCE(SUM(stars),0) FROM payments").fetchone()[0]
    con.close()
    return r

def db_24h():
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    con = sqlite3.connect(DB)
    r = con.execute("SELECT COALESCE(SUM(stars),0) FROM payments WHERE paid_at>=?", (since,)).fetchone()[0]
    con.close()
    return r

def db_product_total(product):
    con = sqlite3.connect(DB)
    r = con.execute("SELECT COALESCE(SUM(stars),0) FROM payments WHERE product=?", (product,)).fetchone()[0]
    con.close()
    return r

def db_subscribers():
    con = sqlite3.connect(DB)
    rows = con.execute("SELECT user_id,username,first_name,product,stars_paid,subscribed_at FROM subscribers ORDER BY subscribed_at DESC").fetchall()
    con.close()
    return rows

def db_count_subscribers():
    con = sqlite3.connect(DB)
    r = con.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
    con.close()
    return r

def db_count_orders():
    con = sqlite3.connect(DB)
    r = con.execute("SELECT COUNT(*) FROM payments").fetchone()[0]
    con.close()
    return r

# ═══════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════

def main_menu():
    rows = []
    for key, p in PRODUCTS.items():
        rows.append([InlineKeyboardButton(
            f"⭐ {p['name']} — {p['stars']} Star{'s' if p['stars']>1 else ''}",
            callback_data=f"buy:{key}"
        )])
    return InlineKeyboardMarkup(rows)

def admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="adm:stats"),
         InlineKeyboardButton("👥 Subscribers", callback_data="adm:subs")],
        [InlineKeyboardButton("🔗 Invoice Link", callback_data="adm:invoice")],
        [InlineKeyboardButton("📦 Products", callback_data="adm:products")],
    ])

# ═══════════════════════════════════════════════════════════════
#  USER HANDLERS
# ═══════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS

    text = (
        f"👋 Welcome to *{BOT_USERNAME}*!\n\n"
        f"Purchase with Telegram Stars ⭐\n\n"
        f"Choose a product below:"
    )
    kb = main_menu()

    if is_admin:
        # Add admin panel button
        rows = kb.inline_keyboard + [[InlineKeyboardButton("👮 Admin Panel", callback_data="adm:main")]]
        kb = InlineKeyboardMarkup(rows)

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)


async def buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    p = PRODUCTS.get(key)
    if not p:
        await query.answer("Product not found.", show_alert=True)
        return

    payload = f"pay_{query.from_user.id}_{key}_{int(datetime.now().timestamp())}"

    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=p["name"],
        description=p["description"],
        payload=payload,
        currency="XTR",
        prices=[LabeledPrice(p["name"], p["stars"])],
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💳 Pay Now", pay=True),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]])
    )


async def cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_reply_markup(None)
    await update.callback_query.message.reply_text("❌ Cancelled.", reply_markup=main_menu())


async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    payload  = payment.invoice_payload
    charge_id = payment.telegram_payment_charge_id
    stars    = payment.total_amount
    user     = update.effective_user
    username = f"@{user.username}" if user.username else user.first_name

    # Parse product key
    parts = payload.split("_")
    product_key = parts[2] if len(parts) >= 3 else list(PRODUCTS.keys())[0]
    p = PRODUCTS.get(product_key, list(PRODUCTS.values())[0])

    # Save to DB
    db_save(user.id, username, user.first_name, product_key, stars, payload, charge_id)

    # Deliver to user
    await update.message.reply_text(p["delivery"], parse_mode="Markdown")

    # Stats for log
    all_time    = db_total()
    last_24h    = db_24h()
    prod_total  = db_product_total(product_key)
    total_subs  = db_count_subscribers()
    total_orders = db_count_orders()

    # Log to all admins
    log = (
        f"💰 *New Payment Received!*\n\n"
        f"🤖 Bot: {BOT_USERNAME}\n"
        f"📦 Service: {p['name']}\n"
        f"⭐ Stars: {stars}\n"
        f"💳 {p['type']}\n\n"
        f"👤 User: {username}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🌍 Language: {user.language_code or '—'}\n"
        f"🔗 Payload: `{payload}`\n\n"
        f"📊 *Revenue*\n"
        f"💎 All-time: ⭐ {all_time}\n"
        f"🕐 Last 24h: ⭐ {last_24h}\n"
        f"📦 This product: ⭐ {prod_total}\n\n"
        f"👥 Total Subscribers: {total_subs}\n"
        f"🛒 Total Orders: {total_orders}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, log, parse_mode="Markdown")
        except Exception as e:
            logging.warning(f"Could not send log to admin {admin_id}: {e}")

# ═══════════════════════════════════════════════════════════════
#  ADMIN PANEL CALLBACKS
# ═══════════════════════════════════════════════════════════════

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        await query.answer("🚫 Admins only.", show_alert=True)
        return

    action = query.data  # adm:main / adm:stats / adm:subs / adm:invoice / adm:products

    if action == "adm:main":
        await query.edit_message_text("👮 *Admin Panel*", parse_mode="Markdown", reply_markup=admin_menu())

    elif action == "adm:stats":
        all_time  = db_total()
        last_24h  = db_24h()
        subs      = db_count_subscribers()
        orders    = db_count_orders()
        text = (
            f"📊 *Stats*\n\n"
            f"💎 All-time: ⭐ {all_time}\n"
            f"🕐 Last 24h: ⭐ {last_24h}\n"
            f"👥 Subscribers: {subs}\n"
            f"🛒 Total Orders: {orders}"
        )
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm:main")]]))

    elif action == "adm:subs":
        rows = db_subscribers()
        if not rows:
            text = "👥 No subscribers yet."
        else:
            lines = [f"👥 *Subscribers ({len(rows)}):*\n"]
            for r in rows[:30]:
                uname = r[1] or r[2] or f"ID:{r[0]}"
                lines.append(f"• {uname} — {r[3]} — ⭐{r[4]} — {r[5][:10]}")
            text = "\n".join(lines)
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm:main")]]))

    elif action == "adm:invoice":
        # Generate invoice link for first product
        key = list(PRODUCTS.keys())[0]
        p   = PRODUCTS[key]
        try:
            link = await context.bot.create_invoice_link(
                title=p["name"],
                description=p["description"],
                payload=f"direct_{key}",
                currency="XTR",
                prices=[LabeledPrice(p["name"], p["stars"])]
            )
            text = f"🔗 *Invoice Link:*\n\n`{link}`\n\nLong press the link above to copy."
        except Exception as e:
            text = f"❌ Error: {e}"
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm:main")]]))

    elif action == "adm:products":
        lines = ["📦 *Products:*\n"]
        for key, p in PRODUCTS.items():
            lines.append(f"• {p['name']} — ⭐{p['stars']} — key: `{key}`")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="adm:main")]]))


# ═══════════════════════════════════════════════════════════════
#  ADMIN COMMANDS (text fallback)
# ═══════════════════════════════════════════════════════════════

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text("👮 *Admin Panel*", parse_mode="Markdown", reply_markup=admin_menu())


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    all_time = db_total()
    last_24h = db_24h()
    subs     = db_count_subscribers()
    orders   = db_count_orders()
    await update.message.reply_text(
        f"📊 *Stats*\n\n"
        f"💎 All-time: ⭐ {all_time}\n"
        f"🕐 Last 24h: ⭐ {last_24h}\n"
        f"👥 Subscribers: {subs}\n"
        f"🛒 Total Orders: {orders}",
        parse_mode="Markdown"
    )


async def subscribers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    rows = db_subscribers()
    if not rows:
        await update.message.reply_text("No subscribers yet.")
        return
    lines = [f"👥 *Subscribers ({len(rows)}):*\n"]
    for r in rows[:30]:
        uname = r[1] or r[2] or f"ID:{r[0]}"
        lines.append(f"• {uname} — {r[3]} — ⭐{r[4]} — {r[5][:10]}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def invoice_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    key = list(PRODUCTS.keys())[0]
    p   = PRODUCTS[key]
    try:
        link = await context.bot.create_invoice_link(
            title=p["name"],
            description=p["description"],
            payload=f"direct_{key}",
            currency="XTR",
            prices=[LabeledPrice(p["name"], p["stars"])]
        )
        await update.message.reply_text(
            f"🔗 *Invoice Link:*\n\n`{link}`\n\nLong press to copy & share anywhere.",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(message)s",
        level=logging.INFO
    )
    db_init()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # User
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buy_cb, pattern="^buy:"))
    app.add_handler(CallbackQueryHandler(cancel_cb, pattern="^cancel$"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    # Admin commands
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("subscribers", subscribers_cmd))
    app.add_handler(CommandHandler("invoice", invoice_cmd))

    # Admin panel callbacks
    app.add_handler(CallbackQueryHandler(admin_cb, pattern="^adm:"))

    print("✅ Comeback bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
