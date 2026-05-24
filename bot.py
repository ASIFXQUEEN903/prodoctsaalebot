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
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
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
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']} - ₹{cat['price']}", callback_data=f"cat_{cat['_id']}")] for cat in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("🛍️ *Categories*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        products_list = list(products_col.find({"category_id": ObjectId(cat_id)}))
        if not products_list:
            await query.edit_message_text("📭 *No products in this category*", parse_mode="Markdown", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(f"📦 {p['name']} - ₹{p['price']}", callback_data=f"buy_{p['_id']}")] for p in products_list]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="products")])
        await query.edit_message_text("🛒 *Products*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        if not product:
            await query.edit_message_text("❌ Product not found.", reply_markup=main_menu())
            return
        
        # Check if user has enough balance
        cat = categories_col.find_one({"_id": product["category_id"]})
        category_price = cat["price"] if cat else 0
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Buy", callback_data=f"confirm_buy_{prod_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="products")]
        ]
        
        text = f"""
📦 *{product['name']}*

💰 Product Price: ₹{product['price']}
📁 Category: {cat['name'] if cat else 'N/A'}
💳 Your Balance: ₹{user['wallet']}

📝 *Details:*
{product['details']}

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
                products_col.update_one({"_id": product["_id"]}, {"$inc": {"stock": -1}})
                update_wallet(user_id, -product["price"])
                await query.edit_message_text(f"✅ *Purchase Successful!*\n\n📦 {product['name']}\n💰 Amount: ₹{product['price']}\n\n{product['details']}", parse_mode="Markdown", reply_markup=main_menu())
            else:
                await query.edit_message_text("❌ *Out of stock*", parse_mode="Markdown", reply_markup=main_menu())
        else:
            need = product["price"] - user["wallet"]
            await query.edit_message_text(f"❌ *Insufficient balance!*\n\n💳 Your Balance: ₹{user['wallet']}\n💰 Need: ₹{need} more\n\nPlease recharge your wallet.", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== ADMIN PANEL ==========
    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
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
        await query.edit_message_text("🔧 *Admin Panel*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== ADD CATEGORY (Step by step) ==========
    elif data == "admin_add_cat":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        await query.edit_message_text("📁 *Step 1/2: Enter Category Name*\n\nExample: `Electronics`, `Accounts`, `Gaming`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_name"
    
    # ========== ADD PRODUCT ==========
    elif data == "admin_add_prod":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        
        # First show categories to select from
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ *No categories available!*\n\nPlease add a category first using 'Add Category' button.", parse_mode="Markdown")
            return
        
        keyboard = [[InlineKeyboardButton(f"📁 {cat['name']}", callback_data=f"select_cat_{cat['_id']}")] for cat in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("📦 *Select Category for Product*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("select_cat_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        cat_id = data.split("_")[2]
        context.user_data["product_category_id"] = cat_id
        await query.edit_message_text("📦 *Step 1/4: Enter Product Name*\n\nExample: `iPhone 14 Pro`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_prod_name"
    
    # ========== EDIT PRICE ==========
    elif data == "admin_edit_price":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        prods = list(products_col.find({}))
        if not prods:
            await query.edit_message_text("No products available.", reply_markup=main_menu())
            return
        keyboard = [[InlineKeyboardButton(f"{p['name']} - ₹{p['price']}", callback_data=f"editprice_{p['_id']}")] for p in prods]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("💰 *Select product to edit price:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("editprice_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        prod_id = data.split("_")[1]
        context.user_data["edit_prod_id"] = prod_id
        await query.edit_message_text("💰 *Send new price (number only):*\n\nExample: `499`", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_price"
    
    # ========== EDIT STOCK ==========
    elif data == "admin_edit_stock":
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        prods = list(products_col.find({}))
        if not prods:
            await query.edit_message_text("No products available.")
            return
        keyboard = [[InlineKeyboardButton(f"{p['name']} - Stock: {p['stock']}", callback_data=f"editstock_{p['_id']}")] for p in prods]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("📊 *Select product to edit stock:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("editstock_"):
        if user_id not in ADMIN_IDS:
            await query.edit_message_text("🔒 Unauthorized.")
            return
        prod_id = data.split("_")[1]
        context.user_data["edit_prod_id"] = prod_id
        await query.edit_message_text("📊 *Send new stock quantity (number only):*\n\nExample: `50`", parse_mode="Markdown")
        context.user_data["admin_action"] = "edit_stock"
    
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
        total_products = products_col.count_documents({})
        total_categories = categories_col.count_documents({})
        
        stats = f"""
📊 *BOT STATISTICS*

━━━━━━━━━━━━━━━━━━━━━
👥 Total Users: {total_users}
📁 Total Categories: {total_categories}
📦 Total Products: {total_products}
💳 Total Wallet Balance: ₹{total_wallet}
💰 Total Recharge: ₹{total_recharge}
⏳ Pending Requests: {pending_recharge}
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
            await query.edit_message_text(f"✅ Approved! ₹{req['amount']} added to user's wallet.")
            try:
                await context.bot.send_message(req["user_id"], f"✅ *Recharge Approved!*\n\n💰 ₹{req['amount']} has been added to your wallet.", parse_mode="Markdown")
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
        await update.message.reply_text("💰 *Step 2/2: Enter Category Price*\n\nExample: `100` (This is the price to access this category)", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_price"
        return
    
    # ========== ADD CATEGORY - STEP 2: PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_price":
        try:
            price = int(text)
            cat_name = context.user_data["new_category_name"]
            
            # Check if category already exists
            existing = categories_col.find_one({"name": cat_name})
            if existing:
                await update.message.reply_text(f"❌ Category '{cat_name}' already exists!")
                context.user_data.pop("admin_action")
                context.user_data.pop("new_category_name")
                return
            
            # Insert category with price
            categories_col.insert_one({
                "name": cat_name,
                "price": price,
                "created_at": datetime.now()
            })
            await update.message.reply_text(f"✅ *Category Added Successfully!*\n\n📁 Name: {cat_name}\n💰 Price: ₹{price}\n\nYou can now add products to this category.", parse_mode="Markdown")
            
            # Clean up
            context.user_data.pop("admin_action")
            context.user_data.pop("new_category_name")
        except ValueError:
            await update.message.reply_text("❌ Invalid price! Please send a number only.\nExample: `100`")
        return
    
    # ========== ADD PRODUCT - STEP 1: NAME ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_prod_name":
        context.user_data["new_product_name"] = text
        await update.message.reply_text("💰 *Step 2/4: Enter Product Price*\n\nExample: `499`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_prod_price"
        return
    
    # ========== ADD PRODUCT - STEP 2: PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_prod_price":
        try:
            price = int(text)
            context.user_data["new_product_price"] = price
            await update.message.reply_text("📊 *Step 3/4: Enter Stock Quantity*\n\nExample: `50`", parse_mode="Markdown")
            context.user_data["admin_action"] = "add_prod_stock"
        except ValueError:
            await update.message.reply_text("❌ Invalid price! Send a number.")
        return
    
    # ========== ADD PRODUCT - STEP 3: STOCK ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_prod_stock":
        try:
            stock = int(text)
            context.user_data["new_product_stock"] = stock
            await update.message.reply_text("📝 *Step 4/4: Enter Product Details*\n\nExample: `Brand new, 1 year warranty, Original box included`", parse_mode="Markdown")
            context.user_data["admin_action"] = "add_prod_details"
        except ValueError:
            await update.message.reply_text("❌ Invalid stock! Send a number.")
        return
    
    # ========== ADD PRODUCT - STEP 4: DETAILS ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_prod_details":
        details = text
        name = context.user_data.get("new_product_name")
        price = context.user_data.get("new_product_price")
        stock = context.user_data.get("new_product_stock")
        cat_id = context.user_data.get("product_category_id")
        
        # Insert product
        products_col.insert_one({
            "name": name,
            "price": price,
            "stock": stock,
            "details": details,
            "category_id": ObjectId(cat_id),
            "created_at": datetime.now()
        })
        
        # Get category name
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        await update.message.reply_text(f"""
✅ *Product Added Successfully!*

━━━━━━━━━━━━━━━━━━━━━
📦 Name: {name}
📁 Category: {cat['name'] if cat else 'N/A'}
💰 Price: ₹{price}
📊 Stock: {stock}
📝 Details: {details}
━━━━━━━━━━━━━━━━━━━━━

Product is now available for users to buy!
""", parse_mode="Markdown")
        
        # Clean up
        context.user_data.pop("admin_action")
        context.user_data.pop("new_product_name")
        context.user_data.pop("new_product_price")
        context.user_data.pop("new_product_stock")
        context.user_data.pop("new_product_details", None)
        context.user_data.pop("product_category_id", None)
        return
    
    # ========== EDIT PRICE ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "edit_price":
        try:
            new_price = int(text)
            prod_id = context.user_data["edit_prod_id"]
            product = products_col.find_one({"_id": ObjectId(prod_id)})
            products_col.update_one({"_id": ObjectId(prod_id)}, {"$set": {"price": new_price}})
            await update.message.reply_text(f"✅ Price updated!\n\n📦 {product['name']}\n💰 Old: ₹{product['price']}\n💰 New: ₹{new_price}", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Invalid price! Send a number.")
        context.user_data.pop("admin_action")
        context.user_data.pop("edit_prod_id", None)
        return
    
    # ========== EDIT STOCK ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "edit_stock":
        try:
            new_stock = int(text)
            prod_id = context.user_data["edit_prod_id"]
            product = products_col.find_one({"_id": ObjectId(prod_id)})
            products_col.update_one({"_id": ObjectId(prod_id)}, {"$set": {"stock": new_stock}})
            await update.message.reply_text(f"✅ Stock updated!\n\n📦 {product['name']}\n📊 Old: {product['stock']}\n📊 New: {new_stock}", parse_mode="Markdown")
        except ValueError:
            await update.message.reply_text("❌ Invalid stock! Send a number.")
        context.user_data.pop("admin_action")
        context.user_data.pop("edit_prod_id", None)
        return
    
    # ========== USER RECHARGE AMOUNT (after screenshot) ==========
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
        except ValueError:
            await update.message.reply_text("❌ Invalid amount! Send a number.")

# ---------- ADMIN COMMAND ----------
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
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

# ---------- MAIN ----------
def main():
    app = Application.builder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    
    # Callback handler - ONE handler for ALL buttons
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🤖 Bot is running...")
    print(f"Admin ID: {ADMIN_IDS[0]}")
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
