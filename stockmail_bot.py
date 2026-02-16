import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
import re
import os
from datetime import datetime

# ===== কনফিগারেশন =====
TELEGRAM_TOKEN = "8412297634:AAEwgTioLJVIK_bX-qhIrHaooKrNqYPeHik"
MONGODB_URI = "mongodb+srv://asdFGH:asdFGH@cluster0.mkjaenr.mongodb.net/?appName=Cluster0"

# ===== MongoDB কানেকশন টেস্ট =====
try:
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    # সার্ভারে পিং করে কানেকশন টেস্ট
    client.admin.command('ping')
    print("✅ MongoDB এ সফলভাবে কানেক্ট হয়েছে!")
    
    db = client["email_bot_db"]  # ডাটাবেস
    collection = db["emails"]     # কালেকশন
    print("✅ ডাটাবেস ও কালেকশন প্রস্তুত!")
    
except ConnectionFailure as e:
    print(f"❌ MongoDB কানেক্ট করতে পারেনি: {e}")
    print("চেক করুন:")
    print("1. নেটওয়ার্ক অ্যাক্সেস সঠিক আছে কিনা (0.0.0.0/0)")
    print("2. ইউজারনেম ও পাসওয়ার্ড সঠিক আছে কিনা")
    print("3. আপনার ইন্টারনেট সংযোগ ঠিক আছে কিনা")
    exit(1)
except Exception as e:
    print(f"❌ অজানা ত্রুটি: {e}")
    exit(1)

# ===== লগিং সেটআপ =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ইমেল ভ্যালিডেশন ফাংশন =====
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# ===== কমান্ড হ্যান্ডলার =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = """
👋 স্বাগতম! আমি আপনার ইমেল ম্যানেজমেন্ট বট।

উপলব্ধ কমান্ডসমূহ:
📧 /postmail [ইমেল] - নতুন ইমেল সংরক্ষণ করুন
🔍 /view [ইমেল] - ইমেল আছে কিনা চেক করুন
📋 /list - সব ইমেলের তালিকা দেখুন
🔄 /update [পুরাতন] [নতুন] - ইমেল আপডেট করুন
❌ /delete [ইমেল] - ইমেল ডিলিট করুন

উদাহরণ:
/postmail aaa@mail.com
/view aaa@mail.com
/list
/update aaa@mail.com bbb@mail.com
/delete aaa@mail.com
"""
    await update.message.reply_text(welcome_msg)

async def postmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ দয়া করে একটি ইমেল দিন। যেমন: /postmail aaa@mail.com")
            return
        
        email = ' '.join(context.args).strip()
        
        if not is_valid_email(email):
            await update.message.reply_text("❌ ইমেল ঠিকানা সঠিক নয়।")
            return
        
        existing = collection.find_one({"email": email})
        if existing:
            await update.message.reply_text(f"⚠️ '{email}' ইতিমধ্যেই ডাটাবেসে আছে।")
            return
        
        data = {
            "email": email,
            "created_by": update.effective_user.username or update.effective_user.first_name,
            "user_id": update.effective_user.id,
            "created_at": datetime.now()
        }
        
        collection.insert_one(data)
        await update.message.reply_text(f"✅ '{email}' সফলভাবে সংরক্ষণ করা হয়েছে!")
        
    except Exception as e:
        logger.error(f"Error in postmail: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে। আবার চেষ্টা করুন।")

async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ দয়া করে একটি ইমেল দিন। যেমন: /view aaa@mail.com")
            return
        
        email = ' '.join(context.args).strip()
        
        result = collection.find_one({"email": email})
        
        if result:
            created_at = result.get('created_at', 'Unknown')
            created_by = result.get('created_by', 'Unknown')
            await update.message.reply_text(
                f"✅ '{email}' ডাটাবেসে আছে!\n"
                f"📅 তৈরি: {created_at}\n"
                f"👤 তৈরি করেছেন: {created_by}"
            )
        else:
            await update.message.reply_text(f"❌ '{email}' ডাটাবেসে নেই।")
            
    except Exception as e:
        logger.error(f"Error in view: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে। আবার চেষ্টা করুন।")

async def list_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emails = list(collection.find({}, {"email": 1, "created_at": 1, "_id": 0}))
        
        if not emails:
            await update.message.reply_text("📭 ডাটাবেসে এখনও কোনো ইমেল নেই।")
            return
        
        count = len(emails)
        message = f"📋 মোট {count}টি ইমেল পাওয়া গেছে:\n\n"
        
        for i, item in enumerate(emails, 1):
            email = item.get('email', 'Unknown')
            created_at = item.get('created_at', 'Unknown')
            message += f"{i}. {email}\n"
        
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"Error in list: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে। আবার চেষ্টা করুন।")

async def update_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ সঠিক ফরম্যাট: /update [পুরাতন_ইমেল] [নতুন_ইমেল]")
            return
        
        old_email = context.args[0].strip()
        new_email = context.args[1].strip()
        
        if not is_valid_email(new_email):
            await update.message.reply_text("❌ নতুন ইমেল ঠিকানা সঠিক নয়।")
            return
        
        existing = collection.find_one({"email": old_email})
        if not existing:
            await update.message.reply_text(f"❌ '{old_email}' ডাটাবেসে নেই।")
            return
        
        new_exists = collection.find_one({"email": new_email})
        if new_exists:
            await update.message.reply_text(f"⚠️ '{new_email}' ইতিমধ্যেই ডাটাবেসে আছে।")
            return
        
        collection.update_one(
            {"email": old_email},
            {"$set": {"email": new_email}}
        )
        
        await update.message.reply_text(f"✅ '{old_email}' -> '{new_email}' সফলভাবে আপডেট করা হয়েছে!")
        
    except Exception as e:
        logger.error(f"Error in update: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে। আবার চেষ্টা করুন।")

async def delete_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ দয়া করে একটি ইমেল দিন। যেমন: /delete aaa@mail.com")
            return
        
        email = ' '.join(context.args).strip()
        
        existing = collection.find_one({"email": email})
        if not existing:
            await update.message.reply_text(f"❌ '{email}' ডাটাবেসে নেই।")
            return
        
        collection.delete_one({"email": email})
        await update.message.reply_text(f"✅ '{email}' সফলভাবে ডিলিট করা হয়েছে!")
        
    except Exception as e:
        logger.error(f"Error in delete: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে। আবার চেষ্টা করুন।")

def main():
    # অ্যাপ্লিকেশন তৈরি
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # কমান্ড হ্যান্ডলার যোগ করা
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("postmail", postmail))
    application.add_handler(CommandHandler("view", view))
    application.add_handler(CommandHandler("list", list_emails))
    application.add_handler(CommandHandler("update", update_email))
    application.add_handler(CommandHandler("delete", delete_email))
    
    # বট চালু করা
    print("🤖 বট চালু হচ্ছে...")
    print(f"🤖 বট ইউজারনেম: @stocktokenmail_bot")
    print("📝 লগ দেখতে থাকুন...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
