import os
import logging
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient

# ---------- CONFIG ----------
TOKEN = "8862940536:AAF-mUV1F979xcueVNkNt22211Ir7gToMkc"
MONGO_URI = "mongodb+srv://userbot:userbot@cluster0.iweqz.mongodb.net/test?retryWrites=true&w=majority"

# UPI Configuration
UPI_ID = "your_upi_id@okhdfcbank"  # Change to your UPI ID
UPI_QR_IMAGE_URL = "https://your-domain.com/qr-code.jpg"  # Apne QR code image ka link yahan daalein
UPI_NAME = "Your Business Name"

# ---------- DATABASE ----------
client = MongoClient(MONGO_URI)
db = client["TelegramSaleBot"]
users_col = db["users"]
products_col = db["products"]
categories_col = db["categories"]
recharge_reqs_col = db["recharge_requests"]

# Admin ID (updated)
ADMIN_IDS = [1847314753]

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
    msg = f"""
🎉 *Welcome {update.effective_user.first_name}!*

💎 Your one-stop shop for digital products

👇 *Use below buttons to explore*
"""
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = get_user(user_id)

    if data == "main_menu":
        await query.edit_message_text("✨ *Main Menu:*", parse_mode="Markdown", reply_markup=main_menu())

    elif data == "wallet":
        text = f"""
💰 *YOUR WALLET*

💵 *Balance:* ₹{user['wallet']}
📅 *Today's Recharge:* ₹{user['today_recharge']}
💎 *Total Recharge:* ₹{user['total_recharge']}

Use 'Recharge' button to add funds.
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=wallet_menu())

    elif data == "support":
        await query.edit_message_text("📞 *Support*\n\nFor any issues or queries, contact our admin.", parse_mode="Markdown", reply_markup=support_menu())

    elif data == "recharge":
        keyboard = [
            [InlineKeyboardButton("💳 UPI Payment", callback_data="upi_payment")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text("💸 *Select Recharge Method*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "upi_payment":
        # Show amount selection
        keyboard = [
            [InlineKeyboardButton("₹10", callback_data="amount_10"),
             InlineKeyboardButton("₹50", callback_data="amount_50"),
             InlineKeyboardButton("₹100", callback_data="amount_100")],
            [InlineKeyboardButton("₹200", callback_data="amount_200"),
             InlineKeyboardButton("₹500", callback_data="amount_500"),
             InlineKeyboardButton("₹1000", callback_data="amount_1000")],
            [InlineKeyboardButton("💰 Custom Amount", callback_data="custom_amount")],
            [InlineKeyboardButton("🔙 Back", callback_data="recharge")]
        ]
        await query.edit_message_text("💵 *Select Recharge Amount*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("amount_"):
        amount = int(data.split("_")[1])
        context.user_data["recharge_amount"] = amount
        
        # Show QR code image (external link) with UPI details
        keyboard = [
            [InlineKeyboardButton("✅ I have paid", callback_data="paid_screenshot")],
            [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]
        ]
        
        await query.message.delete()
        await query.message.reply_photo(
            photo=UPI_QR_IMAGE_URL,
            caption=f"""
💳 *UPI Payment Details*

━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
👤 *Pay to:* {UPI_NAME}
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━

📱 *How to pay:*
1️⃣ Open Google Pay / PhonePe / Paytm
2️⃣ Scan QR code or enter UPI ID
3️⃣ Pay ₹{amount}
4️⃣ Click 'I have paid' button

⚠️ *After payment, send screenshot for verification*
""",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "custom_amount":
        await query.edit_message_text("💸 *Enter custom amount* (Min ₹10)\n\nSend a number like: `250`", parse_mode="Markdown")
        context.user_data["awaiting_custom_amount"] = True

    elif data == "paid_screenshot":
        await query.edit_message_text("📸 *Please send payment screenshot*\n\nTake a screenshot of your payment transaction and send here.\n\n*Important:* Screenshot should clearly show Transaction ID and Amount.", parse_mode="Markdown")
        context.user_data["awaiting_screenshot"] = True

    elif data == "products":
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("📦 *No products available*\n\nCheck back later!", parse_mode="Markdown", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"cat_{cat['_id']}")] for cat in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("🛍️ *Product Categories*\n\nSelect a category:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        products = list(products_col.find({"category_id": ObjectId(cat_id)}))
        if not products:
            await query.edit_message_text("📭 *No products in this category*", parse_mode="Markdown", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(f"📦 {p['name']} - ₹{p['price']} (Stock: {p['stock']})", callback_data=f"buy_{p['_id']}")] for p in products]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="products")])
        await query.edit_message_text("🛒 *Available Products*\n\nTap to buy:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        if not product:
            await query.edit_message_text("❌ Product not found.", reply_markup=main_menu())
            return
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Buy", callback_data=f"confirm_buy_{prod_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="products")]
        ]
        
        text = f"""
📦 *{product['name']}*

💰 *Price:* ₹{product['price']}
📊 *Stock:* {product['stock']} units

📝 *Details:*
{product['details']}

💳 *Your Balance:* ₹{user['wallet']}

Tap 'Confirm Buy' to purchase.
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("confirm_buy_"):
        prod_id = data.split("_")[2]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        user = get_user(user_id)
        
        if not product:
            await query.edit_message_text("❌ Product not found.", reply_markup=main_menu())
            return
            
        if user["wallet"] >= product["price"]:
            if product["stock"] > 0:
                new_stock = product["stock"] - 1
                products_col.update_one({"_id": product["_id"]}, {"$set": {"stock": new_stock}})
                update_wallet(user_id, -product["price"])
                await query.edit_message_text(f"""
✅ *Purchase Successful!*

━━━━━━━━━━━━━━━━━━━━━
📦 *Product:* {product['name']}
💰 *Amount:* ₹{product['price']}
💳 *Balance:* ₹{user['wallet'] - product['price']}
━━━━━━━━━━━━━━━━━━━━━

📝 *Product Details:*
{product['details']}

Thanks for shopping! 🎉
""", parse_mode="Markdown", reply_markup=main_menu())
            else:
                await query.edit_message_text("❌ *Out of stock!*\n\nThis product is currently unavailable.", parse_mode="Markdown", reply_markup=main_menu())
        else:
            need = product["price"] - user["wallet"]
            await query.edit_message_text(f"""
❌ *Insufficient Balance!*

💳 *Your Balance:* ₹{user['wallet']}
💰 *Product Price:* ₹{product['price']}
🔴 *Need more:* ₹{need}

Please recharge your wallet first.
""", parse_mode="Markdown", reply_markup=main_menu())

# ---------- ADMIN PANEL ----------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("🔒 *Unauthorized Access*", parse_mode="Markdown")
        return
    keyboard = [
        [InlineKeyboardButton("📁 Add Category", callback_data="admin_add_cat")],
        [InlineKeyboardButton("📦 Add Product", callback_data="admin_add_prod")],
        [InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📊 Edit Stock", callback_data="admin_edit_stock")],
        [InlineKeyboardButton("⏳ Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("📈 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text("🔧 *Admin Control Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    if user_id not in ADMIN_IDS:
        await query.edit_message_text("🔒 Unauthorized.")
        return

    if data == "admin_add_cat":
        await query.edit_message_text("📁 *Send category name:*", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat"

    elif data == "admin_add_prod":
        await query.edit_message_text("📦 *Send product info in format:*\n\n`name|price|stock|details|category_name`\n\nExample:\n`iPhone 14|50000|10|Brand new sealed|Electronics`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_prod"

    elif data == "admin_edit_price":
        prods = list(products_col.find({}))
        if not prods:
            await query.edit_message_text("No products available.")
            return
        keyboard = [[InlineKeyboardButton(f"{p['name']} - ₹{p['price']}", callback_data=f"editprice_{p['_id']}")] for p in prods]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("💰 *Select product to edit price:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_edit_stock":
        prods = list(products_col.find({}))
        if not prods:
            await query.edit_message_text("No products available.")
            return
        keyboard = [[InlineKeyboardButton(f"{p['name']} - Stock: {p['stock']}", callback_data=f"editstock_{p['_id']}")] for p in prods]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("📊 *Select product to edit stock:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("editprice_"):
        prod_id = data.split("_")[1]
        context.user_data["edit_prod_id"] = prod_id
        await query.edit_message_text("💰 *Send new price (number only):*", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_price"

    elif data.startswith("editstock_"):
        prod_id = data.split("_")[1]
        context.user_data["edit_prod_id"] = prod_id
        await query.edit_message_text("📊 *Send new stock quantity (number only):*", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_stock"

    elif data == "admin_pending":
        pending = list(recharge_reqs_col.find({"status": "pending"}))
        if not pending:
            await query.edit_message_text("✅ No pending requests.")
            return
        for req in pending:
            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{req['_id']}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{req['_id']}")
            ]]
            try:
                await query.message.reply_photo(
                    photo=req["screenshot_file_id"],
                    caption=f"👤 *User:* `{req['user_id']}`\n💰 *Amount:* ₹{req['amount']}\n📅 *Time:* {req['timestamp']}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await query.message.reply_text(f"Request ID: {req['_id']}\nUser: {req['user_id']}\nAmount: ₹{req['amount']}", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_stats":
        total_users = users_col.count_documents({})
        total_wallet = sum([u.get("wallet", 0) for u in users_col.find({})])
        total_recharge = sum([u.get("total_recharge", 0) for u in users_col.find({})])
        pending_recharge = recharge_reqs_col.count_documents({"status": "pending"})
        total_products = products_col.count_documents({})
        
        stats = f"""
📊 *BOT STATISTICS*

━━━━━━━━━━━━━━━━━━━━━
👥 *Total Users:* {total_users}
💳 *Total Wallet:* ₹{total_wallet}
💰 *Total Recharge:* ₹{total_recharge}
⏳ *Pending Requests:* {pending_recharge}
📦 *Total Products:* {total_products}
━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats, parse_mode="Markdown")

    elif data.startswith("approve_"):
        req_id = data.split("_")[1]
        req = recharge_reqs_col.find_one({"_id": ObjectId(req_id)})
        if req and req["status"] == "pending":
            update_wallet(req["user_id"], req["amount"])
            users_col.update_one(
                {"user_id": req["user_id"]}, 
                {"$inc": {"total_recharge": req["amount"], "today_recharge": req["amount"]},
                 "$set": {"last_recharge_date": datetime.now().strftime("%Y-%m-%d")}}
            )
            recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "approved"}})
            await query.edit_message_text(f"✅ Approved! ₹{req['amount']} added to user's wallet.")
            try:
                await context.bot.send_message(req["user_id"], f"✅ *Recharge Approved!*\n\n💰 ₹{req['amount']} has been added to your wallet.", parse_mode="Markdown")
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
        amount = context.user_data.get("recharge_amount", 0)
        context.user_data["screenshot_file_id"] = file_id
        context.user_data["awaiting_amount"] = True
        await update.message.reply_text(f"💰 *Amount:* ₹{amount}\n\n✅ *Screenshot received!*\n\nNow please send the exact amount you paid:", parse_mode="Markdown")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Handle custom amount
    if context.user_data.get("awaiting_custom_amount"):
        context.user_data["awaiting_custom_amount"] = False
        try:
            amount = int(text)
            if amount < 10:
                await update.message.reply_text("❌ Minimum amount is ₹10")
                return
            context.user_data["recharge_amount"] = amount
            
            # Show QR code image with UPI details
            keyboard = [
                [InlineKeyboardButton("✅ I have paid", callback_data="paid_screenshot")],
                [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]
            ]
            
            await update.message.reply_photo(
                photo=UPI_QR_IMAGE_URL,
                caption=f"""
💳 *UPI Payment Details*

━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
👤 *Pay to:* {UPI_NAME}
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━

📱 *How to pay:*
1️⃣ Open any UPI app (GPay/PhonePe/Paytm)
2️⃣ Scan QR code or enter UPI ID
3️⃣ Pay ₹{amount}
4️⃣ Click 'I have paid' button

⚠️ *After payment, send screenshot for verification*
""",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ Please send a valid number.")
        return

    # Admin actions
    if user_id in ADMIN_IDS:
        if context.user_data.get("admin_action") == "add_cat":
            categories_col.insert_one({"name": text})
            await update.message.reply_text(f"✅ Category '{text}' added successfully!")
            context.user_data.pop("admin_action")
            return

        elif context.user_data.get("admin_action") == "add_prod":
            parts = text.split("|")
            if len(parts) == 5:
                name, price, stock, details, cat_name = parts
                cat = categories_col.find_one({"name": cat_name.strip()})
                if cat:
                    products_col.insert_one({
                        "name": name.strip(),
                        "price": int(price),
                        "stock": int(stock),
                        "details": details.strip(),
                        "category_id": cat["_id"]
                    })
                    await update.message.reply_text(f"✅ Product '{name}' added successfully!")
                else:
                    await update.message.reply_text(f"❌ Category '{cat_name}' not found. Create category first.")
            else:
                await update.message.reply_text("❌ Invalid format. Use: name|price|stock|details|category_name")
            context.user_data.pop("admin_action")
            return

        elif context.user_data.get("admin_action") == "edit_price":
            try:
                new_price = int(text)
                prod_id = context.user_data["edit_prod_id"]
                products_col.update_one({"_id": ObjectId(prod_id)}, {"$set": {"price": new_price}})
                await update.message.reply_text(f"✅ Price updated to ₹{new_price}!")
            except:
                await update.message.reply_text("❌ Invalid number.")
            context.user_data.pop("admin_action")
            return

        elif context.user_data.get("admin_action") == "edit_stock":
            try:
                new_stock = int(text)
                prod_id = context.user_data["edit_prod_id"]
                products_col.update_one({"_id": ObjectId(prod_id)}, {"$set": {"stock": new_stock}})
                await update.message.reply_text(f"✅ Stock updated to {new_stock} units!")
            except:
                await update.message.reply_text("❌ Invalid number.")
            context.user_data.pop("admin_action")
            return

    # User recharge amount entry (after screenshot)
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
            await update.message.reply_text("✅ *Recharge request submitted!*\n\nAdmin will verify and approve shortly.\n\nThank you for your patience! 🙏", parse_mode="Markdown")
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"💰 *New Recharge Request*\n\n👤 User: `{user_id}`\n💵 Amount: ₹{amount}\n\n🔍 Check /admin panel for pending approvals!", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid amount. Please send a number.")

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(admin_button_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
