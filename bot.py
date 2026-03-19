import logging
import uuid
import os
from telegram import *
from telegram.ext import *

logging.basicConfig(level=logging.INFO)

# ===== CONFIG =====
BOT_TOKEN = "8206597984:AAFLFaGm20uuCGTFRn541Xo9bRDL3ahp7qs"   # ⚠️ New token use karo
ADMIN_ID = 7702942505

QR_PATH = "qr.png"
CHANNEL = "https://t.me/Shein_Reward"

VOUCHERS = {
    "500": {"price": 25, "file": "data/500.txt"},
    "1000": {"price": 200, "file": "data/1000.txt"}
}

orders = {}
user_history = {}
order_count = 1


# ===== FILE FUNCTIONS =====
def load_codes(file):
    try:
        if not os.path.exists(file):
            return []
        with open(file, "r") as f:
            return [x.strip() for x in f if x.strip()]
    except:
        return []


def save_codes(file, codes):
    os.makedirs(os.path.dirname(file), exist_ok=True)
    with open(file, "w") as f:
        f.write("\n".join(codes))


# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [["🛒 Buy Coupon", "📜 History"], ["💬 Support", "📢 Channel"]]
    await update.message.reply_text("Welcome 👋", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))


# ===== TEXT =====
async def text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text

    if msg == "🛒 Buy Coupon":
        buttons = []
        for k, v in VOUCHERS.items():
            stock = len(load_codes(v["file"]))
            status = f"Stock: {stock}" if stock > 0 else "❌ Out of stock"
            buttons.append([InlineKeyboardButton(f"{k}₹ ({status})", callback_data=f"buy_{k}")])

        await update.message.reply_text("Select:", reply_markup=InlineKeyboardMarkup(buttons))

    elif msg == "📜 History":
        h = user_history.get(update.message.from_user.id, [])
        if not h:
            await update.message.reply_text("No history")
        else:
            await update.message.reply_text("\n".join(h))

    elif msg == "💬 Support":
        await update.message.reply_text("Support: @LexlordD")

    elif msg == "📢 Channel":
        await update.message.reply_text(CHANNEL)

    elif context.user_data.get("await_qty"):
        try:
            qty = int(msg)
            value = context.user_data["voucher"]

            stock = len(load_codes(VOUCHERS[value]["file"]))
            if qty > stock:
                await update.message.reply_text("❌ Not enough stock!")
                context.user_data.clear()
                return

            context.user_data["qty"] = qty
            context.user_data["await_qty"] = False
            await send_payment(update, context)

        except:
            await update.message.reply_text("Enter valid number")


# ===== BUTTON =====
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global order_count
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("buy_"):
        value = data.split("_")[1]
        context.user_data["voucher"] = value

        kb = [
            [InlineKeyboardButton("1", callback_data="q1"),
             InlineKeyboardButton("2", callback_data="q2")],
            [InlineKeyboardButton("Custom", callback_data="custom_qty")]
        ]

        await q.edit_message_text("Select quantity:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("q"):
        qty = int(data[1:])
        context.user_data["qty"] = qty
        await send_payment(q, context)

    elif data == "custom_qty":
        context.user_data["await_qty"] = True
        await q.message.reply_text("Enter custom quantity:")

    elif data == "cancel":
        if "order_id" in context.user_data:
            orders.pop(context.user_data["order_id"], None)

        context.user_data.clear()

        keyboard = [
            ["🛒 Buy Coupon", "📜 History"],
            ["💬 Support", "📢 Channel"]
        ]

        await q.message.reply_text(
            "❌ Your order is Cancelled",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

        await q.message.delete()

    elif data.startswith("approve_"):
        oid = int(data.split("_")[1])
        order = orders.get(oid)
        if not order:
            return

        file = VOUCHERS[order["value"]]["file"]
        codes = load_codes(file)

        if len(codes) < order["qty"]:
            await q.edit_message_text("❌ Stock issue")
            return

        send_codes = []
        for _ in range(order["qty"]):
            send_codes.append(codes.pop(0))

        save_codes(file, codes)

        user_history.setdefault(order["user"], []).append(f"{order['value']} x{order['qty']} Delivered")

        await context.bot.send_message(order["user"], "✅ Approved\n\n" + "\n".join(send_codes))
        await q.edit_message_text("Approved")

    elif data.startswith("reject_"):
        oid = int(data.split("_")[1])
        order = orders.get(oid)
        if order:
            await context.bot.send_message(order["user"], "❌ Rejected")
        await q.edit_message_text("Rejected")


# ===== PAYMENT =====
async def send_payment(source, context):
    global order_count

    user = source.from_user.id if hasattr(source, "from_user") else source.message.chat_id

    value = context.user_data["voucher"]
    qty = context.user_data["qty"]

    stock = len(load_codes(VOUCHERS[value]["file"]))
    if qty > stock:
        await context.bot.send_message(user, "❌ Stock not available")
        return

    total = VOUCHERS[value]["price"] * qty
    txn = str(uuid.uuid4())[:8]

    oid = order_count
    order_count += 1

    orders[oid] = {
        "user": user,
        "value": value,
        "qty": qty,
        "price": total,
        "txn": txn
    }

    context.user_data["order_id"] = oid

    kb = [[InlineKeyboardButton("❌ Cancel", callback_data="cancel")]]

    try:
        with open(QR_PATH, "rb") as qr:
            await context.bot.send_photo(
                chat_id=user,
                photo=qr,
                caption=f"""🧾 Order ID: {oid}
🔐 Txn: {txn}

Voucher: {value}
Qty: {qty}
Total: ₹{total}

📌 Send UTR + Screenshot""",
                reply_markup=InlineKeyboardMarkup(kb)
            )
    except:
        await context.bot.send_message(user, "QR not found ❌")


# ===== PHOTO =====
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "order_id" not in context.user_data:
        return

    oid = context.user_data["order_id"]
    order = orders.get(oid)

    kb = [[InlineKeyboardButton("Approve", callback_data=f"approve_{oid}"),
           InlineKeyboardButton("Reject", callback_data=f"reject_{oid}")]]

    await context.bot.send_photo(
        ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=f"""Payment Proof

Order: {oid}
Txn: {order['txn']}
Amount: ₹{order['price']}
""",
        reply_markup=InlineKeyboardMarkup(kb)
    )

    await update.message.reply_text("⏳ Pending approval")


# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.PHOTO, photo))

    print("Running...")
    app.run_polling()


if __name__ == "__main__":
    main()
