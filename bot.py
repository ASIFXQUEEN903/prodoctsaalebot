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
UPI_ID = "your_upi_id@okhdfcbank"
UPI_QR_IMAGE_URL = "https://your-domain.com/qr-code.jpg"
UPI_NAME = "Your Business Name"

# ---------- DATABASE ----------
client = MongoClient(MONGO_URI)
db = client["TelegramSaleBot"]
users_col = db["users"]
products_col = db["products"]
categories_col = db["categories"]
recharge_reqs_col = db["recharge_requests"]

# Admin IDs
ADMIN_IDS = [1847314753]

# ---------- LOGGING ----------
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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

def back_button(callback_data):
    return [[InlineKeyboardButton("🔙 Back", callback_data=callback_data)]]

# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    get_user(user_id)
    msg = f"🎉 Welcome {update.effective_user.first_name}!\n\n💎 Use below buttons to explore."
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

# ---------- SINGLE CALLBACK HANDLER ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = get_user(user_id)
    
    logger.info(f"Callback data received: {data} from user {user_id}")
    
    # ========== MAIN MENU ==========
    if data == "main_menu":
        await query.edit_message_text("✨ *Main Menu:*", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== WALLET ==========
    elif data == "wallet":
        text = f"""
💰 *YOUR WALLET*

💵 Balance: ₹{user['wallet']}
📅 Today's Recharge: ₹{user['today_recharge']}
💎 Total Recharge: ₹{user['total_recharge']}
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("main_menu")))
    
    # ========== SUPPORT ==========
    elif data == "support":
        keyboard = [
            [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/your_admin")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text("📞 *Support*\n\nContact admin for any issues.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== RECHARGE ==========
    elif data == "recharge":
        keyboard = [
            [InlineKeyboardButton("💳 UPI Payment", callback_data="upi_payment")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text("💸 *Select Recharge Method*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "upi_payment":
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
        
        keyboard = [
            [InlineKeyboardButton("✅ I have paid", callback_data="paid_screenshot")],
            [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]
        ]
        
        await query.message.delete()
        await query.message.reply_photo(
            photo=UPI_QR_IMAGE_URL,
            caption=f"""
💳 *UPI Payment Details*

🏦 UPI ID: `{UPI_ID}`
💰 Amount: ₹{amount}

After payment, click 'I have paid'
""",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "custom_amount":
        await query.edit_message_text("💸 *Enter amount* (Min ₹10)\n\nSend a number like: 250", parse_mode="Markdown")
        context.user_data["awaiting_custom_amount"] = True
    
    elif data == "paid_screenshot":
        await query.edit_message_text("📸 *Please send payment screenshot*", parse_mode="Markdown")
        context.user_data["awaiting_screenshot"] = True
    
    # ========== PRODUCTS ==========
    elif data == "products":
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("📦 *No products available*", parse_mode="Markdown", reply_markup=main_menu())
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            if product:
                stock = product.get('stock', 0)
                price = cat.get('price', 0)
                stock_emoji = "✅" if stock > 0 else "❌"
                keyboard.append([InlineKeyboardButton(f"📁 {cat['name']} - ₹{price} {stock_emoji} ({stock} left)", callback_data=f"cat_{cat['_id']}")])
            else:
                keyboard.append([InlineKeyboardButton(f"📁 {cat['name']} - No stock", callback_data=f"cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text("🛍️ *Select Category*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== PRODUCT DETAILS ==========
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        if not product:
            await query.edit_message_text(f"📭 *No stock in {cat['name']} category*\n\nPlease check back later.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
        
        stock = product.get('stock', 0)
        price = cat.get('price', 0)
        
        if stock <= 0:
            status = "❌ OUT OF STOCK"
            buy_button = []
        else:
            status = f"✅ IN STOCK ({stock} units left)"
            buy_button = [[InlineKeyboardButton("🛒 BUY NOW", callback_data=f"buy_{product['_id']}")]]
        
        text = f"""
📦 *{cat['name']}*

━━━━━━━━━━━━━━━━━━━━━
💰 *Price:* ₹{price}
📊 *Status:* {status}
━━━━━━━━━━━━━━━━━━━━━

💳 *Your Balance:* ₹{user['wallet']}
"""
        
        keyboard = buy_button + [back_button("products")[0]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== BUY PRODUCT ==========
    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        user = get_user(user_id)
        
        if not product:
            await query.edit_message_text("❌ Product not found.", reply_markup=main_menu())
            return
        
        cat = categories_col.find_one({"_id": product["category_id"]})
        stock_list = product.get('stock_list', [])
        price = cat.get('price', 0) if cat else 0
        
        if len(stock_list) <= 0:
            await query.edit_message_text("❌ *Out of stock!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
            
        if user["wallet"] >= price:
            keyboard = [
                [InlineKeyboardButton("✅ YES, CONFIRM", callback_data=f"confirm_buy_{prod_id}")],
                [InlineKeyboardButton("🔙 Cancel", callback_data="products")]
            ]
            
            await query.edit_message_text(f"""
⚠️ *CONFIRM PURCHASE*

📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{price}
💳 Your Balance: ₹{user['wallet']}
💎 Balance after purchase: ₹{user['wallet'] - price}

Are you sure you want to buy?
""", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            need = price - user["wallet"]
            await query.edit_message_text(f"""
❌ *Insufficient Balance!*

💳 Your Balance: ₹{user['wallet']}
💰 Price: ₹{price}
🔴 Need: ₹{need} more

Please recharge your wallet first.
""", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
    
    elif data.startswith("confirm_buy_"):
        prod_id = data.split("_")[2]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        user = get_user(user_id)
        
        if not product:
            await query.edit_message_text("❌ Product not found.", reply_markup=main_menu())
            return
        
        cat = categories_col.find_one({"_id": product["category_id"]})
        stock_list = product.get('stock_list', [])
        price = cat.get('price', 0) if cat else 0
        
        if len(stock_list) <= 0:
            await query.edit_message_text("❌ *Out of stock!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
            
        if user["wallet"] >= price:
            # Get first item from stock list
            bought_item = stock_list[0]
            new_stock_list = stock_list[1:]
            
            # Update product
            products_col.update_one(
                {"_id": product["_id"]}, 
                {"$set": {"stock_list": new_stock_list, "stock": len(new_stock_list)}}
            )
            update_wallet(user_id, -price)
            
            await query.edit_message_text(f"""
✅ *PURCHASE SUCCESSFUL!*

━━━━━━━━━━━━━━━━━━━━━
📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{price}
💳 Remaining: ₹{user['wallet'] - price}
━━━━━━━━━━━━━━━━━━━━━

🎉 *Here is your purchase:*

{bought_item}

Thank you for shopping! 🙏
""", parse_mode="Markdown", reply_markup=main_menu())
            
            # Notify admin
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"🛒 *Purchase*\n\nUser: {user_id}\nCategory: {cat['name'] if cat else 'Product'}\nAmount: ₹{price}\nStock left: {len(new_stock_list)}", parse_mode="Markdown")
        else:
            need = price - user["wallet"]
            await query.edit_message_text(f"❌ *Insufficient balance!* Need ₹{need} more.", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== ADMIN PANEL ==========
    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        keyboard = [
            [InlineKeyboardButton("📁 Add Category", callback_data="admin_add_cat")],
            [InlineKeyboardButton("🗑️ Remove Category", callback_data="admin_remove_cat")],
            [InlineKeyboardButton("📝 Add Stock", callback_data="admin_add_stock")],
            [InlineKeyboardButton("💰 Edit Category Price", callback_data="admin_edit_price")],
            [InlineKeyboardButton("📋 View Stock", callback_data="admin_view_stock")],
            [InlineKeyboardButton("⏳ Pending Approvals", callback_data="admin_pending")],
            [InlineKeyboardButton("📈 Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ]
        await query.edit_message_text("🔧 *Admin Control Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== ADD CATEGORY (Name and Price) ==========
    elif data == "admin_add_cat":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        await query.edit_message_text("📁 *Step 1/2: Send category name*\n\nExample: `Netflix Account`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_name"
    
    # ========== REMOVE CATEGORY ==========
    elif data == "admin_remove_cat":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ *No categories to remove!*", parse_mode="Markdown")
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            stock_count = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"🗑️ {cat['name']} (₹{cat['price']}) - {stock_count} stock", callback_data=f"remove_cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        
        await query.edit_message_text("🗑️ *Select category to remove*\n\n⚠️ *Warning:* All stock will also be deleted!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("remove_cat_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        cat_id = data.split("_")[2]
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        if cat:
            products_col.delete_many({"category_id": ObjectId(cat_id)})
            categories_col.delete_one({"_id": ObjectId(cat_id)})
            
            await query.edit_message_text(f"✅ *Category Removed!*\n\n📁 {cat['name']}\n\nCategory and all stock deleted.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Category not found!", parse_mode="Markdown")
    
    # ========== ADD STOCK (Line by Line - Only email/password) ==========
    elif data == "admin_add_stock":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ No categories available. First add a category.", parse_mode="Markdown")
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            stock_count = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"📊 {cat['name']} - Stock: {stock_count}", callback_data=f"addstock_cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        
        await query.edit_message_text("📊 *Select category to add stock*\n\nSend email/password line by line.\nEach line will be added to stock.\n\nExample:\n`email: test1@gmail.com | pass: 12345`\n`email: test2@gmail.com | pass: 67890`", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("addstock_cat_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        cat_id = data.split("_")[2]
        context.user_data["stock_category_id"] = cat_id
        
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        # Check if product exists for this category, if not create one
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        if not product:
            products_col.insert_one({
                "category_id": ObjectId(cat_id),
                "stock": 0,
                "stock_list": [],
                "created_at": datetime.now()
            })
            product = products_col.find_one({"category_id": ObjectId(cat_id)})
        
        await query.edit_message_text(f"""
📊 *Adding stock to:* {cat['name']}

*Send email/password line by line.*

Each line will be added to stock.

Example:
`email: user1@gmail.com | pass: pass123`
`email: user2@gmail.com | pass: pass456`

Current stock count: {product.get('stock', 0)}

Type /admin when done adding stock.
""", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_stock_items"
    
    # ========== EDIT CATEGORY PRICE ==========
    elif data == "admin_edit_price":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("No categories available.")
            return
        
        keyboard = []
        for cat in cats:
            keyboard.append([InlineKeyboardButton(f"💰 {cat['name']} - ₹{cat['price']}", callback_data=f"editprice_cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        
        await query.edit_message_text("💰 *Select category to edit price:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("editprice_cat_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        cat_id = data.split("_")[2]
        context.user_data["edit_cat_id"] = cat_id
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        await query.edit_message_text(f"💰 *Current price:* ₹{cat['price']}\n\nSend new price:\n\nExample: `599`", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_price"
    
    # ========== VIEW STOCK ==========
    elif data == "admin_view_stock":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("No categories available.")
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            stock_count = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"📋 {cat['name']} - Stock: {stock_count}", callback_data=f"viewstock_cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        
        await query.edit_message_text("📋 *Select category to view stock*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("viewstock_cat_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        cat_id = data.split("_")[2]
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        if product:
            stock_list = product.get('stock_list', [])
            if not stock_list:
                await query.edit_message_text(f"📋 *{cat['name']}*\n\nNo stock available.", parse_mode="Markdown")
            else:
                stock_text = "\n".join([f"{i+1}. {item}" for i, item in enumerate(stock_list[:20])])
                more = f"\n\n... and {len(stock_list) - 20} more" if len(stock_list) > 20 else ""
                await query.edit_message_text(f"📋 *{cat['name']}*\n\n*Total Stock:* {len(stock_list)}\n\n{stock_text}{more}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("admin_view_stock")))
    
    # ========== PENDING APPROVALS ==========
    elif data == "admin_pending":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
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
                    caption=f"👤 User: `{req['user_id']}`\n💰 Amount: ₹{req['amount']}\n📅 Time: {req['timestamp']}",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            except:
                await query.message.reply_text(f"User: {req['user_id']}\nAmount: ₹{req['amount']}", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== STATISTICS ==========
    elif data == "admin_stats":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        total_users = users_col.count_documents({})
        total_wallet = sum([u.get("wallet", 0) for u in users_col.find({})])
        total_recharge = sum([u.get("total_recharge", 0) for u in users_col.find({})])
        pending_recharge = recharge_reqs_col.count_documents({"status": "pending"})
        total_categories = categories_col.count_documents({})
        total_stock = 0
        for prod in products_col.find({}):
            total_stock += prod.get('stock', 0)
        
        stats = f"""
📊 *BOT STATISTICS*

━━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
📁 Total Categories: {total_categories}
📦 Total Stock Items: {total_stock}
💳 Total Wallet: ₹{total_wallet}
💰 Total Recharge: ₹{total_recharge}
⏳ Pending: {pending_recharge}
━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats, parse_mode="Markdown")
    
    # ========== APPROVE / REJECT ==========
    elif data.startswith("approve_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
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
            await query.edit_message_text(f"✅ Approved! ₹{req['amount']} added.")
            try:
                await context.bot.send_message(req["user_id"], f"✅ *Recharge Approved!*\n\n💰 ₹{req['amount']} added to your wallet.", parse_mode="Markdown")
            except:
                pass
    
    elif data.startswith("reject_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        req_id = data.split("_")[1]
        recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "rejected"}})
        await query.edit_message_text("❌ Rejected.")

# ---------- MESSAGE HANDLERS ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if context.user_data.get("awaiting_screenshot"):
        context.user_data["awaiting_screenshot"] = False
        photo = update.message.photo[-1]
        context.user_data["screenshot_file_id"] = photo.file_id
        await update.message.reply_text("💰 *Enter the amount you paid:*\n\nExample: `250`", parse_mode="Markdown")
        context.user_data["awaiting_amount"] = True

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # ========== CUSTOM AMOUNT ==========
    if context.user_data.get("awaiting_custom_amount"):
        context.user_data["awaiting_custom_amount"] = False
        try:
            amount = int(text)
            if amount < 10:
                await update.message.reply_text("❌ Minimum amount is ₹10")
                return
            context.user_data["recharge_amount"] = amount
            
            keyboard = [
                [InlineKeyboardButton("✅ I have paid", callback_data="paid_screenshot")],
                [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]
            ]
            
            await update.message.reply_photo(
                photo=UPI_QR_IMAGE_URL,
                caption=f"""
💳 *UPI Payment*

🏦 UPI ID: `{UPI_ID}`
💰 Amount: ₹{amount}

Click 'I have paid' after payment
""",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except ValueError:
            await update.message.reply_text("❌ Please send a valid number.")
        return
    
    # ========== ADD CATEGORY - STEP 1: NAME ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_name":
        context.user_data["new_category_name"] = text
        await update.message.reply_text("💰 *Step 2/2: Enter category price (INR)*\n\nExample: `100`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_price"
        return
    
    # ========== ADD CATEGORY - STEP 2: PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_price":
        try:
            price = int(text)
            cat_name = context.user_data["new_category_name"]
            
            existing = categories_col.find_one({"name": cat_name})
            if existing:
                await update.message.reply_text(f"❌ *Category '{cat_name}' already exists!*", parse_mode="Markdown")
            else:
                categories_col.insert_one({
                    "name": cat_name,
                    "price": price,
                    "created_at": datetime.now()
                })
                await update.message.reply_text(f"✅ *Category Added!*\n\n📁 {cat_name}\n💰 ₹{price}\n\nNow use 'Add Stock' to add email/password stock.", parse_mode="Markdown")
            
            context.user_data.pop("admin_action")
            context.user_data.pop("new_category_name")
        except ValueError:
            await update.message.reply_text("❌ *Invalid price!* Send a number.", parse_mode="Markdown")
        return
    
    # ========== ADD STOCK ITEMS (Line by Line - Only email/password) ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_stock_items":
        lines = text.split('\n')
        cat_id = context.user_data.get("stock_category_id")
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        
        if not product:
            await update.message.reply_text("❌ Product not found!", parse_mode="Markdown")
            context.user_data.pop("admin_action")
            context.user_data.pop("stock_category_id")
            return
        
        current_stock = product.get('stock_list', [])
        added = 0
        
        for line in lines:
            line = line.strip()
            if line:
                current_stock.append(line)
                added += 1
        
        # Update product
        products_col.update_one(
            {"_id": product["_id"]},
            {"$set": {"stock_list": current_stock, "stock": len(current_stock)}}
        )
        
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        await update.message.reply_text(f"✅ *Stock Added!*\n\n📁 {cat['name']}\n➕ Added: {added} items\n📊 Total stock: {len(current_stock)} items\n\nYou can continue sending more items line by line.\nType /admin when done.", parse_mode="Markdown")
        # Keep the action active for more stock addition
    
    # ========== EDIT CATEGORY PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "edit_price":
        try:
            new_price = int(text)
            cat_id = context.user_data["edit_cat_id"]
            cat = categories_col.find_one({"_id": ObjectId(cat_id)})
            categories_col.update_one({"_id": ObjectId(cat_id)}, {"$set": {"price": new_price}})
            await update.message.reply_text(f"✅ *Price updated!*\n\n📁 {cat['name']}\n💰 Old: ₹{cat['price']}\n💰 New: ₹{new_price}", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ *Invalid price!* Send a number.", parse_mode="Markdown")
        context.user_data.pop("admin_action")
        context.user_data.pop("edit_cat_id")
        return
    
    # ========== USER RECHARGE ==========
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
            await update.message.reply_text("✅ *Recharge request submitted!*\n\nAdmin will verify and approve shortly.", parse_mode="Markdown")
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"💰 *New Recharge Request*\n\n👤 User: `{user_id}`\n💵 Amount: ₹{amount}\n\n🔍 Check /admin", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ *Invalid amount!* Send a number.", parse_mode="Markdown")

# ---------- ADMIN COMMAND ----------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🔒 *Unauthorized Access*", parse_mode="Markdown")
        return
    
    keyboard = [
        [InlineKeyboardButton("📁 Add Category", callback_data="admin_add_cat")],
        [InlineKeyboardButton("🗑️ Remove Category", callback_data="admin_remove_cat")],
        [InlineKeyboardButton("📝 Add Stock", callback_data="admin_add_stock")],
        [InlineKeyboardButton("💰 Edit Category Price", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📋 View Stock", callback_data="admin_view_stock")],
        [InlineKeyboardButton("⏳ Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("📈 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
    ]
    await update.message.reply_text("🔧 *Admin Control Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Bot is running...")
    print(f"Admin ID: {ADMIN_IDS[0]}")
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
