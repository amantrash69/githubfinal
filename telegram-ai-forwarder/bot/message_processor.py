import datetime
from telethon import events
from bot.database import get_db, is_paused

# ==========================================
# 🤖 PUT YOUR LINK-SWAP BOT USERNAME HERE:
# ==========================================
LINK_BOT_USERNAME = "@Lootkamallbot"
# ==========================================

async def process_new_message(client, message):
    if is_paused():
        return

    # Check if this chat is one of our sources
    chat = await message.get_chat()
    if not chat: 
        return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)

    conn = get_db()
    
    # Find matching source in Database
    source = None
    sources = conn.execute("SELECT * FROM sources").fetchall()
    for s in sources:
        stored_val = str(s['source_id']).replace('@', '')
        if str(chat_id) == stored_val or str(chat_id) == f"-100{stored_val}" or (chat_username and stored_val.lower() == chat_username.lower()):
            source = s
            break
            
    if not source:
        conn.close()
        return

    # Get all Target Channels for this Source
    routes = conn.execute("SELECT target_id FROM routing WHERE source_id=?", (source['source_id'],)).fetchall()
    
    if not routes:
        conn.close()
        return

    try:
        # 1. Talk to your link-swapping bot!
        # timeout=15 means it will wait up to 15 seconds for your bot to reply
        async with client.conversation(LINK_BOT_USERNAME, timeout=15) as conv:
            
            # Send the original message to your converter bot
            if message.media:
                await conv.send_file(message.media, caption=message.text)
            else:
                await conv.send_message(message.text)

            # Wait for your bot to reply with the converted message
            converted_response = await conv.get_response()

        # 2. Send the newly converted response to your target channels
        for route in routes:
            target_id = route['target_id']
            try:
                # Send it to the target!
                if converted_response.media:
                    await client.send_file(target_id, converted_response.media, caption=converted_response.text)
                else:
                    await client.send_message(target_id, converted_response.text)
                    
                # Log success for your /stats command
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                conn.commit()
                
            except Exception as e:
                print(f"Failed to send to {target_id}: {e}")
                
    except Exception as e:
        print(f"Failed to communicate with Link Bot: {e}")
        
    finally:
        conn.close()
