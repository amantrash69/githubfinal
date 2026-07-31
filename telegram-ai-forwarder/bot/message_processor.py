import datetime
from telethon import events
from telethon.tl.types import MessageMediaWebPage
from bot.database import get_db, is_paused

# ==========================================
# 🤖 YOUR LINK CONVERTER BOT
# ==========================================
LINK_BOT_USERNAME = "@Lootkamallbot"

async def process_new_message(client, message):
    print("\n--- 🟢 NEW MESSAGE DETECTED ---")
    
    if is_paused():
        print("❌ Bot is paused. Ignoring message.")
        return

    chat = await message.get_chat()
    if not chat: 
        return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)
    print(f"📡 Message arrived from ID: {chat_id} | Username: {chat_username}")

    conn = get_db()
    
    try:
        # ==========================================
        # 1. VERIFY SOURCE
        # ==========================================
        matched_source_name = None
        sources = conn.execute("SELECT * FROM sources").fetchall()
        
        for s in sources:
            s_tup = tuple(s)
            s_id = str(s_tup[0])
            s_name = str(s_tup[1]) if len(s_tup) > 1 else str(s_tup[0])
            clean_s_name = s_name.replace('@', '').lower()
            
            # Robust matching for both IDs and Usernames
            if str(chat_id) == s_id or str(chat_id) == f"-100{s_id}" or str(chat_id).replace('-100', '') == s_id.replace('-100', '') or (chat_username and clean_s_name == chat_username.lower()):
                matched_source_name = s_name
                print(f"✅ Matched Source: {matched_source_name}")
                break
                
        if not matched_source_name:
            print("❌ Chat is NOT in sources list. Ignoring.")
            return

        # ==========================================
        # 2. FIND ROUTES FOR THIS SOURCE
        # ==========================================
        target_names = []
        try:
            routes_data = conn.execute("SELECT * FROM routes").fetchall()
        except:
            try:
                routes_data = conn.execute("SELECT * FROM routing").fetchall()
            except:
                routes_data = []

        for r in routes_data:
            r_tup = tuple(r)
            route_src = str(r_tup[0])
            route_tgt = str(r_tup[1]) if len(r_tup) > 1 else ""
            
            if route_src.lower() == matched_source_name.lower():
                target_names.append(route_tgt)

        if not target_names:
            print("❌ No route assigned for this source. Ignoring.")
            return
            
        print(f"🎯 Route Target(s) Found: {target_names}")

        # ==========================================
        # 3. CHECK BLACKLIST / FILTERS
        # ==========================================
        message_text = (message.text or "").lower()
        if message_text:
            try:
                filters = conn.execute("SELECT * FROM filters").fetchall()
                for f in filters:
                    f_tup = tuple(f)
                    filter_val = str(f_tup[-1]).lower().strip()
                    
                    if filter_val and filter_val in message_text:
                        print(f"🚫 MESSAGE BLOCKED: Contains blacklisted text '{filter_val}'")
                        
                        # Update stats for rejection
                        today = datetime.datetime.now().strftime("%Y-%m-%d")
                        conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                        conn.execute("UPDATE statistics SET processed = processed + 1, rejected = rejected + 1 WHERE date=?", (today,))
                        conn.commit()
                        return # Stop the script instantly!
            except Exception as e:
                print(f"⚠️ Filter check error: {e}")

        # ==========================================
        # 4. SEND TO CONVERTER BOT
        # ==========================================
        print(f"🚀 Sending to {LINK_BOT_USERNAME}...")
        try:
            async with client.conversation(LINK_BOT_USERNAME, timeout=15) as conv:
                
                # Send original message (ignoring link previews)
                if message.media and not isinstance(message.media, MessageMediaWebPage):
                    await conv.send_file(message.media, caption=message.text)
                else:
                    await conv.send_message(message.text)

                print("⏳ Waiting for bot reply...")
                converted_response = await conv.get_response()
                print("✅ Got reply from bot!")

            # ==========================================
            # 5. FORWARD TO FINAL TARGET(S)
            # ==========================================
            for t_name in target_names:
                try:
                    print(f"➡️ Forwarding final message to Target: {t_name}")
                    
                    # Send converted message (ignoring link previews)
                    if converted_response.media and not isinstance(converted_response.media, MessageMediaWebPage):
                        await client.send_file(t_name, converted_response.media, caption=converted_response.text)
                    else:
                        await client.send_message(t_name, converted_response.text)
                        
                    print(f"🎉 SUCCESS! Message forwarded to {t_name}.")
                    
                    # Update stats for successful forward
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                    conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                    conn.commit()
                    
                except Exception as e:
                    print(f"❌ Failed to post in Target {t_name}: {e}")
                    # Update stats for error
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                    conn.execute("UPDATE statistics SET processed = processed + 1, errors = errors + 1 WHERE date=?", (today,))
                    conn.commit()
                    
        except Exception as e:
            print(f"❌ Failed during Bot Conversation: {e}")
            
    finally:
        print("--- 🏁 PROCESS FINISHED ---\n")
        conn.close()
