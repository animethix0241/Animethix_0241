import os
import json
import time
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# =========================================================
# 1️⃣ TINY WEB SERVER FOR RENDER PORT BINDING
# =========================================================
web = Flask('')

@web.route('/')
def home():
    return "Mini App Engine: Active"

def run_web():
    # Render automatically passes the port number inside os.environ
    port = int(os.environ.get("PORT", 8080))
    web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# =========================================================
# 2️⃣ DATABASE SETUP
# =========================================================
if not os.path.exists("stream_sessions.json"):
    with open("stream_sessions.json", "w") as f:
        json.dump({}, f)

def save_session_sync(session_id, data):
    try:
        with open("stream_sessions.json", "r") as f:
            database = json.load(f)
    except Exception:
        database = {}
        
    database[session_id] = data
    with open("stream_sessions.json", "w") as f:
        json.dump(database, f, indent=4)

# =========================================================
# 3️⃣ BOT CONFIGURATION & HANDLER
# =========================================================
API_ID = 36724272
API_HASH = "13f7e2f4412dcfe2724171ca079df81d"
BOT_TOKEN = "8628679769:AAFG86eT9Ie_i2keK1_fpbUBjp4S6rvw_0k"
HF_MINI_APP_URL = "https://atx0241-atx-player.static.hf.space"

app = Client(
    "mini_app_tester",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    if len(message.command) > 1:
        raw_data = message.command[1]
        user_id = message.chat.id
        
        session_ref = f"sess_{int(time.time())}_{user_id}"
        
        session_data = {
            "title": f"Batch Session: {raw_data}",
            "video": "https://your-direct-stream-source-url.com/file",  
            "next": "",
            "prev": ""
        }
        save_session_sync(session_ref, session_data)

        inline_menu = [
            [
                InlineKeyboardButton(
                    "🎬 WATCH ONLINE (MINI APP)", 
                    web_app=WebAppInfo(url=f"{HF_MINI_APP_URL}?session={session_ref}")
                )
            ]
        ]
        
        await message.reply(
            f"🎬 **YOUR ANIME TRACK IS READY**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"**Requested Parameters:** {raw_data}\n\n"
            f"Click the button below to test if it opens smoothly inside the Telegram Webview/Mini App engine!",
            reply_markup=InlineKeyboardMarkup(inline_menu)
        )
    else:
        await message.reply(
            "👋 **Welcome!**\n\n"
            "Please use a valid link from your website to test the Mini App stream tracking functionality."
        )

# =========================================================
# 4️⃣ SYSTEM ENTRY POINT
# =========================================================
if __name__ == "__main__":
    # Start the web server first so Render detects port binding instantly
    print("🛰️ Starting web server for Render port check...")
    keep_alive()
    
    # Start the bot
    print("🚀 Mini App Tester Bot is starting...")
    app.run()
