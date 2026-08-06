import os
import datetime
from telethon import events
from bot.database import get_db, is_paused, set_paused, add_source, add_target, add_route, add_filter

ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 0))

def register_admin_handlers(client):
    
    @client.on(events.NewMessage(pattern=r'^/admin'))
    async def admin_start(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
        
        help_text = f"""⚙️ **ADMIN PANEL**
Status: {status}

**📡 Channels**
`/addsource @username` (or Reply to a forwarded message with `/addsource`)
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
        if event.sender_id != ADMIN_USER_ID: return
        set_paused(True)
        await event.reply("🔴 Forwarding is now PAUSED.")

    @client.on(events.NewMessage(pattern=r'^/resume'))
    async def resume_bot(event):
        if event.sender_id != ADMIN_USER_ID: return
        set_paused(False)
        await event.reply("🟢 Forwarding is now ACTIVE.")

    # ==========================================
    # UPGRADED: Smart /addsource handler
    # ==========================================
    @client.on(events.NewMessage(pattern=r'^/addsource\s*(.*)'))
    async def cmd_add_source(event):
        if event.sender_id != ADMIN_USER_ID: return
        
        target = event.pattern_match.group(1).strip()
        
        # Scenario 1: Admin replied to a forwarded message with /addsource
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            if reply_msg.forward:
                if reply_msg.forward.chat:
                    chat_id = reply_msg.forward.chat.id
                    title = getattr(reply_msg.forward.chat, 'title', str(chat_id))
                    target = str(chat_id)
                    add_source(chat_id, target)
                    await event.reply(f"✅ Auto-Added Private Source: **{title}** (`{chat_id}`)")
                    return
                elif reply_msg.forward.sender_id:
                    sender_id = reply_msg.forward.sender_id
                    target = str(sender_id)
                    add_source(sender_id, target)
                    await event.reply(f"✅ Auto-Added Private User/Bot Source: `{sender_id}`")
                    return
        
        # Scenario 2: Standard text command (/addsource @username or /addsource -100...)
        if not target:
            await event.reply("❌ Please provide a @username, an ID, or reply to a forwarded message with `/addsource`.")
            return

        try:
            # If the admin manually typed a numeric ID (like -100123456)
            if target.lstrip('-').isdigit():
                chat_id = int(target)
                add_source(chat_id, target)
                await event.reply(f"✅ Source ID `{chat_id}` added successfully.")
            else:
                # If the admin typed a @username
                entity = await client.get_entity(target)
                add_source(entity.id, target)
                await event.reply(f"✅ Source {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure your account is a member of that channel.")

    # ==========================================
    # NEW: Forward ID Detector (Auto-Responder)
    # ==========================================
    @client.on(events.NewMessage())
    async def forward_detector(event):
        if event.sender_id != ADMIN_USER_ID: return
        if not event.forward: return
        
        if event.forward.chat:
            chat_id = event.forward.chat.id
            title = getattr(event.forward.chat, 'title', 'Unknown Group')
            await event.reply(f"📡 **Source ID Detected!**\nName: {title}\nID: `{chat_id}`\n\nTo add this group as a source, just reply to the message you just sent with `/addsource`, or copy this command:\n`/addsource {chat_id}`")
        elif event.forward.sender_id:
            sender_id = event.forward.sender_id
            await event.reply(f"👤 **User/Bot ID Detected!**\nID: `{sender_id}`\n\nTo add this user as a source, copy this command:\n`/addsource {sender_id}`")

    @client.on(events.NewMessage(pattern=r'^/addtarget\s+(.+)'))
    async def cmd_add_target(event):
        if event.sender_id != ADMIN_USER_ID: return
        target = event.pattern_match.group(1).strip()
        try:
            entity = await client.get_entity(target)
            add_target(entity.id, target)
            await event.reply(f"✅ Target {target} added successfully.")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\nMake sure you have admin rights to post there.")

    @client.on(events.NewMessage(pattern=r'^/addroute\s+(.+)'))
    async def cmd_add_route(event):
        if event.sender_id != ADMIN_USER_ID: return
        text = event.pattern_match.group(1).strip()
        if "->" not in text:
            await event.reply("❌ Wrong format. Use: `/addroute @source -> @target`")
            return
        src, tgt = [x.strip() for x in text.split("->")]
        add_route(src, tgt)
        await event.reply(f"✅ Route created: {src} -> {tgt}")

    @client.on(events.NewMessage(pattern=r'^/addword\s+(.+)'))
    async def cmd_add_word(event):
        if event.sender_id != ADMIN_USER_ID: return
        word = event.pattern_match.group(1).strip()
        add_filter('word', word)
        await event.reply(f"✅ Blacklisted word added: {word}")

    @client.on(events.NewMessage(pattern=r'^/addlink\s+(.+)'))
    async def cmd_add_link(event):
        if event.sender_id != ADMIN_USER_ID: return
        link = event.pattern_match.group(1).strip()
        add_filter('link', link)
        await event.reply(f"✅ Blocked link added: {link}")

    @client.on(events.NewMessage(pattern=r'^/adddomain\s+(.+)'))
    async def cmd_add_domain(event):
        if event.sender_id != ADMIN_USER_ID: return
        dom = event.pattern_match.group(1).strip()
        add_filter('domain', dom)
        await event.reply(f"✅ Blocked domain added: {dom}")

    @client.on(events.NewMessage(pattern=r'^/stats'))
    async def cmd_stats(event):
        if event.sender_id != ADMIN_USER_ID: return
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
        if event.sender_id != ADMIN_USER_ID: return
        conn = get_db()
        src_c = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        tgt_c = conn.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
        conn.close()
        st = "🟢 ACTIVE" if not is_paused() else "🔴 PAUSED"
        await event.reply(f"🔧 **System Status**\n\nForwarding is {st}\n📡 Sources: {src_c}\n🎯 Targets: {tgt_c}")
