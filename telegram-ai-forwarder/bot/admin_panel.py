import os
import re
import datetime
from telethon import events
from bot.database import get_db, is_paused, set_paused, add_source, add_target, add_route, add_filter

# ==========================================
# 👑 BULLETPROOF ADMIN ID PARSER
# ==========================================
raw_admin_ids = str(os.environ.get("ADMIN_USER_ID", "0"))
# Extracts ONLY the numbers, completely ignoring accidental quotes, spaces, or brackets!
ADMIN_USER_IDS = [int(x) for x in re.findall(r'\d+', raw_admin_ids)]

print(f"\n👑 ADMIN SYSTEM ACTIVE | Authorized IDs: {ADMIN_USER_IDS}\n")

def is_admin(sender_id):
    if not sender_id:
        return False
    return sender_id in ADMIN_USER_IDS

def register_admin_handlers(client):
    
    # 🛠️ TRACKER: Logs every command attempt (Python 3.12 Safe Regex)
    @client.on(events.NewMessage(pattern=r'(?i)^/(admin|status|stats|addsource|addtarget|addroute|addword|addlink|adddomain|pause|resume)', incoming=True, outgoing=True))
    async def command_tracker(event):
        sender = event.sender_id
        print(f"\n--- 🛠️ COMMAND DETECTED: {event.raw_text} ---")
        print(f"👤 Sender ID: {sender}")
        if not is_admin(sender):
            print(f"❌ ACCESS DENIED: {sender} is not in the Admin List.")
        else:
            print(f"✅ ACCESS GRANTED: Executing command...")

    @client.on(events.NewMessage(pattern=r'(?i)^/admin', incoming=True, outgoing=True))
    async def admin_start(event):
        if not is_admin(event.sender_id): return
        status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
        
        help_text = f"""⚙️ **ADMIN PANEL**
Status: {status}

**📡 Channels**
`/addsource @username`
`/addtarget @username`

**🔀 Routing**
`/addroute @source -> @target`

**🚫 Blacklists / Filters**
`/addword casino`
`/addlink example.com`
`/adddomain badsite.com`

**⚙️ Controls**
`/pause` (Stops forwarding)
`/resume` (Starts forwarding)
`/stats` (See today's numbers)
`/status` (System info)
"""
        await event.reply(help_text)

    @client.on(events.NewMessage(pattern=r'(?i)^/pause', incoming=True, outgoing=True))
    async def pause_bot(event):
        if not is_admin(event.sender_id): return
        set_paused(True)
        await event.reply("🔴 Forwarding is now PAUSED.")

    @client.on(events.NewMessage(pattern=r'(?i)^/resume', incoming=True, outgoing=True))
    async def resume_bot(event):
        if not is_admin(event.sender_id): return
        set_paused(False)
        await event.reply("🟢 Forwarding is now ACTIVE.")

    @client.on(events.NewMessage(pattern=r'(?i)^/addsource\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_source(event):
        if not is_admin(event.sender_id): return
        target = event.pattern_match.group(1).strip()
        try:
            entity = await client.get_entity(target)
            add_source(entity.id, target)
            await event.reply(f"✅ Source {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure your account is a member of that channel.")

    @client.on(events.NewMessage(pattern=r'(?i)^/addtarget\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_target(event):
        if not is_admin(event.sender_id): return
        target = event.pattern_match.group(1).strip()
        try:
            entity = await client.get_entity(target)
            add_target(entity.id, target)
            await event.reply(f"✅ Target {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure you have rights to post there.")

    @client.on(events.NewMessage(pattern=r'(?i)^/addroute\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_route(event):
        if not is_admin(event.sender_id): return
        text = event.pattern_match.group(1).strip()
        if "->" not in text:
            await event.reply("❌ Wrong format. Use: `/addroute @source -> @target`")
            return
        src, tgt = [x.strip() for x in text.split("->")]
        add_route(src, tgt)
        await event.reply(f"✅ Route created: {src} -> {tgt}")

    @client.on(events.NewMessage(pattern=r'(?i)^/addword\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_word(event):
        if not is_admin(event.sender_id): return
        word = event.pattern_match.group(1).strip()
        add_filter('word', word)
        await event.reply(f"✅ Blacklisted word added: {word}")

    @client.on(events.NewMessage(pattern=r'(?i)^/addlink\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_link(event):
        if not is_admin(event.sender_id): return
        link = event.pattern_match.group(1).strip()
        add_filter('link', link)
        await event.reply(f"✅ Blocked link added: {link}")

    @client.on(events.NewMessage(pattern=r'(?i)^/adddomain\s+(.+)', incoming=True, outgoing=True))
    async def cmd_add_domain(event):
        if not is_admin(event.sender_id): return
        dom = event.pattern_match.group(1).strip()
        add_filter('domain', dom)
        await event.reply(f"✅ Blocked domain added: {dom}")

    @client.on(events.NewMessage(pattern=r'(?i)^/stats', incoming=True, outgoing=True))
    async def cmd_stats(event):
        if not is_admin(event.sender_id): return
        conn = get_db()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        stats = conn.execute("SELECT * FROM statistics WHERE date=?", (today,)).fetchone()
        conn.close()
        
        if stats:
            text = f"📊 **Stats for Today**\n\n📥 Processed: {stats['processed']}\n✅ Forwarded: {stats['forwarded']}\n🚫 Rejected: {stats['rejected']}\n❌ Errors: {stats['errors']}"
        else:
            text = "📊 No messages processed yet today."
        await event.reply(text)

    @client.on(events.NewMessage(pattern=r'(?i)^/status', incoming=True, outgoing=True))
    async def cmd_status(event):
        if not is_admin(event.sender_id): return
        conn = get_db()
        src_c = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        tgt_c = conn.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        conn.close()
        st = "🟢 ACTIVE" if not is_paused() else "🔴 PAUSED"
        await event.reply(f"🔧 **System Status**\n\nForwarding is {st}\n📡 Sources: {src_c}\n🎯 Targets: {tgt_c}")
