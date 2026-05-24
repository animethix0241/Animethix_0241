import asyncio
import os
import json
import time
import aiofiles
from threading import Thread
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.errors import FloodWait, UserNotParticipant

# =========================================================
# 1️⃣ DATABASE INITIALIZATION (Safety Net)
# =========================================================
# This ensures that if JSON files are ever deleted, the bot recreates them 
# instantly instead of crashing.
for file in ["users.json", "sessions.json", "banned.json", "stream_sessions.json"]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump({} if "banned" not in file else [], f)

# =========================================================
# 2️⃣ GLOBAL MEMORY TRACKER
# =========================================================
last_warning = {}
user_sessions = {}
user_strikes = {}
active_slots = 0
MAX_CONCURRENT_USERS = 25
user_queue = asyncio.Queue()
spam_cooldown = {} # To track the 15s Anti-Spam Lock
file_lock = asyncio.Lock()

async def save_json(filename, data):
    async with file_lock:
        try:
            loop = asyncio.get_running_loop()
            content = await loop.run_in_executor(None, lambda: json.dumps(data, indent=4))
            async with aiofiles.open(filename, mode='w') as f:
                await f.write(content)
        except Exception as e: 
            print(f"Save Error: {e}")

def load_json_sync(filename, default_type=dict):
    if not os.path.exists(filename):
        with open(filename, "w") as f: 
            json.dump(default_type(), f)
        return default_type()
    with open(filename, "r") as f: 
        return json.load(f)

async def load_json(filename, default_type=dict):
    async with file_lock:
        if not os.path.exists(filename):
            async with aiofiles.open(filename, "w") as f:
                await f.write(json.dumps(default_type()))
            return default_type()
        try:
            async with aiofiles.open(filename, mode='r') as f:
                content = await f.read()
                return json.loads(content)
        except Exception:
            return default_type()

async def add_user_to_db(user_id, username):
    users = await load_json("users.json", dict)
    users[str(user_id)] = f"@{username}" if username else "Anonymous"
    await save_json("users.json", users)

async def add_batch_to_sessions(user_id, message_ids):
    sessions = await load_json("sessions.json", dict)
    user_key = str(user_id)
    if user_key not in sessions: 
        sessions[user_key] = []
    
    expiry = int(time.time()) + DELETE_TIME 
    sessions[user_key].append({"msgs": message_ids, "expiry": expiry})
    await save_json("sessions.json", sessions)

async def auto_janitor(client):
    print("🧹 [SYSTEM] Janitor Protocol Initialized.")
    while True:
        try:
            await asyncio.sleep(300) 
            sessions = await load_json("sessions.json", dict)
            if not sessions:
                continue
            
            current_time = int(time.time())
            updated_sessions = {}
            any_deleted = False

            for user_id, batches in sessions.items():
                remaining_batches = []
                for batch in batches:
                    if current_time >= batch["expiry"]:
                        try:
                            await client.delete_messages(int(user_id), batch["msgs"])
                            any_deleted = True
                        except Exception as e:
                            print(f"⚠️ [JANITOR] Could not delete for {user_id}: {e}")
                    else:
                        remaining_batches.append(batch)
                
                if remaining_batches:
                    updated_sessions[user_id] = remaining_batches

            if any_deleted or len(sessions) != len(updated_sessions):
                await save_json("sessions.json", updated_sessions)
                print(f"🧹 [JANITOR] Cleanup cycle complete at {time.strftime('%H:%M:%S')}")

        except Exception as global_err:
            print(f"🚨 [CRITICAL] Janitor Loop Error: {global_err}")
            await asyncio.sleep(10)

# =========================================================
# 3️⃣ BULLETPROOF BAN CHECK SYSTEM
# =========================================================
BANNED_USERS = set(load_json_sync("banned.json", list))

def is_user_banned(user_id):
    return user_id in BANNED_USERS

async def update_ban_list(user_id, ban=True):
    global BANNED_USERS
    if ban:
        BANNED_USERS.add(user_id)
    else:
        BANNED_USERS.discard(user_id)
    await save_json("banned.json", list(BANNED_USERS))

# =========================================================
# 4️⃣ KEEP ALIVE WEB SERVER (For 24x7 Hosting)
# =========================================================
web = Flask('')

@web.route('/')
@web.route('/player/sessions/<session_id>', methods=['GET'])
def get_player_session(session_id):
    try:
        data = load_json_sync("stream_sessions.json", dict)
        session_info = data.get(session_id)
        if not session_info:
            return jsonify({"error": "Session Expired or Invalid"}), 404
        return jsonify(session_info), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
def home():
    return "Animethix Engine v3.0: Active & Operational"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    web.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# =========================================================
# 5️⃣ BOT CONFIGURATION
# =========================================================
API_ID = 36724272
API_HASH = "13f7e2f4412dcfe2724171ca079df81d"
BOT_TOKEN = "8628679769:AAFG86eT9Ie_i2keK1_fpbUBjp4S6rvw_0k"
RAW_CHANNEL_ID = -1003813237940
GALLERY_CHANNEL_ID = -1003726533474
DELETE_TIME = 21600  # 6 Hours
AUTH_CHANNEL = -1003597213361  # Animethix Updates
AUTH_GROUP = -1003876800188    # Animethix Chat
FSUB_IMAGE = "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiYzDLVdCALvX1i2ZXqTp0wuwd7ShMN3lW-4b80VYOZoQ2iFrfnK0GN2kJZXeTFyGHdpRfw5B8Jc1QOULSZQN4SipKak6itGZSvuWIx-mP7dY8ZzlLSA8AbQ4Dy_WAtrOmkts4PB_boQ1TEEShdSRKKXL1G6NWtKQ075suDkH6aH6qUVvfcZEVA-oKIsu8/s735/photo_2026-03-11_07-28-16.jpg"
ADMINS = [7784446308] # Your Telegram ID
LOG_CHANNEL_ID = -1003783914118
# 🌐 Paste your HuggingFace Static Space link here
HF_MINI_APP_URL = "https://atx0241-atx-player.static.hf.space"
app = Client(
    "animethix_filebot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# =========================================================
# 📝 THE LOG FUNCTION
# =========================================================
async def send_log(client, user, action, detail="None"):
    try:
        log_text = (
            f"👤 **USER:** {user.first_name} (ID: `{user.id}`)\n"
            f"🔗 **USERNAME:** @{user.username if user.username else 'N/A'}\n"
            f"🛠️ **ACTION:** `{action}`\n"
            f"📦 **DETAILS:** `{detail}`\n"
            f"⏰ **TIME:** {time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await client.send_message(LOG_CHANNEL_ID, log_text)
    except Exception as e:
        print(f"Log Error: {e}")

# =========================================================
# 6️⃣ FSUB & VAPORIZE CORE
# =========================================================
async def check_fsub(client, user_id):
    if user_id in ADMINS:
        return True
    if not AUTH_CHANNEL or not AUTH_GROUP:
        print("⚠️ FSUB ERROR: Channel or Group ID is missing in config!")
        return True 
        
    try:
        await client.get_chat_member(AUTH_CHANNEL, user_id)
        await client.get_chat_member(AUTH_GROUP, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception as e:
        print(f"FSub Error: {e}")
        return False

async def vaporize_protocol(client, chat_id):
    message_ids = user_sessions.get(chat_id, []).copy()
    if not message_ids:
        return

    try:
        try:
            warn = await client.send_message(chat_id, "🚨 **UNAUTHORIZED ACCESS DETECTED**")
            for i in range(5, 0, -1):
                bar = "■" * (5 - i) + "□" * i
                await client.edit_message_text(
                    chat_id, warn.id,
                    f"🚨 **MEMBERSHIP REVOKED**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"User left official channels. Purging data...\n"
                    f"`[{bar}] {i}s`"
                )
                await asyncio.sleep(1)
            message_ids.append(warn.id) 
        except Exception:
            print(f"User {chat_id} blocked bot, skipping animation.")

        await client.delete_messages(chat_id, message_ids)
        
    except Exception as e:
        print(f"Vaporize Error for {chat_id}: {e}")
    finally:
        user_sessions.pop(chat_id, None)
        last_warning.pop(chat_id, None)
        print(f"🧹 Full memory wipe for {chat_id}")

async def clean_chat_history(client, chat_id, message_ids, warning_msg_id):
    await asyncio.sleep(DELETE_TIME)
    try:
        for i in range(10, 0, -1):
            bar = "■" * (10 - i) + "□" * i
            try:
                await client.edit_message_text(
                    chat_id, warning_msg_id,
                    f"🚨 **SECURE WIPE INITIATED**\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"Purging history for privacy...\n"
                    f"<code>[{bar}] {i}s</code>"
                )
            except:
                break 
            await asyncio.sleep(1)

        try:
            await client.edit_message_text(chat_id, warning_msg_id, "💥 **VAPORIZING DATA...**")
        except:
            pass
        await asyncio.sleep(1.2)

        try:
            await client.delete_messages(chat_id, message_ids)
        except:
            pass

    except Exception as e:
        print(f"CLEANUP ERROR for {chat_id}: {e}")
    finally:
        user_sessions.pop(chat_id, None)
        if last_warning.get(chat_id) == warning_msg_id:
            last_warning.pop(chat_id, None)
        print(f"✅ Cleanup Complete for {chat_id}: Memory Cleared.")

# =========================================================
# 📂 SMART FILE SENDER HELPER
# =========================================================
async def send_file_with_caption(client, user_id, message_id, is_gallery=False):
    try:
        source_id = GALLERY_CHANNEL_ID if is_gallery else RAW_CHANNEL_ID
        msg = await client.get_messages(source_id, message_id)
        
        if not msg or (not msg.document and not msg.video):
            return None

        media = msg.document or msg.video
        file_name = getattr(media, "file_name", "Animethix_Encoded_File")
        
        final_caption = (
            f"📁 **{file_name}**\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✨ **Encoded for Quality**\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        return await client.copy_message(
            chat_id=user_id,
            from_chat_id=source_id,
            message_id=message_id,
            caption=final_caption
        )
    except Exception as e:
        print(f"SEND FILE ERROR: {e}")
        return None

# =========================================================
# 📂 SMART FILE PROCESSOR
# =========================================================
async def process_file_request(client, user_id, raw_data, user, message, is_from_queue=False):
    global active_slots
    active_slots += 1
    try:
        if is_from_queue:
            await client.send_message(user_id, "✅ **SORRY FOR THE WAIT!**\nA slot opened up. Starting your files now...")
        
        is_gallery = False
        if raw_data.startswith("gal_"):
            is_gallery = True
            raw_data = raw_data.replace("gal_", "")

        if user_id in last_warning:
            try:
                await client.delete_messages(user_id, last_warning[user_id])
            except:
                pass

        status_msg = await message.reply("🛰️ **FETCHING FROM CLOUD...**")
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        user_sessions[user_id].append(status_msg.id)

        try:
            target_ids = []
            parts = [p.strip() for p in raw_data.replace(" ", "_").replace(",", "_").split("_") if p.strip()]
            
            for p in parts:
                if "-" in p:
                    try:
                        start_id, end_id = map(int, p.split("-"))
                        target_ids.extend(range(min(start_id, end_id), max(start_id, end_id) + 1))
                    except: 
                        continue
                else:
                    try: 
                        target_ids.append(int(p))
                    except: 
                        continue

            target_ids = list(dict.fromkeys(target_ids))

            if len(target_ids) > 100:
                await status_msg.delete()
                return await message.reply(
                    "⚠️ **BATCH LIMIT EXCEEDED**\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "To prevent spam, you can only request \n"
                    "up to **100 files** at a time.\n"
                    "━━━━━━━━━━━━━━━━━━━━"
                )
            
            for m_id in target_ids:
                try:
                    sent = await send_file_with_caption(client, user_id, m_id, is_gallery=is_gallery)
                    if sent:
                        user_sessions[user_id].append(sent.id)
                    await asyncio.sleep(0.8)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: 
                    continue
            try:
                await status_msg.delete()
            except:
                pass

            warning_text = (
                "🛡️ **SECURITY PROTOCOL ACTIVE**\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Files and history delete in **6 Hours**.\n"
                "Forward to **Saved Messages** to keep them!\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )

            warn = await message.reply(
                warning_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "📟 JOIN UPDATES CHANNEL",
                        url="https://t.me/Animethix_Updates"
                    )
                ]])
            )

            last_warning[user_id] = warn.id
            user_sessions[user_id].append(warn.id)
            await add_batch_to_sessions(user_id, user_sessions[user_id].copy())
            user_sessions.pop(user_id, None)

        except Exception as e:
            print(f"ENGINE ERROR: {e}")
            await message.reply(
                "📡 **Animethix Engine Notice**\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "The engine is under high load or maintenance.\n"
                "**Please try again in a few moments.**\n"
                "━━━━━━━━━━━━━━━━━━━━"
            )
    finally:
        active_slots -= 1
        if not user_queue.empty():
            q_uid, q_data, q_mid, q_msg = await user_queue.get()
            try: 
                await client.delete_messages(q_uid, q_mid)
            except: 
                pass
            asyncio.create_task(process_file_request(client, q_uid, q_data, q_msg.from_user, q_msg, is_from_queue=True))
         
# =========================================================
# 7️⃣ UNIFIED START COMMAND HANDLER (Fixed & Safe)
# =========================================================
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    try:
        global active_slots
        user_id = message.chat.id
        user = message.from_user

        # 1. Spam Prevention
        current_time = time.time()
        if user_id in spam_cooldown and (current_time - spam_cooldown[user_id]) < 15:
            warn = await message.reply("⏳ **ENGINE OVERLOAD: BATCH IN PROGRESS**\n━━━━━━━━━━━━━━━━━━━━\nFinish your current batch first.")
            await asyncio.sleep(15)
            await warn.edit("🔄 **RESUMING PROTOCOL...**\n━━━━━━━━━━━━━━━━━━━━\nCompleting previous batch now.")
            await asyncio.sleep(5)
            await warn.delete()
            return
            
        spam_cooldown[user_id] = current_time
        await add_user_to_db(user_id, user.username)
        raw_data = message.command[1] if len(message.command) > 1 else "none"
        
        if is_user_banned(user_id):
            await message.reply(
                "🚫 **ACCESS RESTRICTED**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "You have been restricted by the bot.\n"
                "Contact admin for assistance."
            )
            return

        if not await check_fsub(client, user_id):
            buttons = [
                [
                    InlineKeyboardButton("📢 JOIN UPDATES", url="https://t.me/Animethix_Updates"),
                    InlineKeyboardButton("💬 JOIN CHAT", url="https://t.me/Animethix_Discussion")
                ],
                [InlineKeyboardButton("♻️ TRY AGAIN", callback_data=f"check:{raw_data}")] 
            ]
            await client.send_photo(
                chat_id=user_id,
                photo=FSUB_IMAGE,
                caption=(
                    "👋 **HELLO USER**\n\n"
                    "**JOIN OUR CHANNELS AND GROUPS THEN CLICK ON TRY AGAIN**\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "You have to join both the channel and group to get your files."
                ),
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        if raw_data == "none":
            await send_log(client, user, "Started Bot", "Main Menu")
            sent = await message.reply(
                "👋 **Welcome to Animethix!**\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                "Your private gateway to high-quality anime.\n"
                "Search our website to get your download links.\n"
                "━━━━━━━━━━━━━━━━━━━━",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🌐 OPEN WEBSITE", url="https://animethix.blogspot.com/")
                ]])
            )
            user_sessions[user_id] = [message.id, sent.id]
            return

        if len(message.command) > 1:
            # Generate a temporary streaming tracking key
            session_ref = f"sess_{int(time.time())}_{user_id}"
            
            stream_db = await load_json("stream_sessions.json", dict)
            stream_db[session_ref] = {
                "title": f"Batch Session: {raw_data}",
                "video": "https://your-direct-stream-source-url.com/file", # Placeholder layout path
                "next": "",
                "prev": ""
            }
            await save_json("stream_sessions.json", stream_db)

            # Build the layout buttons including the WebApp markup link
            inline_menu = [
                [
                    InlineKeyboardButton("📥 GET FILES DIRECTLY", callback_data=f"get_files:{raw_data}"),
                    InlineKeyboardButton("🎬 WATCH ONLINE (MINI APP)", web_app=WebAppInfo(url=f"{HF_MINI_APP_URL}?session={session_ref}"))
                ]
            ]
            
            await message.reply(
                f"🎬 **YOUR ANIME CLOUD TRACK IS READY**\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"**Session Parameters:** `{raw_data}`\n\n"
                f"You can download the raw media files directly to your storage or stream it smoothly using our zero-download inline media engine!",
                reply_markup=InlineKeyboardMarkup(inline_menu)
            )
            return

    except Exception as e:
        print(f"CRITICAL START ERROR: {e}")
        await message.reply("📡 **Engine Error:** Request could not be processed right now.")

# =========================================================
# 🛡️ PROTECTION & MODERATION SYSTEM (3-STRIKE)
# =========================================================
async def handle_strike(client, message, reason):
    user_id = message.from_user.id
    user_strikes[user_id] = user_strikes.get(user_id, 0) + 1
    strikes = user_strikes[user_id]

    if strikes >= 3:
        await update_ban_list(user_id, ban=True)
        await client.ban_chat_member(message.chat.id, user_id)
        await message.reply(
            f"🚫 **TERMINATED**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"User: {message.from_user.first_name}\n"
            f"Reason: Repeated {reason}\n"
            f"Status: **Global Ban Applied**"
        )
        await send_log(client, message.from_user, "AUTO-BAN", f"3 Strikes for {reason}")
        user_strikes.pop(user_id, None)
    else:
        warn_msg = await message.reply(
            f"⚠️ **WARNING [{strikes}/3]**\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Direct links and adding bots is forbidden!\n"
            f"Next violation leads to a permanent ban."
        )
        await asyncio.sleep(10)
        await warn_msg.delete()

# =========================================================
# 8️⃣ CALLBACK & WATCHERS
# =========================================================
@app.on_callback_query(filters.regex(r"^check:"))
@app.on_callback_query(filters.regex(r"^get_files:"))
async def callback_file_downloader(client, query):
    user_id = query.from_user.id
    raw_data = query.data.split(":", 1)[1]
    
    await query.message.delete()
    if active_slots >= MAX_CONCURRENT_USERS:
        wait_msg = await query.message.reply_to_message.reply(
            "⏳ **TRAFFIC ALERT: ALL SLOTS FULL**\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Added to queue. Auto-start shortly!"
        )
        await user_queue.put((user_id, raw_data, wait_msg.id, query.message.reply_to_message))
        return
        
    await process_file_request(client, user_id, raw_data, query.from_user, query.message.reply_to_message)
async def refresh_handler(client, query):
    user_id = query.from_user.id
    raw_data = query.data.split(":", 1)[1]

    if await check_fsub(client, user_id):
        await query.message.delete()
        query.message.from_user = query.from_user
        if raw_data != "none":
            query.message.text = f"/start {raw_data}"
            query.message.command = ["start", raw_data]
        else:
            query.message.text = "/start"
            query.message.command = ["start"]
        await start_handler(client, query.message)
    else:
        await query.answer("⚠️ You haven't joined both yet! Please join and try again.", show_alert=True)

@app.on_chat_member_updated(filters.chat([AUTH_CHANNEL, AUTH_GROUP]))
async def leave_watcher(client, update):
    if update.chat and update.chat.id in [AUTH_CHANNEL, AUTH_GROUP]:
        user_left = False
        if update.new_chat_member:
            if update.new_chat_member.status in ["left", "kicked"]:
                user_left = True
        elif update.old_chat_member and not update.new_chat_member:
            user_left = True

        if user_left:
            target = update.old_chat_member or update.new_chat_member
            user_obj = getattr(target, "user", None)
            if not user_obj: return
            await send_log(client, user_obj, "Left Channel/Group", "Vaporizing data...")

            user_id = user_obj.id
            sessions = await load_json("sessions.json")
            
            if user_id in user_sessions or str(user_id) in sessions:
                print(f"🧹 User {user_id} left. Executing Vaporize Protocol...")
                
                if str(user_id) in sessions:
                    user_data = sessions.pop(str(user_id))
                    await save_json("sessions.json", sessions)
                    for batch in user_data:
                        try:
                            await client.delete_messages(user_id, batch["msgs"])
                        except:
                            pass

                asyncio.create_task(vaporize_protocol(client, user_id))

@app.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply("❌ **Reply to a message to broadcast it.**")
    
    users = await load_json("users.json", dict)
    status = await message.reply(f"🚀 **Broadcast Started...**\nTarget: {len(users)} users.")
    
    success = 0
    failed = 0
    
    for user_id in users.keys():
        try:
            await message.reply_to_message.copy(user_id)
            success += 1
            await asyncio.sleep(0.1) 
        except Exception:
            failed += 1
            
    await status.edit(
        f"✅ **Broadcast Complete**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 Success: {success}\n"
        f"🔴 Failed: {failed}"
    )

@app.on_message(filters.command("ban") & filters.user(ADMINS))
async def ban_command(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/ban user_id`")
    try:
        target_id = int(message.text.split(None, 1)[1])
        await update_ban_list(target_id, ban=True)
        await message.reply(f"🚫 **User {target_id} has been restricted.**")
    except ValueError:
        await message.reply("❌ **Invalid User ID.**")

@app.on_message(filters.command("unban") & filters.user(ADMINS))
async def unban_command(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/unban user_id`")
    try:
        target_id = int(message.text.split(None, 1)[1])
        await update_ban_list(target_id, ban=False)
        await message.reply(f"✅ **User {target_id} access restored.**")
    except ValueError:
        await message.reply("❌ **Invalid User ID.**")

@app.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    users = await load_json("users.json", dict)
    banned = await load_json("banned.json", list)
    sessions = await load_json("sessions.json", dict)
    
    active_batches = sum(len(b) for b in sessions.values())
    
    await message.reply(
        f"📊 **Animethix Engine Stats**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Total Users: `{len(users)}` \n"
        f"🚫 Banned Users: `{len(banned)}` \n"
        f"📦 Active Batches: `{active_batches}` \n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

@app.on_message(filters.command("info") & filters.user(ADMINS))
async def info_handler(client, message):
    if len(message.command) < 2:
        return await message.reply("❌ **Usage:** `/info user_id` or reply to a user.")
    target_id = int(message.command[1])
    try:
        u = await client.get_users(target_id)
        await message.reply(f"👤 **Name:** {u.first_name}\n🆔 **ID:** `{u.id}`\n🔗 **User:** @{u.username}")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@app.on_message(filters.command("clear") & filters.user(ADMINS))
async def clear_all_history(client, message):
    status = await message.reply("☢️ **GLOBAL RESET INITIATED...**")
    users = await load_json("users.json", dict)
    sessions = await load_json("sessions.json", dict)
    total_deleted = 0

    for user_id in users:
        user_key = str(user_id)
        if user_key in sessions:
            for batch in sessions[user_key]:
                try:
                    await client.delete_messages(user_id, batch["msgs"])
                    total_deleted += len(batch["msgs"])
                except: pass

        try:
            message_ids = [m.id for m in await client.get_chat_history(user_id, limit=100)]
            if message_ids:
                await client.delete_messages(user_id, message_ids)
                total_deleted += len(message_ids)
        except Exception as e:
            pass
        await asyncio.sleep(0.5)

    await save_json("sessions.json", {})
    await status.edit(
        "💥 **TOTAL SYSTEM RESET COMPLETE**\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🧹 All users will now see a clean chat.\n"
        f"🗑️ Total items purged: `{total_deleted}`\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )

@app.on_message((filters.group | filters.channel) & filters.text)
async def link_protector(client, message):
    if message.sender_chat:
        return
    if message.from_user and (message.from_user.id in ADMINS or message.from_user.is_bot):
        return
    if "t.me/" in message.text or "http" in message.text:
        await message.delete()
        await handle_strike(client, message, "Link Spam")

@app.on_message(filters.group & filters.new_chat_members)
async def bot_hammer(client, message):
    if message.from_user and message.from_user.id in ADMINS:
        return
    for member in message.new_chat_members:
        if member.is_bot and member.id != (await client.get_me()).id:
            try:
                await client.ban_chat_member(message.chat.id, member.id)
                await message.delete() 
                await handle_strike(client, message, "Adding unauthorized bots")
            except Exception as e:
                print(f"Bot Hammer Error: {e}")

@app.on_message(filters.command("cleanbots") & filters.user(ADMINS))
async def clean_bots_handler(client, message):
    status = await message.reply("🧹 **SCANNING FOR UNAUTHORIZED BOTS...**")
    me = await client.get_me()
    count = 0
    async for member in client.get_chat_members(message.chat.id):
        if member.user.is_bot and member.user.id != me.id:
            try:
                await client.ban_chat_member(message.chat.id, member.user.id)
                count += 1
            except:
                pass
    await status.edit(f"✅ **CLEANUP COMPLETE**\nRemoved `{count}` unauthorized bots.")

# =========================================================
# 🚀 SYSTEM ENTRY POINT (Stable Version as requested)
# =========================================================
if __name__ == "__main__":
    # 1. Start the Flask server in a separate thread
    keep_alive() 
    
    # 2. Start the Bot using the standard .start() method
    app.start() 
    
    print("🚀 Animethix Engine v3.0 is LIVE & PROTECTED...")
    
    # 3. Now that the bot is STARTED, we can start the Janitor
    loop = asyncio.get_event_loop()
    loop.create_task(auto_janitor(app))
    
    # 4. Keep the bot alive (exactly as requested)
    from pyrogram import idle
    idle()
