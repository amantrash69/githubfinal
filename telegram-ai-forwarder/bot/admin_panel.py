import os
import datetime
from telethon import events
from bot.database import get_db, is_paused, set_paused, add_source, add_target, add_route, add_filter

# This safely splits the comma-separated IDs from Render
raw_admin_ids = os.environ.get("ADMIN_USER_ID", "0")
ADMIN_USER_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

def is_admin(sender_id):
    return sender_id in ADMIN_USER_IDS

def register_admin_handlers(client):
    
    @client.on(events.NewMessage(pattern=r'^/admin'))
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
`/pause` (Stops all forwarding)
`/resume` (Starts forwarding again)
`/stats` (See today's numbers)
`/status` (System info)
"""
        await event.reply(help_text)

    @client.on(events.NewMessage(pattern=r'^/pause'))
    async def pause_bot(event):
        if not is_admin(event.sender_id): return
        set_paused(True)
        await event.reply("🔴 Forwarding is now PAUSED.")

    @client.on(events.NewMessage(pattern=r'^/resume'))
    async def resume_bot(event):
        if not is_admin(event.sender_id): return
        set_paused(False)
        await event.reply("🟢 Forwarding is now ACTIVE.")

    @client.on(events.NewMessage(pattern=r'^/addsource\s+(.+)'))
    async def cmd_add_source(event):
        if not is_admin(event.sender_id): return
        target = event.pattern_match.group(1).strip()
        try:
            entity = await client.get_entity(target)
            add_source(entity.id, target)
            await event.reply(f"✅ Source {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure your account is a member of that channel.")

    @client.on(events.NewMessage(pattern=r'^/addtarget\s+(.+)'))
    async def cmd_add_target(event):
        if not is_admin(event.sender_id): return
        target = event.pattern_match.group(1).strip()
        try:
            entity = await client.get_entity(target)
            add_target(entity.id, target)
            await event.reply(f"✅ Target {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure you have admin rights to post there.")

    @client.on(events.NewMessage(pattern=r'^/addroute\s+(.+)'))
    async def cmd_add_route(event):
        if not is_admin(event.sender_id): return
        text = event.pattern_match.group(1).strip()
        if "->" not in text:
            await event.reply("❌ Wrong format. Use: `/addroute @source -> @target`")
            return
        src, tgt = [x.strip() for x in text.split("->")]
        add_route(src, tgt)
        await event.reply(f"✅ Route created: {src} -> {tgt}")

    @client.on(events.NewMessage(pattern=r'^/addword\s+(.+)'))
    async def cmd_add_word(event):
        if not is_admin(event.sender_id): return
        word = event.pattern_match.group(1).strip()
        add_filter('word', word)
        await event.reply(f"✅ Blacklisted word added: {word}")

    @client.on(events.NewMessage(pattern=r'^/addlink\s+(.+)'))
    async def cmd_add_link(event):
        if not is_admin(event.sender_id): return
        link = event.pattern_match.group(1).strip()
        add_filter('link', link)
        await event.reply(f"✅ Blocked link added: {link}")

    @client.on(events.NewMessage(pattern=r'^/adddomain\s+(.+)'))
    async def cmd_add_domain(event):
        if not is_admin(event.sender_id): return
        dom = event.pattern_match.group(1).strip()
        add_filter('domain', dom)
        await event.reply(f"✅ Blocked domain added: {dom}")

    @client.on(events.NewMessage(pattern=r'^/stats'))
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

    @client.on(events.NewMessage(pattern=r'^/status'))
    async def cmd_status(event):
        if not is_admin(event.sender_id): return
        conn = get_db()
        src_c = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        tgt_c = conn.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        conn.close()
        st = "🟢 ACTIVE" if not is_paused() else "🔴 PAUSED"
        await event.reply(f"🔧 **System Status**\n\nForwarding is {st}\n📡 Sources: {src_c}\n🎯 Targets: {tgt_c}")
