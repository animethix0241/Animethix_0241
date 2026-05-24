import os
import json
import time
import asyncio
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.errors import FloodWait

# =========================================================
# 1️⃣ TINY WEB SERVER FOR RENDER PORT BINDING
# =========================================================
web = Flask('')

@web.route('/')
def home():
    return "Mini App Engine: Active"

def run_web():
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
# 3️⃣ BOT CONFIGURATION & CORE LOGIC
# =========================================================
API_ID = 36724272
API_HASH = "13f7e2f4412dcfe2724171ca079df81d"
BOT_TOKEN = "8628679769:AAFG86eT9Ie_i2keK1_fpbUBjp4S6rvw_0k"
RAW_CHANNEL_ID = -1003813237940  # Channel where your raw media files are stored
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
        
        status_msg = await message.reply("🛰️ **FETCHING YOUR FILES...**")

        # Parse the range or IDs (e.g., "201-205" or "201")
        target_ids = []
        parts = [p.strip() for p in raw_data.replace("_", "-").split("-") if p.strip()]
        
        if len(parts) == 2:
            try:
                start_id = int(parts[0])
                end_id = int(parts[1])
                target_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
            except ValueError:
                pass
        elif len(parts) == 1:
            try:
                target_ids.append(int(parts[0]))
            except ValueError:
                pass

        if not target_ids:
            await status_msg.edit("⚠️ **Invalid session parameters configuration.**")
            return

        # Process and send the files
        total_files = len(target_ids)
        for index, m_id in enumerate(target_ids):
            is_last_file = (index == total_files - 1)
            
            try:
                # Fetch original file from your storage channel
                source_msg = await client.get_messages(RAW_CHANNEL_ID, m_id)
                
                if not source_msg or (not source_msg.document and not source_msg.video):
                    continue  # Skip if file not found in channel

                media = source_msg.document or source_msg.video
                file_name = getattr(media, "file_name", "Animethix_File")
                caption_text = f"📁 **{file_name}**"

                # If it is the last file, attach the Mini App player button directly to it
                if is_last_file:
                    session_ref = f"sess_{int(time.time())}_{user_id}"
                    
                    # Create data reference for ATX Player
                    session_data = {
                        "title": file_name,
                        "video": "https://your-direct-stream-source-url.com/file",  # Video playback path placeholder
                        "next": "",
                        "prev": ""
                    }
                    save_session_sync(session_ref, session_data)

                    # Build markup with the WebApp endpoint passing our tracking token
                    inline_menu = [
                        [
                            InlineKeyboardButton(
                                "🎬 PLAY WITH ATX PLAYER", 
                                web_app=WebAppInfo(url=f"{HF_MINI_APP_URL}?session={session_ref}")
                            )
                        ]
                    ]
                    reply_markup = InlineKeyboardMarkup(inline_menu)
                else:
                    reply_markup = None

                # Copy file directly to user chat
                await client.copy_message(
                    chat_id=user_id,
                    from_chat_id=RAW_CHANNEL_ID,
                    message_id=m_id,
                    caption=caption_text,
                    reply_markup=reply_markup
                )
                
                # Small delay to avoid flooding limits
                await asyncio.sleep(1.0)

            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Error transferring message ID {m_id}: {e}")
                continue

        # Clean up tracking status message when batch transfer terminates
        try:
            await status_msg.delete()
        except Exception:
            pass

    else:
        await message.reply(
            "👋 **Welcome!**\n\n"
            "Please use a valid link from your website to request files and test the ATX Player."
        )

# =========================================================
# 4️⃣ SYSTEM ENTRY POINT
# =========================================================
if __name__ == "__main__":
    print("🛰️ Starting web server for Render port check...")
    keep_alive()
    
    print("🚀 Mini App Tester Bot is starting...")
    app.run()
