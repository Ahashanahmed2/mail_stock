import os
import sys
import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from pymongo import MongoClient
import re
from datetime import datetime

# লগিং সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
MONGODB_URI = os.environ.get('MONGODB_URI')

if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN environment variable সেট করা হয়নি!")
    sys.exit(1)

if not MONGODB_URI:
    logger.error("❌ MONGODB_URI environment variable সেট করা হয়নি!")
    sys.exit(1)

# MongoDB কানেকশন
try:
    logger.info("MongoDB এ কানেক্ট হচ্ছে...")
    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    logger.info("✅ MongoDB কানেক্ট সফল!")
    
    db = client["email_bot_db"]
    collection = db["emails"]
    
except Exception as e:
    logger.error(f"❌ MongoDB কানেক্ট ত্রুটি: {e}")
    sys.exit(1)

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

# কমান্ড হ্যান্ডলার
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 হ্যালো {user.first_name}!\n"
        "আমি আপনার ইমেল ম্যানেজমেন্ট বট।\n\n"
        "📌 **উপলব্ধ কমান্ড:**\n"
        "/postmail [ইমেল] - নতুন ইমেল যোগ করুন\n"
        "/view [ইমেল] - ইমেল খুঁজুন\n"
        "/list - সব ইমেল দেখুন\n"
        "/update [পুরাতন] [নতুন] - ইমেল আপডেট\n"
        "/delete [ইমেল] - ইমেল মুছুন"
    )

async def postmail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: /postmail email@example.com")
            return
        
        email = ' '.join(context.args).strip().lower()
        
        if not is_valid_email(email):
            await update.message.reply_text("❌ ইমেল ঠিকানা সঠিক নয়")
            return
        
        if collection.find_one({"email": email}):
            await update.message.reply_text(f"⚠️ {email} আগে থেকেই আছে")
            return
        
        data = {
            "email": email,
            "created_by": update.effective_user.username or update.effective_user.first_name,
            "user_id": update.effective_user.id,
            "created_at": datetime.now()
        }
        
        collection.insert_one(data)
        await update.message.reply_text(f"✅ {email} সংরক্ষিত হয়েছে")
        
    except Exception as e:
        logger.error(f"Error in postmail: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে")

async def view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: /view email@example.com")
            return
        
        email = ' '.join(context.args).strip().lower()
        
        if collection.find_one({"email": email}):
            await update.message.reply_text(f"✅ {email} ডাটাবেসে আছে")
        else:
            await update.message.reply_text(f"❌ {email} ডাটাবেসে নেই")
            
    except Exception as e:
        logger.error(f"Error in view: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে")

async def list_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        emails = list(collection.find({}, {"email": 1, "_id": 0}).sort("created_at", -1))
        
        if not emails:
            await update.message.reply_text("📭 ডাটাবেসে কোনো ইমেল নেই")
            return
        
        count = len(emails)
        email_list = "\n".join([f"{i+1}. {e['email']}" for i, e in enumerate(emails)])
        await update.message.reply_text(f"📋 মোট {count}টি ইমেল:\n\n{email_list}")
        
    except Exception as e:
        logger.error(f"Error in list: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে")

async def update_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) != 2:
            await update.message.reply_text("❌ ব্যবহার: /update old@email.com new@email.com")
            return
        
        old_email = context.args[0].strip().lower()
        new_email = context.args[1].strip().lower()
        
        if not is_valid_email(new_email):
            await update.message.reply_text("❌ নতুন ইমেল সঠিক নয়")
            return
        
        if not collection.find_one({"email": old_email}):
            await update.message.reply_text(f"❌ {old_email} ডাটাবেসে নেই")
            return
        
        if collection.find_one({"email": new_email}):
            await update.message.reply_text(f"⚠️ {new_email} আগে থেকেই আছে")
            return
        
        collection.update_one(
            {"email": old_email},
            {"$set": {"email": new_email, "updated_at": datetime.now()}}
        )
        await update.message.reply_text(f"✅ {old_email} → {new_email} আপডেট হয়েছে")
        
    except Exception as e:
        logger.error(f"Error in update: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে")

async def delete_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not context.args:
            await update.message.reply_text("❌ ব্যবহার: /delete email@example.com")
            return
        
        email = ' '.join(context.args).strip().lower()
        
        if not collection.find_one({"email": email}):
            await update.message.reply_text(f"❌ {email} ডাটাবেসে নেই")
            return
        
        collection.delete_one({"email": email})
        await update.message.reply_text(f"✅ {email} ডিলিট হয়েছে")
        
    except Exception as e:
        logger.error(f"Error in delete: {e}")
        await update.message.reply_text("❌ একটি ত্রুটি হয়েছে")

async def run_bot():
    """বট চালু করার জন্য async ফাংশন"""
    try:
        logger.info("🤖 বট চালু হচ্ছে...")
        
        # Application তৈরি
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        
        # হ্যান্ডলার যোগ করুন
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("postmail", postmail))
        app.add_handler(CommandHandler("view", view))
        app.add_handler(CommandHandler("list", list_emails))
        app.add_handler(CommandHandler("update", update_email))
        app.add_handler(CommandHandler("delete", delete_email))
        
        logger.info("✅ বট চালু হয়েছে")
        
        # বট চালান
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        
        # বট চলতে থাকবে
        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"❌ বট চালু ত্রুটি: {e}", exc_info=True)
        raise

def main():
    """মেইন ফাংশন - Event Loop সেটআপ"""
    try:
        # Python 3.14+ এর জন্য Event Loop সেটআপ
        if sys.version_info >= (3, 14):
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        
        # Event Loop তৈরি
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # বট চালান
        loop.run_until_complete(run_bot())
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("🛑 বট বন্ধ হচ্ছে...")
    except Exception as e:
        logger.error(f"❌ মেইন ত্রুটি: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
