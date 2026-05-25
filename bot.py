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

# Store Bot Start Time
BOT_START_TIME = datetime.now()

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
            "last_recharge_date": None,
            "join_date": datetime.now()
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

def format_number(num):
    """Format number with commas"""
    return f"{num:,}"

def get_time_ago(timestamp):
    """Get time ago string"""
    if not timestamp:
        return "Unknown"
    diff = datetime.now() - timestamp
    if diff.days > 0:
        return f"{diff.days} days ago"
    elif diff.seconds > 3600:
        return f"{diff.seconds // 3600} hours ago"
    elif diff.seconds > 60:
        return f"{diff.seconds // 60} minutes ago"
    else:
        return "Just now"

# ---------- STYLISH KEYBOARDS ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("👛 𝗪𝗔𝗟𝗟𝗘𝗧", callback_data="wallet")],
        [InlineKeyboardButton("🛍️ 𝗣𝗥𝗢𝗗𝗨𝗖𝗧𝗦", callback_data="products")],
        [InlineKeyboardButton("💳 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘", callback_data="recharge")],
        [InlineKeyboardButton("❓ 𝗦𝗨𝗣𝗣𝗢𝗥𝗧", callback_data="support")],
        [InlineKeyboardButton("📢 𝗖𝗛𝗔𝗡𝗡𝗘𝗟", url="https://t.me/your_channel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button(callback_data):
    return [[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data=callback_data)]]

def two_row_buttons(buttons):
    """Convert list to 2 rows"""
    result = []
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        result.append(row)
    return result

# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    # Stylish welcome message
    msg = f"""
╔══════════════════════════╗
║      ✨ 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗦𝗛𝗢𝗣 ✨     ║
╚══════════════════════════╝

🌟 *Hello {update.effective_user.first_name}!*

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏪 *Your One-Stop Digital Store*
💎 *Trusted by 1000+ Customers*
⚡ *Instant Delivery*
━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 *Your Balance:* ₹{format_number(user['wallet'])}

👇 *Tap below buttons to explore*
"""
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu())

# ---------- CALLBACK HANDLER ----------
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    user = get_user(user_id)
    
    logger.info(f"📩 Callback: {data}")
    
    # ========== MAIN MENU ==========
    if data == "main_menu":
        msg = f"""
╔══════════════════════════╗
║        ✨ 𝗠𝗔𝗜𝗡 𝗠𝗘𝗡𝗨 ✨        ║
╚══════════════════════════╝

💰 *Balance:* ₹{format_number(user['wallet'])}
📅 *Member since:* {user.get('join_date', datetime.now()).strftime('%d %b %Y')}

👇 *Select an option below*
"""
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== WALLET ==========
    elif data == "wallet":
        # Show popup alert
        await query.answer("💰 Opening your wallet...", show_alert=False)
        
        text = f"""
╔══════════════════════════╗
║        💰 𝗪𝗔𝗟𝗟𝗘𝗧 𝗗𝗘𝗧𝗔𝗜𝗟𝗦        ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 *Current Balance:* ₹{format_number(user['wallet'])}
📈 *Total Recharged:* ₹{format_number(user['total_recharge'])}
📊 *Today's Recharge:* ₹{format_number(user['today_recharge'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Need to add funds?*
Tap the Recharge button below!
"""
        keyboard = [
            [InlineKeyboardButton("💳 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗡𝗢𝗪", callback_data="recharge")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== SUPPORT ==========
    elif data == "support":
        await query.answer("📞 Opening support...", show_alert=False)
        
        text = f"""
╔══════════════════════════╗
║        ❓ 𝗦𝗨𝗣𝗣𝗢𝗥𝗧 𝗖𝗘𝗡𝗧𝗘𝗥        ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📞 *Contact Admin:* @your_admin
⏰ *Response Time:* 24/7
━━━━━━━━━━━━━━━━━━━━━━━━━━

💬 *Common Issues:*
• Recharge not credited?
• Product delivery issue?
• Wrong product received?

*Click below to contact admin*
"""
        keyboard = [
            [InlineKeyboardButton("📞 𝗖𝗢𝗡𝗧𝗔𝗖𝗧 𝗔𝗗𝗠𝗜𝗡", url="https://t.me/your_admin")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== RECHARGE ==========
    elif data == "recharge":
        await query.answer("💳 Loading recharge options...", show_alert=False)
        
        text = f"""
╔══════════════════════════╗
║        💳 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗪𝗔𝗟𝗟𝗘𝗧        ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Current Balance:* ₹{format_number(user['wallet'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━

💎 *Select Amount to Recharge:*

Tap any amount below to proceed.
"""
        # 2 row buttons for amounts
        keyboard = [
            [InlineKeyboardButton("₹10", callback_data="amount_10"), InlineKeyboardButton("₹50", callback_data="amount_50")],
            [InlineKeyboardButton("₹100", callback_data="amount_100"), InlineKeyboardButton("₹200", callback_data="amount_200")],
            [InlineKeyboardButton("₹500", callback_data="amount_500"), InlineKeyboardButton("₹1000", callback_data="amount_1000")],
            [InlineKeyboardButton("🎯 𝗖𝗨𝗦𝗧𝗢𝗠 𝗔𝗠𝗢𝗨𝗡𝗧", callback_data="custom_amount")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "upi_payment":
        await query.answer("💳 Opening payment gateway...", show_alert=False)
        
        text = f"""
╔══════════════════════════╗
║      💳 𝗨𝗣𝗜 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗚𝗔𝗧𝗘𝗪𝗔𝗬      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
👤 *Pay to:* {UPI_NAME}
💰 *Amount:* ₹{context.user_data.get('recharge_amount', '?')}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Payment Steps:*
1️⃣ Open GPay / PhonePe / Paytm
2️⃣ Scan QR code or enter UPI ID
3️⃣ Pay the exact amount
4️⃣ Click "I HAVE PAID" button

⚠️ *Send screenshot after payment!*
"""
        keyboard = [
            [InlineKeyboardButton("✅ 𝗜 𝗛𝗔𝗩𝗘 𝗣𝗔𝗜𝗗", callback_data="paid_screenshot")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="recharge")]
        ]
        await query.message.delete()
        await query.message.reply_photo(photo=UPI_QR_IMAGE_URL, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("amount_"):
        amount = int(data.split("_")[1])
        context.user_data["recharge_amount"] = amount
        await query.answer(f"✅ ₹{amount} selected! Proceeding to payment...", show_alert=True)
        
        # Directly go to UPI payment
        text = f"""
╔══════════════════════════╗
║      💳 𝗨𝗣𝗜 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗚𝗔𝗧𝗘𝗪𝗔𝗬      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
👤 *Pay to:* {UPI_NAME}
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Payment Steps:*
1️⃣ Open GPay / PhonePe / Paytm
2️⃣ Scan QR code or enter UPI ID
3️⃣ Pay ₹{amount}
4️⃣ Click "I HAVE PAID" button

⚠️ *Send screenshot after payment!*
"""
        keyboard = [
            [InlineKeyboardButton("✅ 𝗜 𝗛𝗔𝗩𝗘 𝗣𝗔𝗜𝗗", callback_data="paid_screenshot")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="recharge")]
        ]
        await query.message.delete()
        await query.message.reply_photo(photo=UPI_QR_IMAGE_URL, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "custom_amount":
        await query.answer("💰 Enter custom amount", show_alert=False)
        await query.edit_message_text("💰 *Enter your custom amount:*\n\nMinimum: ₹10\n\nSend a number like: `250`", parse_mode="Markdown")
        context.user_data["awaiting_custom_amount"] = True
    
    elif data == "paid_screenshot":
        await query.answer("📸 Please send payment screenshot", show_alert=True)
        await query.edit_message_text("📸 *Please send payment screenshot*\n\nMake sure the screenshot clearly shows:\n• Transaction ID\n• Amount\n• Date & Time", parse_mode="Markdown")
        context.user_data["awaiting_screenshot"] = True
    
    # ========== PRODUCTS ==========
    elif data == "products":
        await query.answer("🛍️ Loading products...", show_alert=False)
        
        cats = list(categories_col.find({}))
        
        if not cats:
            text = """
╔══════════════════════════╗
║      📦 𝗡𝗢 𝗣𝗥𝗢𝗗𝗨𝗖𝗧𝗦 𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
😔 *No products found!*

Please check back later for 
exciting new products.

━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
            return
        
        keyboard = []
        for cat in cats:
            cat_price = cat.get('price', 0)
            product = products_col.find_one({"category_id": cat["_id"]})
            stock = product.get('stock', 0) if product else 0
            emoji = "✅" if stock > 0 else "❌"
            button_text = f"📁 {cat['name']}  |  ₹{cat_price}  {emoji}  [{stock}]"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"cat_{cat['_id']}")])
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞 𝗧𝗢 𝗠𝗘𝗡𝗨", callback_data="main_menu")])
        
        text = f"""
╔══════════════════════════╗
║      🛍️ 𝗣𝗥𝗢𝗗𝗨𝗖𝗧𝗦 𝗖𝗔𝗧𝗔𝗟𝗢𝗚𝗨𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Your Balance:* ₹{format_number(user['wallet'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📦 *Available Categories:*

Tap any category to view details
"""
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== CATEGORY CLICK ==========
    elif data.startswith("cat_"):
        cat_id = data.split("_")[1]
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        
        if not cat:
            await query.edit_message_text("❌ Category not found!", reply_markup=main_menu())
            return
        
        cat_price = cat.get('price', 0)
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        
        if not product or product.get('stock', 0) <= 0:
            await query.answer("❌ Out of stock!", show_alert=True)
            text = f"""
╔══════════════════════════╗
║      ❌ 𝗢𝗨𝗧 𝗢𝗙 𝗦𝗧𝗢𝗖𝗞      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *{cat['name']}*

💰 *Price:* ₹{cat_price}
📊 *Status:* ❌ OUT OF STOCK
━━━━━━━━━━━━━━━━━━━━━━━━━━

😔 *This product is currently unavailable.*

Please check back later!
"""
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]]))
            return
        
        stock = product.get('stock', 0)
        await query.answer(f"✅ In stock! {stock} units available", show_alert=False)
        
        text = f"""
╔══════════════════════════╗
║      📦 𝗣𝗥𝗢𝗗𝗨𝗖𝗧 𝗗𝗘𝗧𝗔𝗜𝗟𝗦      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 *Category:* {cat['name']}
💰 *Price:* ₹{cat_price}
📊 *Stock:* {stock} units left
━━━━━━━━━━━━━━━━━━━━━━━━━━

💳 *Your Balance:* ₹{format_number(user['wallet'])}

━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ *Instant Delivery After Purchase*
🔒 *Secure & Trusted*
⚡ *24/7 Support*
━━━━━━━━━━━━━━━━━━━━━━━━━━

👇 *Tap below to purchase*
"""
        keyboard = [
            [InlineKeyboardButton("🛒 𝗕𝗨𝗬 𝗡𝗢𝗪", callback_data=f"buy_{product['_id']}")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== BUY CLICK ==========
    elif data.startswith("buy_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        
        if not product:
            await query.edit_message_text("❌ Product not found!", reply_markup=main_menu())
            return
        
        cat = categories_col.find_one({"_id": product["category_id"]})
        cat_price = cat.get('price', 0) if cat else 0
        
        if product.get('stock', 0) <= 0:
            await query.answer("❌ Out of stock!", show_alert=True)
            await query.edit_message_text("❌ *Out of stock!*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]]))
            return
        
        if user["wallet"] >= cat_price:
            await query.answer("⚠️ Please confirm purchase", show_alert=True)
            text = f"""
╔══════════════════════════╗
║      ⚠️ 𝗖𝗢𝗡𝗙𝗜𝗥𝗠 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *Category:* {cat['name'] if cat else 'Product'}
💰 *Amount:* ₹{cat_price}
💳 *Your Balance:* ₹{format_number(user['wallet'])}
💎 *Balance After:* ₹{format_number(user['wallet'] - cat_price)}
━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ *Are you sure you want to buy?*

This action cannot be undone!
"""
            keyboard = [
                [InlineKeyboardButton("✅ 𝗬𝗘𝗦, 𝗖𝗢𝗡𝗙𝗜𝗥𝗠", callback_data=f"confirm_{prod_id}")],
                [InlineKeyboardButton("🔙 𝗡𝗢, 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="products")]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            need = cat_price - user["wallet"]
            await query.answer(f"❌ Need ₹{need} more!", show_alert=True)
            text = f"""
╔══════════════════════════╗
║      ❌ 𝗜𝗡𝗦𝗨𝗙𝗙𝗜𝗖𝗜𝗘𝗡𝗧 𝗕𝗔𝗟𝗔𝗡𝗖𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 *Your Balance:* ₹{format_number(user['wallet'])}
💰 *Product Price:* ₹{cat_price}
🔴 *Need More:* ₹{need}
━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Please recharge your wallet*

Tap the button below to add funds!
"""
            keyboard = [
                [InlineKeyboardButton("💳 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗡𝗢𝗪", callback_data="recharge")],
                [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== CONFIRM BUY ==========
    elif data.startswith("confirm_"):
        prod_id = data.split("_")[1]
        product = products_col.find_one({"_id": ObjectId(prod_id)})
        
        if not product:
            await query.edit_message_text("❌ Error!", reply_markup=main_menu())
            return
        
        user = get_user(user_id)
        cat = categories_col.find_one({"_id": product["category_id"]})
        cat_price = cat.get('price', 0) if cat else 0
        stock_list = product.get('stock_list', [])
        
        if len(stock_list) <= 0:
            await query.answer("❌ Out of stock!", show_alert=True)
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
            
            await query.answer("✅ Purchase successful!", show_alert=True)
            
            text = f"""
╔══════════════════════════╗
║      ✅ 𝗣𝗨𝗥𝗖𝗛𝗔𝗦𝗘 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *Category:* {cat['name'] if cat else 'Product'}
💰 *Amount:* ₹{cat_price}
💳 *Remaining:* ₹{format_number(user['wallet'] - cat_price)}
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 *Here is your purchase:*

`{bought_item}`

━━━━━━━━━━━━━━━━━━━━━━━━━━
💫 *Thank you for shopping!*

⭐ *Rate us:* @your_channel
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
            
            # Notify admin
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"""
🛒 *NEW PURCHASE*
━━━━━━━━━━━━━━━━━━
👤 User: {user_id}
📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{cat_price}
📊 Stock left: {len(new_list)}
━━━━━━━━━━━━━━━━━━
""", parse_mode="Markdown")
        else:
            await query.answer("❌ Insufficient balance!", show_alert=True)
            await query.edit_message_text("❌ *Insufficient balance!*", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== ADMIN PANEL (Keep existing) ==========
    elif data == "admin_panel":
        if user_id not in ADMIN_IDS:
            await query.answer("🔒 Unauthorized!", show_alert=True)
            return
        keyboard = [
            [InlineKeyboardButton("📁 𝗔𝗗𝗗 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬", callback_data="admin_add_cat")],
            [InlineKeyboardButton("🗑️ 𝗥𝗘𝗠𝗢𝗩𝗘 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬", callback_data="admin_remove_cat")],
            [InlineKeyboardButton("📝 𝗔𝗗𝗗 𝗦𝗧𝗢𝗖𝗞", callback_data="admin_add_stock")],
            [InlineKeyboardButton("💰 𝗘𝗗𝗜𝗧 𝗣𝗥𝗜𝗖𝗘", callback_data="admin_edit_price")],
            [InlineKeyboardButton("📋 𝗩𝗜𝗘𝗪 𝗦𝗧𝗢𝗖𝗞", callback_data="admin_view_stock")],
            [InlineKeyboardButton("⏳ 𝗣𝗘𝗡𝗗𝗜𝗡𝗚", callback_data="admin_pending")],
            [InlineKeyboardButton("📈 𝗦𝗧𝗔𝗧𝗦", callback_data="admin_stats")],
            [InlineKeyboardButton("🔙 𝗠𝗔𝗜𝗡 𝗠𝗘𝗡𝗨", callback_data="main_menu")]
        ]
        await query.edit_message_text("🔧 *ADMIN CONTROL PANEL*\n\nSelect an option below:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ... (rest of admin handlers remain same as previous code)
    else:
        # Handle other admin actions (add category, add stock, etc.)
        # Keep from previous working code
        pass

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
            
            text = f"""
╔══════════════════════════╗
║      💳 𝗨𝗣𝗜 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗚𝗔𝗧𝗘𝗪𝗔𝗬      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
👤 *Pay to:* {UPI_NAME}
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Payment Steps:*
1️⃣ Open GPay / PhonePe / Paytm
2️⃣ Scan QR code or enter UPI ID
3️⃣ Pay ₹{amount}
4️⃣ Click "I HAVE PAID" button

⚠️ *Send screenshot after payment!*
"""
            kb = [[InlineKeyboardButton("✅ 𝗜 𝗛𝗔𝗩𝗘 𝗣𝗔𝗜𝗗", callback_data="paid_screenshot")], [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="recharge")]]
            await update.message.reply_photo(photo=UPI_QR_IMAGE_URL, caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))
        except:
            await update.message.reply_text("❌ Please send a valid number")
        return
    
    # ========== ADD CATEGORY - NAME (Admin) ==========
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

# ========== ADMIN COMMAND ==========
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("🔒 *Unauthorized Access*", parse_mode="Markdown")
        return
    
    keyboard = [
        [InlineKeyboardButton("📁 𝗔𝗗𝗗 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬", callback_data="admin_add_cat")],
        [InlineKeyboardButton("🗑️ 𝗥𝗘𝗠𝗢𝗩𝗘 𝗖𝗔𝗧𝗘𝗚𝗢𝗥𝗬", callback_data="admin_remove_cat")],
        [InlineKeyboardButton("📝 𝗔𝗗𝗗 𝗦𝗧𝗢𝗖𝗞", callback_data="admin_add_stock")],
        [InlineKeyboardButton("💰 𝗘𝗗𝗜𝗧 𝗣𝗥𝗜𝗖𝗘", callback_data="admin_edit_price")],
        [InlineKeyboardButton("📋 𝗩𝗜𝗘𝗪 𝗦𝗧𝗢𝗖𝗞", callback_data="admin_view_stock")],
        [InlineKeyboardButton("⏳ 𝗣𝗘𝗡𝗗𝗜𝗡𝗚", callback_data="admin_pending")],
        [InlineKeyboardButton("📈 𝗦𝗧𝗔𝗧𝗦", callback_data="admin_stats")],
        [InlineKeyboardButton("🔙 𝗠𝗔𝗜𝗡 𝗠𝗘𝗡𝗨", callback_data="main_menu")]
    ]
    await update.message.reply_text("🔧 *ADMIN CONTROL PANEL*\n\nWelcome Admin! Select an option below:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ========== MAIN ==========
def main():
    # Fix old database entries first
    fix_old_categories()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("=" * 50)
    print("🤖 𝗦𝗔𝗟𝗘 𝗕𝗢𝗧 𝗜𝗦 𝗥𝗨𝗡𝗡𝗜𝗡𝗚")
    print("=" * 50)
    print(f"👑 Admin ID: {ADMIN_IDS[0]}")
    print(f"📅 Started at: {BOT_START_TIME.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    print("💡 Commands:")
    print("   /start  - User Menu")
    print("   /admin  - Admin Panel")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
