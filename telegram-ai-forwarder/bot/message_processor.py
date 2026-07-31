import datetime
from telethon import events
from bot.database import get_db, is_paused

LINK_BOT_USERNAME = "@Lootkamallbot"

async def process_new_message(client, message):
    if is_paused():
        return

    chat = await message.get_chat()
    if not chat: 
        return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)

    conn = get_db()
    
    # 1. CHECK IF THIS CHAT IS A SOURCE
    matched_source_name = None
    sources = conn.execute("SELECT * FROM sources").fetchall()
    for s in sources:
        s_tup = tuple(s)
        s_id = str(s_tup[0])
        s_name = str(s_tup[1]) if len(s_tup) > 1 else str(s_tup[0])
        
        clean_s_name = s_name.replace('@', '').lower()
        
        if str(chat_id) == s_id or str(chat_id) == f"-100{s_id}" or (chat_username and clean_s_name == chat_username.lower()):
            matched_source_name = s_name
            break
            
    if not matched_source_name:
        conn.close()
        return

    # 2. FIND WHICH TARGETS THIS SOURCE GOES TO (Bulletproof table check)
    target_names = []
    try:
        # Try finding the table named 'routes'
        routes_data = conn.execute("SELECT * FROM routes").fetchall()
    except:
        try:
            # If that fails, try 'routing'
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
        conn.close()
        return

    # 3. GET THE NUMERIC IDs OF THOSE TARGETS
    target_ids = []
    targets = conn.execute("SELECT * FROM targets").fetchall()
    for t in targets:
        t_tup = tuple(t)
        t_id = t_tup[0]
        t_name = str(t_tup[1]) if len(t_tup) > 1 else ""
        
        for tn in target_names:
            if t_name.lower() == tn.lower():
                target_ids.append(t_id)

    if not target_ids:
        conn.close()
        return

    # 4. SEND TO LOOTKAMALLBOT & FORWARD TO FINAL TARGET
    try:
        async with client.conversation(LINK_BOT_USERNAME, timeout=15) as conv:
            # Send to the link converter
            if message.media:
                await conv.send_file(message.media, caption=message.text)
            else:
                await conv.send_message(message.text)

            # Wait for Lootkamallbot to reply
            converted_response = await conv.get_response()

        # Blast the converted response to your targets!
        for t_id in target_ids:
            try:
                if converted_response.media:
                    await client.send_file(t_id, converted_response.media, caption=converted_response.text)
                else:
                    await client.send_message(t_id, converted_response.text)
                    
                # Update /stats
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                conn.commit()
                
            except Exception as e:
                print(f"Failed to send to target {t_id}: {e}")
                
    except Exception as e:
        print(f"Failed to communicate with Link Bot: {e}")
        
    finally:
        conn.close()
