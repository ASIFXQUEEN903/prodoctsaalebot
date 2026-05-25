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

# ---------- FIX OLD CATEGORIES ----------
def fix_old_categories():
    """Add missing price field to old categories"""
    cats = categories_col.find({})
    for cat in cats:
        if 'price' not in cat:
            categories_col.update_one({"_id": cat["_id"]}, {"$set": {"price": 0}})
            logger.info(f"Fixed category: {cat['name']} - added price=0")
    
    # Fix products without stock_list
    prods = products_col.find({})
    for prod in prods:
        if 'stock_list' not in prod:
            products_col.update_one({"_id": prod["_id"]}, {"$set": {"stock_list": [], "stock": 0}})
            logger.info(f"Fixed product: added empty stock_list")

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

# ---------- CALLBACK HANDLER ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = get_user(user_id)
    
    logger.info(f"📩 Callback: {data} from {user_id}")
    
    # ========== MAIN MENU ==========
    if data == "main_menu":
        await query.edit_message_text("✨ *Main Menu:*", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== WALLET ==========
    elif data == "wallet":
        text = f"💰 *Balance:* ₹{user['wallet']}\n📅 *Today:* ₹{user['today_recharge']}\n💎 *Total:* ₹{user['total_recharge']}"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("main_menu")))
    
    # ========== SUPPORT ==========
    elif data == "support":
        keyboard = [[InlineKeyboardButton("📞 Contact Admin", url="https://t.me/your_admin")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text("📞 *Support*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== RECHARGE ==========
    elif data == "recharge":
        keyboard = [[InlineKeyboardButton("💳 UPI Payment", callback_data="upi_payment")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text("💸 *Recharge*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "upi_payment":
        keyboard = [
            [InlineKeyboardButton("₹10", callback_data="amount_10"), InlineKeyboardButton("₹50", callback_data="amount_50"), InlineKeyboardButton("₹100", callback_data="amount_100")],
            [InlineKeyboardButton("₹200", callback_data="amount_200"), InlineKeyboardButton("₹500", callback_data="amount_500"), InlineKeyboardButton("₹1000", callback_data="amount_1000")],
            [InlineKeyboardButton("💰 Custom", callback_data="custom_amount")], 
            [InlineKeyboardButton("🔙 Back", callback_data="recharge")]
        ]
        await query.edit_message_text("💵 *Select Amount*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("amount_"):
        amount = int(data.split("_")[1])
        context.user_data["recharge_amount"] = amount
        keyboard = [[InlineKeyboardButton("✅ Paid", callback_data="paid_screenshot")], [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]]
        await query.message.delete()
        await query.message.reply_photo(photo=UPI_QR_IMAGE_URL, caption=f"UPI: `{UPI_ID}`\nAmount: ₹{amount}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "custom_amount":
        await query.edit_message_text("💰 *Enter amount:*", parse_mode="Markdown")
        context.user_data["awaiting_custom_amount"] = True
    
    elif data == "paid_screenshot":
        await query.edit_message_text("📸 *Send payment screenshot*", parse_mode="Markdown")
        context.user_data["awaiting_screenshot"] = True
    
    # ========== PRODUCTS (FIXED - with safe price access) ==========
    elif data == "products":
        logger.info("📦 Products button clicked")
        cats = list(categories_col.find({}))
        logger.info(f"📁 Found {len(cats)} categories")
        
        if not cats:
            await query.edit_message_text("📦 *No products available*\n\nAdd categories from admin panel first.", parse_mode="Markdown", reply_markup=main_menu())
            return
        
        keyboard = []
        for cat in cats:
            # Safe price access - if price missing, use 0
            cat_price = cat.get('price', 0)
            
            # Find product for this category
            product = products_col.find_one({"category_id": cat["_id"]})
            stock = product.get('stock', 0) if product else 0
            emoji = "✅" if stock > 0 else "❌"
            button_text = f"📁 {cat['name']} - ₹{cat_price} {emoji} ({stock})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"cat_{cat['_id']}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("🛍️ *Select Category*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== CATEGORY CLICK ==========
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        logger.info(f"📁 Category clicked: {cat_id}")
        
        # Get category
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        if not cat:
            await query.edit_message_text("❌ Category not found!", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
        
        # Safe price access
        cat_price = cat.get('price', 0)
        
        # Get product for this category
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        
        if not product or product.get('stock', 0) <= 0:
            await query.edit_message_text(f"❌ *{cat['name']} - Out of stock!*\n\nNo stock available. Please check back later.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
        
        stock = product.get('stock', 0)
        keyboard = [
            [InlineKeyboardButton("🛒 BUY NOW", callback_data=f"buy_{product['_id']}")],
            [InlineKeyboardButton("🔙 Back", callback_data="products")]
        ]
        
        text = f"""
📦 *{cat['name']}*

━━━━━━━━━━━━━━━━━━━━━
💰 *Price:* ₹{cat_price}
📊 *Stock:* {stock} units left
━━━━━━━━━━━━━━━━━━━━━

💳 *Your Balance:* ₹{user['wallet']}

Tap BUY NOW to purchase.
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== BUY CLICK ==========
    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        logger.info(f"🛒 Buy clicked: {prod_id}")
        
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        if not product:
            await query.edit_message_text("❌ Product not found!", reply_markup=main_menu())
            return
        
        cat = categories_col.find_one({"_id": product["category_id"]})
        cat_price = cat.get('price', 0) if cat else 0
        
        if product.get('stock', 0) <= 0:
            await query.edit_message_text("❌ *Out of stock!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
            return
        
        if user["wallet"] >= cat_price:
            keyboard = [
                [InlineKeyboardButton("✅ YES, CONFIRM", callback_data=f"confirm_{prod_id}")],
                [InlineKeyboardButton("🔙 Cancel", callback_data="products")]
            ]
            await query.edit_message_text(f"""
⚠️ *CONFIRM PURCHASE*

📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{cat_price}
💳 Your Balance: ₹{user['wallet']}
💎 Balance after: ₹{user['wallet'] - cat_price}

Are you sure?
""", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            need = cat_price - user["wallet"]
            await query.edit_message_text(f"❌ *Insufficient Balance!*\n\nNeed ₹{need} more\n\nPlease recharge your wallet.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("products")))
    
    # ========== CONFIRM BUY ==========
    elif data.startswith("confirm_"):
        prod_id = data.split("_")[1]
        logger.info(f"✅ Confirm buy: {prod_id}")
        
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        if not product:
            await query.edit_message_text("❌ Error!", reply_markup=main_menu())
            return
        
        user = get_user(user_id)
        cat = categories_col.find_one({"_id": product["category_id"]})
        cat_price = cat.get('price', 0) if cat else 0
        stock_list = product.get('stock_list', [])
        
        if len(stock_list) <= 0:
            await query.edit_message_text("❌ *Out of stock!*", parse_mode="Markdown", reply_markup=main_menu())
            return
        
        if user["wallet"] >= cat_price:
            # Take first item from stock
            bought_item = stock_list[0]
            new_list = stock_list[1:]
            
            # Update database
            products_col.update_one(
                {"_id": product["_id"]}, 
                {"$set": {"stock_list": new_list, "stock": len(new_list)}}
            )
            update_wallet(user_id, -cat_price)
            
            await query.edit_message_text(f"""
✅ *PURCHASE SUCCESSFUL!*

━━━━━━━━━━━━━━━━━━━━━
📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{cat_price}
💳 Remaining: ₹{user['wallet'] - cat_price}
━━━━━━━━━━━━━━━━━━━━━

🎉 *Here is your purchase:*

{bought_item}

Thank you for shopping! 🙏
""", parse_mode="Markdown", reply_markup=main_menu())
            
            # Notify admin
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"🛒 *Purchase*\nUser: {user_id}\nCategory: {cat['name'] if cat else 'Product'}\nAmount: ₹{cat_price}\nStock left: {len(new_list)}")
        else:
            await query.edit_message_text("❌ *Insufficient balance!*", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== ADMIN PANEL ==========
    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized")
            return
        keyboard = [
            [InlineKeyboardButton("📁 Add Category", callback_data="admin_add_cat")],
            [InlineKeyboardButton("🗑️ Remove Category", callback_data="admin_remove_cat")],
            [InlineKeyboardButton("📝 Add Stock", callback_data="admin_add_stock")],
            [InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price")],
            [InlineKeyboardButton("📋 View Stock", callback_data="admin_view_stock")],
            [InlineKeyboardButton("⏳ Pending", callback_data="admin_pending")],
            [InlineKeyboardButton("📈 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 Main", callback_data="main_menu")]
        ]
        await query.edit_message_text("🔧 *Admin Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== ADD CATEGORY ==========
    elif data == "admin_add_cat":
        if user_id not in ADMIN_IDS:
            return
        await query.edit_message_text("📁 *Send category name:*\n\nExample: `Netflix Account`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_name"
    
    # ========== REMOVE CATEGORY ==========
    elif data == "admin_remove_cat":
        if user_id not in ADMIN_IDS:
            return
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ No categories to remove!")
            return
        
        keyboard = []
        for cat in cats:
            cat_price = cat.get('price', 0)
            product = products_col.find_one({"category_id": cat["_id"]})
            stock_count = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"🗑️ {cat['name']} (₹{cat_price}) - Stock: {stock_count}", callback_data=f"remove_cat_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        
        await query.edit_message_text("🗑️ *Select category to remove*\n\n⚠️ Warning: All stock will be deleted!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("remove_cat_"):
        cat_id = data.split("_")[2]
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        if cat:
            # Delete all products in this category
            products_col.delete_many({"category_id": ObjectId(cat_id)})
            # Delete category
            categories_col.delete_one({"_id": ObjectId(cat_id)})
            await query.edit_message_text(f"✅ *Removed:* {cat['name']}\n\nCategory and all its stock deleted.", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Category not found!")
    
    # ========== ADD STOCK ==========
    elif data == "admin_add_stock":
        if user_id not in ADMIN_IDS:
            return
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ No categories. Add category first.")
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            stock = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"📊 {cat['name']} - Stock: {stock}", callback_data=f"stock_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("Select category to add stock:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("stock_"):
        cat_id = data.split("_")[1]
        context.user_data["stock_cat_id"] = cat_id
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        # Create product if not exists
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        if not product:
            products_col.insert_one({"category_id": ObjectId(cat_id), "stock": 0, "stock_list": []})
        
        await query.edit_message_text(f"""
📊 *Add stock to: {cat['name']}*

Send email/password line by line:

Example:
`email: test1@gmail.com | pass: 12345`
`email: test2@gmail.com | pass: 67890`

Type `/admin` when done.
""", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_stock"
    
    # ========== EDIT PRICE ==========
    elif data == "admin_edit_price":
        if user_id not in ADMIN_IDS:
            return
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("No categories")
            return
        keyboard = [[InlineKeyboardButton(f"💰 {c['name']} - ₹{c.get('price',0)}", callback_data=f"price_{c['_id']}")] for c in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("Select category to edit price:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("price_"):
        cat_id = data.split("_")[1]
        context.user_data["price_cat_id"] = cat_id
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        current_price = cat.get('price', 0)
        await query.edit_message_text(f"💰 *Current price: ₹{current_price}*\n\nSend new price:\nExample: `299`", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_price"
    
    # ========== VIEW STOCK ==========
    elif data == "admin_view_stock":
        if user_id not in ADMIN_IDS:
            return
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("No categories")
            return
        
        keyboard = []
        for cat in cats:
            product = products_col.find_one({"category_id": cat["_id"]})
            stock = product.get('stock', 0) if product else 0
            keyboard.append([InlineKeyboardButton(f"📋 {cat['name']} - {stock} items", callback_data=f"view_{cat['_id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("Select category to view stock:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("view_"):
        cat_id = data.split("_")[1]
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        if product and product.get('stock_list'):
            items = product['stock_list']
            text = f"📋 *{cat['name']}* - Total: {len(items)}\n\n"
            for i, item in enumerate(items[:15]):
                text += f"{i+1}. {item}\n"
            if len(items) > 15:
                text += f"\n... and {len(items)-15} more"
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(back_button("admin_view_stock")))
        else:
            await query.edit_message_text(f"📋 *{cat['name']}* - No stock available", parse_mode="Markdown")
    
    # ========== PENDING ==========
    elif data == "admin_pending":
        if user_id not in ADMIN_IDS:
            return
        pending = list(recharge_reqs_col.find({"status": "pending"}))
        if not pending:
            await query.edit_message_text("✅ No pending requests")
            return
        for req in pending:
            kb = [[InlineKeyboardButton("✅ Approve", callback_data=f"app_{req['_id']}"), InlineKeyboardButton("❌ Reject", callback_data=f"rej_{req['_id']}")]]
            try:
                await query.message.reply_photo(photo=req["screenshot_file_id"], caption=f"👤 User: {req['user_id']}\n💰 Amount: ₹{req['amount']}", reply_markup=InlineKeyboardMarkup(kb))
            except:
                await query.message.reply_text(f"User: {req['user_id']}\nAmount: ₹{req['amount']}", reply_markup=InlineKeyboardMarkup(kb))
    
    elif data.startswith("app_"):
        req_id = data.split("_")[1]
        req = recharge_reqs_col.find_one({"_id": ObjectId(req_id)})
        if req:
            update_wallet(req["user_id"], req["amount"])
            users_col.update_one({"user_id": req["user_id"]}, {"$inc": {"total_recharge": req["amount"], "today_recharge": req["amount"]}})
            recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "approved"}})
            await query.edit_message_text(f"✅ Approved! ₹{req['amount']} added")
            await context.bot.send_message(req["user_id"], f"✅ *Recharge Approved!*\n\n💰 ₹{req['amount']} added to your wallet.", parse_mode="Markdown")
    
    elif data.startswith("rej_"):
        req_id = data.split("_")[1]
        recharge_reqs_col.update_one({"_id": ObjectId(req_id)}, {"$set": {"status": "rejected"}})
        await query.edit_message_text("❌ Rejected")
    
    # ========== STATS ==========
    elif data == "admin_stats":
        if user_id not in ADMIN_IDS:
            return
        total_users = users_col.count_documents({})
        total_wallet = sum([u.get("wallet", 0) for u in users_col.find({})])
        total_cats = categories_col.count_documents({})
        total_stock = 0
        for p in products_col.find({}):
            total_stock += p.get('stock', 0)
        
        stats = f"""
📊 *BOT STATISTICS*

━━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
💰 Total Wallet: ₹{total_wallet}
📁 Total Categories: {total_cats}
📦 Total Stock: {total_stock} items
━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats, parse_mode="Markdown")

# ---------- MESSAGE HANDLERS ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
            kb = [[InlineKeyboardButton("✅ Paid", callback_data="paid_screenshot")], [InlineKeyboardButton("🔙 Back", callback_data="upi_payment")]]
            await update.message.reply_photo(photo=UPI_QR_IMAGE_URL, caption=f"UPI: `{UPI_ID}`\nAmount: ₹{amount}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("❌ Please send a valid number")
        return
    
    # ========== ADD CATEGORY - NAME ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_name":
        context.user_data["cat_name"] = text
        await update.message.reply_text("💰 *Enter category price:*\n\nExample: `100`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_price"
        return
    
    # ========== ADD CATEGORY - PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_price":
        try:
            price = int(text)
            name = context.user_data.get("cat_name")
            
            existing = categories_col.find_one({"name": name})
            if existing:
                await update.message.reply_text(f"❌ Category '{name}' already exists!")
            else:
                categories_col.insert_one({
                    "name": name, 
                    "price": price, 
                    "created_at": datetime.now()
                })
                await update.message.reply_text(f"✅ *Category Added!*\n\n📁 {name}\n💰 ₹{price}\n\nNow use 'Add Stock' to add items.", parse_mode="Markdown")
            
            context.user_data.pop("admin_action")
            context.user_data.pop("cat_name")
        except:
            await update.message.reply_text("❌ Invalid price! Send number only.")
        return
    
    # ========== ADD STOCK ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_stock":
        lines = text.split('\n')
        cat_id = context.user_data.get("stock_cat_id")
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        
        if not product:
            await update.message.reply_text("❌ Error: Product not found")
            return
        
        current = product.get('stock_list', [])
        added = 0
        
        for line in lines:
            line = line.strip()
            if line:
                current.append(line)
                added += 1
        
        products_col.update_one({"_id": product["_id"]}, {"$set": {"stock_list": current, "stock": len(current)}})
        
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        await update.message.reply_text(f"✅ *Stock Added!*\n\n📁 {cat['name']}\n➕ Added: {added} items\n📊 Total: {len(current)} items\n\nYou can continue sending more items.", parse_mode="Markdown")
        # Keep action active for more stock
    
    # ========== EDIT PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "edit_price":
        try:
            new_price = int(text)
            cat_id = context.user_data.get("price_cat_id")
            cat = categories_col.find_one({"_id": ObjectId(cat_id)})
            categories_col.update_one({"_id": ObjectId(cat_id)}, {"$set": {"price": new_price}})
            await update.message.reply_text(f"✅ *Price Updated!*\n\n📁 {cat['name']}\n💰 Old: ₹{cat.get('price',0)}\n💰 New: ₹{new_price}", parse_mode="Markdown")
            context.user_data.pop("admin_action")
            context.user_data.pop("price_cat_id")
        except:
            await update.message.reply_text("❌ Invalid price!")
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
                await context.bot.send_message(admin_id, f"💰 *New Recharge Request*\n\n👤 User: {user_id}\n💵 Amount: ₹{amount}", parse_mode="Markdown")
        except:
            await update.message.reply_text("❌ Invalid amount!")

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
        [InlineKeyboardButton("💰 Edit Price", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📋 View Stock", callback_data="admin_view_stock")],
        [InlineKeyboardButton("⏳ Pending", callback_data="admin_pending")],
        [InlineKeyboardButton("📈 Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 Main", callback_data="main_menu")]
    ]
    await update.message.reply_text("🔧 *Admin Control Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- MAIN ----------
def main():
    # Fix old database entries first
    fix_old_categories()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Bot is running...")
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print("💡 Commands:")
    print("   /start - User menu")
    print("   /admin - Admin panel")
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
