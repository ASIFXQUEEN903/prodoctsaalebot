import os
import logging
from datetime import datetime
from bson import ObjectId
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
import requests
from urllib.parse import urlparse

# ---------- CONFIG ----------
TOKEN = "8862940536:AAF-mUV1F979xcueVNkNt22211Ir7gToMkc"
MONGO_URI = "mongodb+srv://userbot:userbot@cluster0.iweqz.mongodb.net/test?retryWrites=true&w=majority"

# UPI Configuration
UPI_ID = "your_upi_id@okhdfcbank"
UPI_QR_IMAGE_URL = "https://your-domain.com/qr-code.jpg"  # Apna QR code image link yahan daalein
UPI_NAME = "Your Business Name"
UPI_PAYEE_ID = "PAYEE123456"  # Paise bhejne ka ID

BOT_START_TIME = datetime.now()

# ---------- DATABASE ----------
client = MongoClient(MONGO_URI)
db = client["TelegramSaleBot"]
users_col = db["users"]
products_col = db["products"]
categories_col = db["categories"]
recharge_reqs_col = db["recharge_requests"]

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
    return f"{num:,}"

def is_valid_image_url(url):
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('content-type', '')
        return response.status_code == 200 and content_type.startswith('image/')
    except:
        return False

# ---------- STYLISH KEYBOARDS ----------
def main_menu():
    keyboard = [
        [InlineKeyboardButton("👛 𝗪𝗔𝗟𝗟𝗘𝗧", callback_data="wallet")],
        [InlineKeyboardButton("🛍️ 𝗣𝗥𝗢𝗗𝗨𝗖𝗧𝗦", callback_data="products")],
        [InlineKeyboardButton("💳 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘", callback_data="recharge")],
        [InlineKeyboardButton("❓ 𝗦𝗨𝗣𝗣𝗢𝗥𝗧", callback_data="support")],
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button(callback_data):
    return [[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data=callback_data)]]

# ---------- BOT HANDLERS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
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
    
    logger.info(f"Callback: {data}")
    
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
        keyboard = [
            [InlineKeyboardButton("₹10", callback_data="amount_10"), InlineKeyboardButton("₹50", callback_data="amount_50")],
            [InlineKeyboardButton("₹100", callback_data="amount_100"), InlineKeyboardButton("₹200", callback_data="amount_200")],
            [InlineKeyboardButton("₹500", callback_data="amount_500"), InlineKeyboardButton("₹1000", callback_data="amount_1000")],
            [InlineKeyboardButton("🎯 𝗖𝗨𝗦𝗧𝗢𝗠 𝗔𝗠𝗢𝗨𝗡𝗧", callback_data="custom_amount")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="main_menu")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "custom_amount":
        await query.edit_message_text("💰 *Enter your custom amount:*\n\nMinimum: ₹10\n\nSend a number like: `250`", parse_mode="Markdown")
        context.user_data["awaiting_custom_amount"] = True
    
    elif data.startswith("amount_"):
        amount = int(data.split("_")[1])
        context.user_data["recharge_amount"] = amount
        
        # Show QR code, UPI ID, Payee ID, Amount info
        text = f"""
╔══════════════════════════╗
║      💳 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗗𝗘𝗧𝗔𝗜𝗟𝗦      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
🆔 *Payee ID:* `{UPI_PAYEE_ID}`
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Payment Steps:*
1️⃣ Scan QR code below
2️⃣ Pay ₹{amount} to the UPI ID
3️⃣ Note down the Transaction ID/UTR
4️⃣ Send UTR number or screenshot

━━━━━━━━━━━━━━━━━━━━━━━━━━
📸 *Scan QR code to pay*
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ *After payment, click below to send proof*
"""
        
        keyboard = [
            [InlineKeyboardButton("📸 𝗦𝗘𝗡𝗗 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗣𝗥𝗢𝗢𝗙", callback_data="send_payment_proof")],
            [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="recharge")]
        ]
        
        await query.message.delete()
        await query.message.reply_photo(
            photo=UPI_QR_IMAGE_URL,
            caption=text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data == "send_payment_proof":
        amount = context.user_data.get("recharge_amount", 0)
        text = f"""
╔══════════════════════════╗
║      📸 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗣𝗥𝗢𝗢𝗙      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📝 *Please send one of the following:*

1️⃣ *UTR Number* (12-digit transaction ID)
   Example: `123456789012`

2️⃣ *Payment Screenshot* (photo)

━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ *Your request will be processed after verification*
"""
        await query.edit_message_text(text, parse_mode="Markdown")
        context.user_data["awaiting_payment_proof"] = True
    
    # ========== PRODUCTS ==========
    elif data == "products":
        cats = list(categories_col.find({}))
        
        if not cats:
            text = """
╔══════════════════════════╗
║      📦 𝗡𝗢 𝗣𝗥𝗢𝗗𝗨𝗖𝗧𝗦 𝗔𝗩𝗔𝗜𝗟𝗔𝗕𝗟𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
😔 *No products found!*

Please check back later.
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
            text = f"""
╔══════════════════════════╗
║      ❌ 𝗢𝗨𝗧 𝗢𝗙 𝗦𝗧𝗢𝗖𝗞      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
📦 *{cat['name']}*
💰 *Price:* ₹{cat_price}
📊 *Status:* ❌ OUT OF STOCK
━━━━━━━━━━━━━━━━━━━━━━━━━━

😔 *Currently unavailable.*
"""
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]]))
            return
        
        stock = product.get('stock', 0)
        
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
            await query.edit_message_text("❌ Out of stock!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="products")]]))
            return
        
        if user["wallet"] >= cat_price:
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

⚠️ *Are you sure?*
"""
            keyboard = [
                [InlineKeyboardButton("✅ 𝗬𝗘𝗦, 𝗖𝗢𝗡𝗙𝗜𝗥𝗠", callback_data=f"confirm_{prod_id}")],
                [InlineKeyboardButton("🔙 𝗡𝗢, 𝗖𝗔𝗡𝗖𝗘𝗟", callback_data="products")]
            ]
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            need = cat_price - user["wallet"]
            text = f"""
╔══════════════════════════╗
║      ❌ 𝗜𝗡𝗦𝗨𝗙𝗙𝗜𝗖𝗜𝗘𝗡𝗧 𝗕𝗔𝗟𝗔𝗡𝗖𝗘      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💳 *Balance:* ₹{format_number(user['wallet'])}
💰 *Price:* ₹{cat_price}
🔴 *Need:* ₹{need}
━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 *Please recharge your wallet*
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
            await query.edit_message_text("❌ Out of stock!", parse_mode="Markdown", reply_markup=main_menu())
            return
        
        if user["wallet"] >= cat_price:
            bought_item = stock_list[0]
            new_list = stock_list[1:]
            
            products_col.update_one(
                {"_id": product["_id"]}, 
                {"$set": {"stock_list": new_list, "stock": len(new_list)}}
            )
            update_wallet(user_id, -cat_price)
            
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
"""
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_menu())
            
            for admin_id in ADMIN_IDS:
                await context.bot.send_message(admin_id, f"""
🛒 *NEW PURCHASE*
━━━━━━━━━━━━━━━━━━
👤 User: {user_id}
📦 Category: {cat['name'] if cat else 'Product'}
💰 Amount: ₹{cat_price}
📊 Stock left: {len(new_list)}
""", parse_mode="Markdown")
        else:
            await query.edit_message_text("❌ Insufficient balance!", parse_mode="Markdown", reply_markup=main_menu())
    
    # ========== ADMIN PANEL ==========
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
        await query.edit_message_text("🔧 *ADMIN CONTROL PANEL*\n\nSelect an option:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== PENDING REQUESTS ==========
    elif data == "admin_pending":
        if user_id not in ADMIN_IDS:
            await query.answer("Unauthorized!", show_alert=True)
            return
        
        pending = list(recharge_reqs_col.find({"status": "pending"}))
        
        if not pending:
            await query.edit_message_text("✅ *No pending requests*", parse_mode="Markdown")
            return
        
        try:
            await query.delete_response()
        except:
            pass
        
        for req in pending:
            amount = req.get('amount', 0)
            user_id_req = req.get('user_id')
            transaction_id = req.get('transaction_id', 'Not provided')
            screenshot = req.get('screenshot_file_id', None)
            proof_type = req.get('proof_type', 'unknown')
            req_time = req.get('timestamp', datetime.now())
            
            buttons = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘", callback_data=f"approve_rech_{req['_id']}"),
                    InlineKeyboardButton("❌ 𝗥𝗘𝗝𝗘𝗖𝗧", callback_data=f"reject_rech_{req['_id']}")
                ]
            ])
            
            message = f"""
╔══════════════════════════╗
║      💰 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗥𝗘𝗤𝗨𝗘𝗦𝗧      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *User ID:* `{user_id_req}`
💵 *Amount:* ₹{amount}
🆔 *Transaction ID:* `{transaction_id}`
📝 *Proof Type:* {proof_type}
📅 *Time:* {req_time.strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
            
            try:
                if screenshot and (str(screenshot).startswith('http://') or str(screenshot).startswith('https://')):
                    await query.message.reply_photo(photo=screenshot, caption=message, parse_mode="Markdown", reply_markup=buttons)
                elif screenshot:
                    try:
                        await query.message.reply_photo(photo=screenshot, caption=message, parse_mode="Markdown", reply_markup=buttons)
                    except:
                        await query.message.reply_text(message + f"\n📎 *Proof ID:* `{screenshot}`", parse_mode="Markdown", reply_markup=buttons)
                else:
                    await query.message.reply_text(message, parse_mode="Markdown", reply_markup=buttons)
            except Exception as e:
                logger.error(f"Error: {e}")
                await query.message.reply_text(message, parse_mode="Markdown", reply_markup=buttons)
    
    # ========== APPROVE RECHARGE ==========
    elif data.startswith("approve_rech_"):
        if user_id not in ADMIN_IDS:
            await query.answer("Unauthorized!", show_alert=True)
            return
        
        req_id_str = data.split("_")[2]
        req_id = ObjectId(req_id_str)
        req = recharge_reqs_col.find_one({"_id": req_id})
        
        if req and req["status"] == "pending":
            amount = req.get('amount', 0)
            target_user_id = req.get('user_id')
            
            update_wallet(target_user_id, amount)
            users_col.update_one(
                {"user_id": target_user_id}, 
                {"$inc": {"total_recharge": amount, "today_recharge": amount},
                 "$set": {"last_recharge_date": datetime.now().strftime("%Y-%m-%d")}}
            )
            recharge_reqs_col.update_one({"_id": req_id}, {"$set": {"status": "approved", "processed_at": datetime.now()}})
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(ADMIN_ID, f"""
╔══════════════════════════╗
║      ✅ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗 𝗦𝗨𝗖𝗖𝗘𝗦𝗦𝗙𝗨𝗟𝗟𝗬      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Amount:* ₹{amount}
👤 *User:* `{target_user_id}`
💳 *Added to wallet*
━━━━━━━━━━━━━━━━━━━━━━━━━━
""", parse_mode="Markdown")
            
            try:
                new_balance = get_user(target_user_id)['wallet']
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton("🛒 𝗕𝗨𝗬 𝗡𝗢𝗪", callback_data="products"))
                
                await context.bot.send_message(target_user_id, f"""
╔══════════════════════════╗
║      ✅ 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗔𝗣𝗣𝗥𝗢𝗩𝗘𝗗      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Amount:* ₹{amount}
💳 *New Balance:* ₹{format_number(new_balance)}
━━━━━━━━━━━━━━━━━━━━━━━━━━

🎉 *Thank you for recharging!*

👇 *Click below to buy accounts*
""", parse_mode="Markdown", reply_markup=kb)
            except Exception as e:
                logger.error(f"Could not notify user: {e}")
        else:
            await query.answer("Request already processed!", show_alert=True)
            try:
                await query.message.delete()
            except:
                pass
    
    # ========== REJECT RECHARGE ==========
    elif data.startswith("reject_rech_"):
        if user_id not in ADMIN_IDS:
            await query.answer("Unauthorized!", show_alert=True)
            return
        
        req_id_str = data.split("_")[2]
        req_id = ObjectId(req_id_str)
        req = recharge_reqs_col.find_one({"_id": req_id})
        
        if req and req["status"] == "pending":
            amount = req.get('amount', 0)
            target_user_id = req.get('user_id')
            
            recharge_reqs_col.update_one({"_id": req_id}, {"$set": {"status": "rejected", "processed_at": datetime.now()}})
            
            try:
                await query.message.delete()
            except:
                pass
            
            await context.bot.send_message(ADMIN_ID, f"""
╔══════════════════════════╗
║      ❌ 𝗥𝗘𝗝𝗘𝗖𝗧𝗘𝗗      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Amount:* ₹{amount}
👤 *User:* `{target_user_id}`
━━━━━━━━━━━━━━━━━━━━━━━━━━
""", parse_mode="Markdown")
            
            try:
                await context.bot.send_message(target_user_id, f"""
╔══════════════════════════╗
║      ❌ 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗥𝗘𝗝𝗘𝗖𝗧𝗘𝗗      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

😔 *Your recharge request was rejected.*

📞 *Please contact support* for more information.
""", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Could not notify user: {e}")
        else:
            await query.answer("Request already processed!", show_alert=True)
            try:
                await query.message.delete()
            except:
                pass
    
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
            await query.edit_message_text("❌ No categories")
            return
        keyboard = [[InlineKeyboardButton(f"🗑️ {c['name']} (₹{c.get('price',0)})", callback_data=f"remove_cat_{c['_id']}")] for c in cats]
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        await query.edit_message_text("Select category to remove:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("remove_cat_"):
        cat_id = data.split("_")[2]
        cat = categories_col.find_one({"_id": ObjectId(cat_id)})
        if cat:
            products_col.delete_many({"category_id": ObjectId(cat_id)})
            categories_col.delete_one({"_id": ObjectId(cat_id)})
            await query.edit_message_text(f"✅ Removed: {cat['name']}")
    
    # ========== ADD STOCK ==========
    elif data == "admin_add_stock":
        if user_id not in ADMIN_IDS:
            return
        cats = list(categories_col.find({}))
        if not cats:
            await query.edit_message_text("❌ No categories")
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
        product = products_col.find_one({"category_id": ObjectId(cat_id)})
        if not product:
            products_col.insert_one({"category_id": ObjectId(cat_id), "stock": 0, "stock_list": []})
        await query.edit_message_text(f"📊 *Add stock to: {cat['name']}*\n\nSend email/password line by line:\n\nExample:\n`email: test1@gmail.com | pass: 123`\n\nType /admin when done", parse_mode="Markdown")
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
        await query.edit_message_text(f"💰 *Current price:* ₹{cat.get('price',0)}\n\nSend new price:", parse_mode="Markdown")
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
        await query.edit_message_text("Select category:", reply_markup=InlineKeyboardMarkup(keyboard))
    
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
            await query.edit_message_text(f"📋 *{cat['name']}* - No stock", parse_mode="Markdown")
    
    # ========== STATISTICS ==========
    elif data == "admin_stats":
        if user_id not in ADMIN_IDS:
            return
        total_users = users_col.count_documents({})
        total_wallet = sum([u.get("wallet", 0) for u in users_col.find({})])
        total_cats = categories_col.count_documents({})
        total_stock = sum([p.get('stock', 0) for p in products_col.find({})])
        pending = recharge_reqs_col.count_documents({"status": "pending"})
        
        stats = f"""
╔══════════════════════════╗
║      📊 𝗕𝗢𝗧 𝗦𝗧𝗔𝗧𝗜𝗦𝗧𝗜𝗖𝗦      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 *Users:* {total_users}
💰 *Wallet:* ₹{format_number(total_wallet)}
📁 *Categories:* {total_cats}
📦 *Stock:* {total_stock} items
⏳ *Pending:* {pending}
━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        await query.edit_message_text(stats, parse_mode="Markdown")

# ---------- MESSAGE HANDLERS ----------
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if context.user_data.get("awaiting_payment_proof"):
        context.user_data["awaiting_payment_proof"] = False
        photo = update.message.photo[-1]
        file_id = photo.file_id
        amount = context.user_data.get("recharge_amount", 0)
        
        req_id = ObjectId()
        recharge_reqs_col.insert_one({
            "_id": req_id,
            "user_id": user_id,
            "amount": amount,
            "screenshot_file_id": file_id,
            "transaction_id": "Screenshot uploaded",
            "proof_type": "screenshot",
            "status": "pending",
            "timestamp": datetime.now()
        })
        
        await update.message.reply_text("✅ *Recharge request submitted!*\n\nAdmin will verify and approve shortly.", parse_mode="Markdown")
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘", callback_data=f"approve_rech_{req_id}"),
             InlineKeyboardButton("❌ 𝗥𝗘𝗝𝗘𝗖𝗧", callback_data=f"reject_rech_{req_id}")]
        ])
        
        for admin_id in ADMIN_IDS:
            await context.bot.send_photo(admin_id, photo=file_id, caption=f"""
╔══════════════════════════╗
║      💰 𝗡𝗘𝗪 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗥𝗘𝗤𝗨𝗘𝗦𝗧      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *User:* `{user_id}`
💵 *Amount:* ₹{amount}
📸 *Screenshot attached*
━━━━━━━━━━━━━━━━━━━━━━━━━━
""", parse_mode="Markdown", reply_markup=buttons)
        
        context.user_data.pop("recharge_amount", None)
        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # ========== WAITING FOR PAYMENT PROOF (UTR) ==========
    if context.user_data.get("awaiting_payment_proof"):
        context.user_data["awaiting_payment_proof"] = False
        utr_number = text
        amount = context.user_data.get("recharge_amount", 0)
        
        req_id = ObjectId()
        recharge_reqs_col.insert_one({
            "_id": req_id,
            "user_id": user_id,
            "amount": amount,
            "screenshot_file_id": None,
            "transaction_id": utr_number,
            "proof_type": "utr",
            "status": "pending",
            "timestamp": datetime.now()
        })
        
        await update.message.reply_text("✅ *Recharge request submitted!*\n\nAdmin will verify using your UTR number.\n\nPlease wait for approval.", parse_mode="Markdown")
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ 𝗔𝗣𝗣𝗥𝗢𝗩𝗘", callback_data=f"approve_rech_{req_id}"),
             InlineKeyboardButton("❌ 𝗥𝗘𝗝𝗘𝗖𝗧", callback_data=f"reject_rech_{req_id}")]
        ])
        
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(admin_id, f"""
╔══════════════════════════╗
║      💰 𝗡𝗘𝗪 𝗥𝗘𝗖𝗛𝗔𝗥𝗚𝗘 𝗥𝗘𝗤𝗨𝗘𝗦𝗧      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 *User:* `{user_id}`
💵 *Amount:* ₹{amount}
🆔 *UTR Number:* `{utr_number}`
━━━━━━━━━━━━━━━━━━━━━━━━━━
""", parse_mode="Markdown", reply_markup=buttons)
        
        context.user_data.pop("recharge_amount", None)
        return
    
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
║      💳 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗗𝗘𝗧𝗔𝗜𝗟𝗦      ║
╚══════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━
🏦 *UPI ID:* `{UPI_ID}`
🆔 *Payee ID:* `{UPI_PAYEE_ID}`
💰 *Amount:* ₹{amount}
━━━━━━━━━━━━━━━━━━━━━━━━━━

📱 *Payment Steps:*
1️⃣ Scan QR code below
2️⃣ Pay ₹{amount} to the UPI ID
3️⃣ Note down the Transaction ID/UTR
4️⃣ Send UTR number or screenshot

━━━━━━━━━━━━━━━━━━━━━━━━━━
📸 *Scan QR code to pay*
━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ *After payment, click below to send proof*
"""
            
            keyboard = [
                [InlineKeyboardButton("📸 𝗦𝗘𝗡𝗗 𝗣𝗔𝗬𝗠𝗘𝗡𝗧 𝗣𝗥𝗢𝗢𝗙", callback_data="send_payment_proof")],
                [InlineKeyboardButton("🔙 𝗕𝗔𝗖𝗞", callback_data="recharge")]
            ]
            
            await update.message.reply_photo(
                photo=UPI_QR_IMAGE_URL,
                caption=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except:
            await update.message.reply_text("❌ Please send a valid number")
        return
    
    # ========== ADD CATEGORY (ADMIN) ==========
    if user_id in ADMIN_IDS and context.user_data.get("admin_action") == "add_cat_name":
        context.user_data["cat_name"] = text
        await update.message.reply_text("💰 *Enter category price:*\n\nExample: `100`", parse_mode="Markdown")
        context.user_data["admin_action"] = "add_cat_price"
        return
    
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
        await update.message.reply_text(f"✅ *Stock Added!*\n\n📁 {cat['name']}\n➕ Added: {added} items\n📊 Total: {len(current)} items\n\nYou can continue adding more stock.", parse_mode="Markdown")
        return
    
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

# ---------- ADMIN COMMAND ----------
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
    await update.message.reply_text("🔧 *ADMIN CONTROL PANEL*\n\nWelcome Admin!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# ---------- MAIN ----------
def main():
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
    print("-" * 50)
    print("💡 Commands:")
    print("   /start  - User Menu")
    print("   /admin  - Admin Panel")
    print("=" * 50)
    
    app.run_polling()

if __name__ == "__main__":
    reset_daily_recharge()
    main()
