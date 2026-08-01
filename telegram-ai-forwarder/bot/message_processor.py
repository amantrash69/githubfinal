import datetime
from telethon import events
from telethon.tl.types import MessageMediaWebPage
from bot.database import get_db, is_paused

LINK_BOT_USERNAME = "@Lootkamallbot"

def check_blacklist(text, conn):
    """
    Bulletproof blacklist checker.
    Scans text against all filters in DB regardless of column layout.
    """
    if not text:
        return False, None

    text_lower = str(text).lower()

    try:
        filters = conn.execute("SELECT * FROM filters").fetchall()
        for f in filters:
            f_tup = tuple(f)
            # Scan each column entry in the tuple
            for val in f_tup:
                clean_val = str(val).lower().strip()
                # Skip column type labels or numbers
                if clean_val in ['word', 'link', 'domain', 'none', ''] or clean_val.isdigit():
                    continue
                
                # If the blacklisted word/domain/link is inside the message text
                if clean_val in text_lower:
                    return True, clean_val
    except Exception as e:
        print(f"⚠️ Filter database read error: {e}")

    return False, None


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

        # Extract text/caption safely
        original_text = message.text or message.caption or getattr(message, 'message', '') or ""

        # ==========================================
        # 3. CHECK BLACKLIST (ORIGINAL MESSAGE)
        # ==========================================
        is_blocked, blocked_word = check_blacklist(original_text, conn)
        if is_blocked:
            print(f"🚫 MESSAGE BLOCKED (Pre-conversion): Contains '{blocked_word}'")
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
            conn.execute("UPDATE statistics SET processed = processed + 1, rejected = rejected + 1 WHERE date=?", (today,))
            conn.commit()
            return

        # ==========================================
        # 4. SEND TO CONVERTER BOT
        # ==========================================
        print(f"🚀 Sending to {LINK_BOT_USERNAME}...")
        try:
            async with client.conversation(LINK_BOT_USERNAME, timeout=15) as conv:
                if message.media and not isinstance(message.media, MessageMediaWebPage):
                    await conv.send_file(message.media, caption=message.text)
                else:
                    await conv.send_message(message.text)

                print("⏳ Waiting for bot reply...")
                converted_response = await conv.get_response()
                print("✅ Got reply from bot!")

            converted_text = converted_response.text or converted_response.caption or getattr(converted_response, 'message', '') or ""

            # ==========================================
            # 5. CHECK BLACKLIST (CONVERTED MESSAGE)
            # ==========================================
            is_blocked, blocked_word = check_blacklist(converted_text, conn)
            if is_blocked:
                print(f"🚫 MESSAGE BLOCKED (Post-conversion): Contains '{blocked_word}'")
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                conn.execute("UPDATE statistics SET processed = processed + 1, rejected = rejected + 1 WHERE date=?", (today,))
                conn.commit()
                return

            # ==========================================
            # 6. FORWARD TO TARGET(S)
            # ==========================================
            for t_name in target_names:
                try:
                    print(f"➡️ Forwarding final message to Target: {t_name}")
                    
                    if converted_response.media and not isinstance(converted_response.media, MessageMediaWebPage):
                        await client.send_file(t_name, converted_response.media, caption=converted_response.text)
                    else:
                        await client.send_message(t_name, converted_response.text)
                        
                    print(f"🎉 SUCCESS! Message forwarded to {t_name}.")
                    
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                    conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                    conn.commit()
                    
                except Exception as e:
                    print(f"❌ Failed to post in Target {t_name}: {e}")
                    today = datetime.datetime.now().strftime("%Y-%m-%d")
                    conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                    conn.execute("UPDATE statistics SET processed = processed + 1, errors = errors + 1 WHERE date=?", (today,))
                    conn.commit()
                    
        except Exception as e:
            print(f"❌ Failed during Bot Conversation: {e}")
            
    finally:
        print("--- 🏁 PROCESS FINISHED ---\n")
        conn.close()
