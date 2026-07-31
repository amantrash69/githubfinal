import datetime
from telethon import events
from bot.database import get_db, is_paused

LINK_BOT_USERNAME = "@Lootkamallbot"

async def process_new_message(client, message):
    print("\n--- 🟢 NEW MESSAGE DETECTED ---")
    if is_paused():
        print("❌ Bot is paused.")
        return

    chat = await message.get_chat()
    if not chat: 
        print("❌ Could not get chat data.")
        return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)
    print(f"📡 Message arrived from ID: {chat_id} | Username: {chat_username}")

    conn = get_db()
    
    # 1. CHECK SOURCES
    matched_source_name = None
    sources = conn.execute("SELECT * FROM sources").fetchall()
    print(f"🗄️ Sources in DB: {[tuple(s) for s in sources]}")
    
    for s in sources:
        s_tup = tuple(s)
        s_id = str(s_tup[0])
        s_name = str(s_tup[1]) if len(s_tup) > 1 else str(s_tup[0])
        
        clean_s_name = s_name.replace('@', '').lower()
        
        # Super robust matching
        if str(chat_id) == s_id or str(chat_id) == f"-100{s_id}" or str(chat_id).replace('-100', '') == s_id.replace('-100', '') or (chat_username and clean_s_name == chat_username.lower()):
            matched_source_name = s_name
            print(f"✅ Matched Source: {matched_source_name}")
            break
            
    if not matched_source_name:
        print("❌ This chat is NOT in your sources list. Ignoring message.")
        conn.close()
        return

    # 2. CHECK ROUTES
    target_names = []
    try:
        routes_data = conn.execute("SELECT * FROM routes").fetchall()
    except:
        try:
            routes_data = conn.execute("SELECT * FROM routing").fetchall()
        except:
            routes_data = []
            
    print(f"🔀 Routes in DB: {[tuple(r) for r in routes_data]}")

    for r in routes_data:
        r_tup = tuple(r)
        route_src = str(r_tup[0])
        route_tgt = str(r_tup[1]) if len(r_tup) > 1 else ""
        
        if route_src.lower() == matched_source_name.lower():
            target_names.append(route_tgt)

    if not target_names:
        print("❌ No routes found for this source. Ignoring message.")
        conn.close()
        return
        
    print(f"🎯 Target Names Found: {target_names}")

    # 3. CHECK TARGET IDs
    target_ids = []
    targets = conn.execute("SELECT * FROM targets").fetchall()
    print(f"🗄️ Targets in DB: {[tuple(t) for t in targets]}")
    
    for t in targets:
        t_tup = tuple(t)
        t_id = t_tup[0]
        t_name = str(t_tup[1]) if len(t_tup) > 1 else ""
        
        for tn in target_names:
            if t_name.lower() == tn.lower():
                target_ids.append(t_id)

    if not target_ids:
        print("❌ Could not find matching Target IDs in database. Ignoring.")
        conn.close()
        return

    # 4. SEND TO LOOTKAMALLBOT
    print(f"🚀 Sending to {LINK_BOT_USERNAME}...")
    try:
        async with client.conversation(LINK_BOT_USERNAME, timeout=15) as conv:
            if message.media:
                await conv.send_file(message.media, caption=message.text)
            else:
                await conv.send_message(message.text)

            print("⏳ Waiting for bot reply...")
            converted_response = await conv.get_response()
            print("✅ Got reply from bot!")

        # 5. SEND TO FINAL TARGET
        for t_id in target_ids:
            try:
                print(f"➡️ Forwarding final message to Target ID: {t_id}")
                if converted_response.media:
                    await client.send_file(t_id, converted_response.media, caption=converted_response.text)
                else:
                    await client.send_message(t_id, converted_response.text)
                    
                print("🎉 SUCCESS! Message forwarded.")
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                conn.commit()
                
            except Exception as e:
                print(f"❌ Failed to post in Target {t_id}: {e}")
                
    except Exception as e:
        print(f"❌ Failed during Bot Conversation: {e}")
        
    finally:
        print("--- 🏁 PROCESS FINISHED ---\n")
        conn.close()
