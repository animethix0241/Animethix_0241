import os
import json
import time
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

# Ensure the database file exists so it never crashes
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

# CONFIGURATION
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
    # Check if there are parameters after /start (e.g., /start 201-226)
    if len(message.command) > 1:
        raw_data = message.command[1]
        user_id = message.chat.id
        
        # Create a temporary unique key for this stream session
        session_ref = f"sess_{int(time.time())}_{user_id}"
        
        # Save the requested file details so your Mini App can fetch it via API later
        session_data = {
            "title": f"Batch Session: {raw_data}",
            "video": "https://your-direct-stream-source-url.com/file",  # Layout placeholder
            "next": "",
            "prev": ""
        }
        save_session_sync(session_ref, session_data)

        # Build the menu button that opens your HuggingFace Mini App
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
        # Fallback if someone just types plain /start without links
        await message.reply(
            "👋 **Welcome!**\n\n"
            "Please use a valid link from your website to test the Mini App stream tracking functionality."
        )

if __name__ == "__main__":
    print("🚀 Mini App Tester Bot is starting...")
    app.run()
