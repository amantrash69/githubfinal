import re
from urllib.parse import urlparse
from bot.database import get_db, is_paused, log_activity
from bot.publisher import forward_message

async def process_new_message(client, message):
    source_chat_id = str(message.chat_id)
    text = message.text or message.caption or ""
    
    # 1. Check if paused
    if is_paused():
        return
        
    conn = get_db()
    
    # 2. Check source is enabled
    source = conn.execute("SELECT * FROM sources WHERE channel_id=? AND enabled=1", (source_chat_id,)).fetchone()
    if not source:
        conn.close()
        return

    source_name = source['username'] or source_chat_id

    # Fetch Filters
    filters = conn.execute("SELECT * FROM filters").fetchall()
    blacklist_words = [f['value'].lower() for f in filters if f['filter_type'] == 'word']
    blocked_links = [f['value'].lower() for f in filters if f['filter_type'] == 'link']
    blocked_domains = [f['value'].lower() for f in filters if f['filter_type'] == 'domain']
    required_words = [f['value'].lower() for f in filters if f['filter_type'] == 'required']

    # 3. Check Blacklist Words (Case Insensitive)
    text_lower = text.lower()
    for word in blacklist_words:
        if re.search(rf'\b{re.escape(word)}\b', text_lower):
            log_activity('rejected', source_name, reason=f'Blacklisted word: {word}')
            conn.close()
            return

    # 4 & 5. Check Blocked URLs and Domains
    urls = re.findall(r'(https?://[^\s]+)', text_lower)
    for url in urls:
        if url in blocked_links:
            log_activity('rejected', source_name, reason=f'Blocked link: {url}')
            conn.close()
            return
        domain = urlparse(url).netloc
        if domain in blocked_domains:
            log_activity('rejected', source_name, reason=f'Blocked domain: {domain}')
            conn.close()
            return

    # 6. Check Required Words
    if required_words:
        if not any(re.search(rf'\b{re.escape(word)}\b', text_lower) for word in required_words):
            log_activity('rejected', source_name, reason='Missing required word')
            conn.close()
            return

    # 7. Find Target Channels (Routing)
    routes = conn.execute('''
        SELECT t.channel_id, t.username FROM routes r
        JOIN targets t ON r.target_id = t.channel_id
        WHERE r.source_id = ? AND r.enabled = 1 AND t.enabled = 1
    ''', (source_chat_id,)).fetchall()

    if not routes:
        conn.close()
        return

    # 8. Duplicate Check & Forwarding (9 & 10)
    for target in routes:
        target_id = target['channel_id']
        target_name = target['username'] or target_id
        
        is_dup = conn.execute("SELECT 1 FROM processed_messages WHERE source_msg_id=? AND target_channel=?", (message.id, target_id)).fetchone()
        
        if not is_dup:
            try:
                await forward_message(client, message, target_id)
                conn.execute("INSERT INTO processed_messages (source_msg_id, source_channel, target_channel, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)", 
                             (message.id, source_chat_id, target_id))
                log_activity('forwarded', source_name, target_name)
            except Exception as e:
                log_activity('error', source_name, target_name, reason=str(e))
                
    conn.commit()
    conn.close()
