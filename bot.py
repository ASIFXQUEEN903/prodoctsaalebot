import os
import logging
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ---------- CONFIG ----------
TOKEN = "8862940536:AAF-mUV1F979xcueVNkNt22211Ir7gToMkc"
MONGO_URI = "mongodb+srv://userbot:userbot@cluster0.iweqz.mongodb.net/test?retryWrites=true&w=majority"

# ---------- DATABASE ----------
client = MongoClient(MONGO_URI)
db = client["TelegramSaleBot"]
users_col = db["users"]
products_col = db["products"]
categories_col = db["categories"]
recharge_reqs_col = db["recharge_requests"]
pending_buy_col = db["pending_buy"]

# Admin IDs (add your Telegram user IDs)
ADMIN_IDS = [123456789, 987654321]

# ---------- LOGGING ----------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# ---------- HELPER FUNCTIONS ----------
def get_user(user_id):
    user = users_col.find_one({"user_id": user_id})
    if not user:
        user = {
            "user_id": user_id,
            "wallet": 0,
            "total_recharge": 0,
            "today_recharge": 0,
            "last_recharge_date": None
        }
        users_col.insert_one(user)
    return user

def update_wallet(user_id, amount):
    users_col.update_one({"user_id": user_id}, {"$inc": {"wallet": amount}})

def reset_daily_recharge():
    today = datetime.now().strftime("%Y-%m-%d")
    users_col.update_many(
        {"last_recharge_date": {"$ne": today}},
        {"$set": {"today_recharge": 0, "last_recharge_date": today}}
    )

# ---------- USER KEYBOARDS ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("👛 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("🛍️ Products", callback_data="products")],
        [InlineKeyboardButton("💰 Recharge", callback_data="recharge")],
        [InlineKeyboardButton("ℹ️ Support", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def wallet_menu():
    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

def support_menu():
    keyboard = [[InlineKeyboardButton("📞 Contact Admin", url="https://t.me/your_admin")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
    return InlineKeyboardMarkup(keyboard)

# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user(user_id)
    msg = f"Welcome {update.effective_user.first_name}!\n\nUse below buttons to explore."
    await update.message.reply_text(msg, reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = get_user(user_id)

    if data == "main_menu":
        await query.edit_message_text("Main Menu:", reply_markup=main_menu())

    elif data == "wallet":
        text = f"💰 Your Wallet Balance: ₹{user['wallet']}\n📅 Today's Recharge: ₹{user['today_recharge']}\n💵 Total Recharge: ₹{user['total_recharge']}"
        await query.edit_message_text(text, reply_markup=wallet_menu())

    elif data == "support":
        await query.edit_message_text("For support, contact admin:", reply_markup=support_menu())

    elif data == "recharge":
        keyboard = [[InlineKeyboardButton("UPI Payment", callback_data="upi_payment")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text("Select payment method:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "upi_payment":
        keyboard = [[InlineKeyboardButton("Pay via UPI", url="https://upier.app/your_upi_id")],
                    [InlineKeyboardButton("I have paid", callback_data="paid_screenshot")],
                    [InlineKeyboardButton("🔙 Back", callback_data="recharge")]]
        await query.edit_message_text("UPI ID: `your_upi_id@okhdfcbank`\n\nSend payment and click 'I have paid'", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "paid_screenshot":
        await query.edit_message_text("Please send the payment screenshot as a photo.")
        context.user_data["awaiting_screenshot"] = True

    elif data == "products":
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("No products available.", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(cat["name"], callback_data=f"cat_{cat['_id']}")] for cat in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("Select category:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        products = list(products_col.find({"category_id": ObjectId(cat_id)}))
        if not products:
            await query.edit_message_text("No products in this category.", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"buy_{p['_id']}")] for p in products]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="products")])
        await query.edit_message_text("Choose product:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        if not product:
            await query.edit_message_text("Product not found.", reply_markup=main_menu())
            return
        if user["wallet"] >= product["price"]:
            # Process buy
            if product["stock"] > 0:
                new_stock = product["stock"] - 1
                products_col.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
                update_wallet(user_id, -product["price"])
                await query.edit_message_text(f"✅ Purchased {product['name']}!\nDetails: {product['details']}", reply_markup=main_menu())
            else:
                await query.edit_message_text("❌ Out of stock.", reply_markup=main_menu())
        else:
            need = product["price"] - user["wallet"]
            await query.edit_message_text(f"Insufficient balance. Need ₹{need} more. Please recharge.", reply_markup=main_menu())

# ---------- ADMIN PANEL ----------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Unauthorized.")
        return
    keyboard = [
        [InlineKeyboardButton("➕ Add Category", callback_data="admin_add_cat")],
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_add_prod")],
        [InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📦 Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text("Admin Panel", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("Unauthorized.")
        return

    if data == "admin_add_cat":
        await query.edit_message_text("Send category name:")
        context.user_data["admin_action"] = "add_cat"

    elif data == "admin_add_prod":
        await query.edit_message_text("Send product info in format: name|price|stock|details|category_name")
        context.user_data["admin_action"] = "add_prod"

    elif data == "admin_edit_price":
        prods = list(products_col.find({}))
        if not prods:
            await query.edit_message_text("No products.")
            return
        keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"editprice_{p['_id']}")] for p in prods]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("Select product to edit price:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("editprice_"):
        prod_id = data.split("_")[1]
        context.user_data["edit_prod_id"] = prod_id
        await query.edit_message_text("Send new price (number):")
        context.user_data["admin_action"] = "edit_price"

    elif data == "admin_pending":
        pending = list(recharge_reqs_col.find({"status": "pending"}))
        if not pending:
            await query.edit_message_text("No pending requests.")
            return
        for req in pending:
            keyboard = [[InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['_id']}"),
                         InlineKeyboardButton("❌ Reject", callback_data=f"reject_{req['_id']}")]]
            await query.message.reply_photo(photo=req["screenshot_file_id"],
                                            caption=f"User: {req['user_id']}\nAmount: ₹{req['amount']}",
                                            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("approve_"):
        req_id = data.split("_")[1]
        req = recharge_reqs_col.find_one({"_id": ObjectId(req_id)})
        if req:
            update_wallet(req["user_id"], req["amount"])
            users_col.update_one({"user_id": req["user_id"]}, {"$inc": {"total_recharge": req["amount"], "today_recharge": req["amount"]}})
            recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "approved"}})
            await query.edit_message_text("✅ Approved. Wallet updated.")
            try:
                await context.bot.send_message(req["user_id"], f"✅ ₹{req['amount']} added to your wallet.")
            except:
                pass

    elif data.startswith("reject_"):
        req_id = data.split("_")[1]
        recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "rejected"}})
        await query.edit_message_text("❌ Rejected.")

# ---------- RECEIVE SCREENSHOT ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("awaiting_screenshot"):
        context.user_data["awaiting_screenshot"] = False
        photo = update.message.photo[-1]
        file_id = photo.file_id
        await update.message.reply_text("Enter recharge amount (in ₹):")
        context.user_data["screenshot_file_id"] = file_id
        context.user_data["awaiting_amount"] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Admin actions
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat":
        categories_col.insert_one({"name": text})
        await update.message.reply_text("Category added.")
        context.user_data.pop("admin_action")
        return

    elif user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_prod":
        parts = text.split("|")
        if len(parts) == 5:
            name, price, stock, details, cat_name = parts
            cat = categories_col.find_one({"name": cat_name})
            if cat:
                products_col.insert_one({
                    "name": name,
                    "price": int(price),
                    "stock": int(stock),
                    "details": details,
                    "category_id": cat["_id"]
                })
                await update.message.reply_text("Product added.")
            else:
                await update.message.reply_text("Category not found.")
        else:
            await update.message.reply_text("Invalid format. Use: name|price|stock|details|category_name")
        context.user_data.pop("admin_action")
        return

    elif user_id in ADMIN_IDS and context.user_data.get("admin_action") == "edit_price":
        try:
            new_price = int(text)
            prod_id = context.user_data["edit_prod_id"]
            products_col.update_one({"_id": ObjectId(prod_id)}, {"$set": {"price": new_price}})
            await update.message.reply_text("Price updated.")
        except:
            await update.message.reply_text("Invalid number.")
        context.user_data.pop("admin_action")
        return

    # User recharge amount entry
    if context.user_data.get("awaiting_amount"):
        context.user_data["awaiting_amount"] = False
        try:
            amount = int(text)
            file_id = context.user_data["screenshot_file_id"]
            recharge_reqs_col.insert_one({
                "user_id": user_id,
                "amount": amount,
                "screenshot_file_id": file_id,
                "status": "pending",
                "timestamp": datetime.now()
            })
            await update.message.reply_text("Recharge request sent to admin.")
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"New recharge request from {user_id} for ₹{amount}")
        except:
            await update.message.reply_text("Invalid amount.")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
