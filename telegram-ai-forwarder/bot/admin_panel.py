import os
from telethon import events, Button
from bot.database import get_db, is_paused, set_paused, add_source, add_target, add_route, add_filter

ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", 0))
user_states = {}

def main_menu_btns():
    return [
        [Button.inline("📡 Sources", b"menu_src"), Button.inline("🎯 Targets", b"menu_tgt")],
        [Button.inline("🔀 Routing", b"menu_rtg"), Button.inline("🚫 Filters", b"menu_flt")],
        [Button.inline("📊 Stats", b"menu_sts"), Button.inline("📝 Activity", b"menu_act")],
        [Button.inline("⏸ Pause / ▶️ Resume", b"toggle_pause"), Button.inline("🔧 Status", b"menu_stat")]
    ]

def register_admin_handlers(client):
    
    @client.on(events.NewMessage(pattern='/admin'))
    async def admin_start(event):
        if event.sender_id != ADMIN_USER_ID:
            await event.reply("❌ Access denied.")
            return
        user_states.pop(event.sender_id, None)
        status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
        await event.reply(f"⚙️ **ADMIN PANEL**\n\nStatus: {status}", buttons=main_menu_btns())

    @client.on(events.CallbackQuery())
    async def callback_handler(event):
        if event.sender_id != ADMIN_USER_ID:
            return
        
        data = event.data.decode('utf-8')
        user_states.pop(event.sender_id, None) # Clear states on button press
        
        if data == "main_menu":
            status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
            await event.edit(f"⚙️ **ADMIN PANEL**\n\nStatus: {status}", buttons=main_menu_btns())
            
        elif data == "toggle_pause":
            set_paused(not is_paused())
            status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
            await event.answer(f"Status changed to {status}", alert=True)
            await event.edit(f"⚙️ **ADMIN PANEL**\n\nStatus: {status}", buttons=main_menu_btns())

        elif data == "menu_src":
            btns = [[Button.inline("➕ Add Source", b"add_src")], [Button.inline("⬅️ Back", b"main_menu")]]
            await event.edit("📡 **Source Channels**", buttons=btns)
            
        elif data == "add_src":
            user_states[event.sender_id] = "WAIT_ADD_SRC"
            await event.edit("Send the source channel username (e.g. @channel) or ID (e.g. -100...):", 
                             buttons=[[Button.inline("Cancel", b"menu_src")]])

        elif data == "menu_tgt":
            btns = [[Button.inline("➕ Add Target", b"add_tgt")], [Button.inline("⬅️ Back", b"main_menu")]]
            await event.edit("🎯 **Target Channels**", buttons=btns)

        elif data == "add_tgt":
            user_states[event.sender_id] = "WAIT_ADD_TGT"
            await event.edit("Send the target channel username (e.g. @channel) or ID (e.g. -100...):", 
                             buttons=[[Button.inline("Cancel", b"menu_tgt")]])
                             
        elif data == "menu_rtg":
            user_states[event.sender_id] = "WAIT_ADD_RTG"
            await event.edit("🔀 **Add Route**\nSend it exactly like this:\n`<source_id> -> <target_id>`\nExample: @source -> @target", 
                             buttons=[[Button.inline("Cancel", b"main_menu")]])

        elif data == "menu_flt":
            btns = [
                [Button.inline("➕ Add Word", b"flt_word"), Button.inline("➕ Add Link", b"flt_link")],
                [Button.inline("➕ Add Domain", b"flt_dom"), Button.inline("⬅️ Back", b"main_menu")]
            ]
            await event.edit("🚫 **Filters**", buttons=btns)
            
        elif data in ["flt_word", "flt_link", "flt_dom"]:
            user_states[event.sender_id] = f"WAIT_{data.upper()}"
            await event.edit("Send the item to blacklist:", buttons=[[Button.inline("Cancel", b"menu_flt")]])

        elif data == "menu_sts":
            conn = get_db()
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            stats = conn.execute("SELECT * FROM statistics WHERE date=?", (today,)).fetchone()
            conn.close()
            
            text = "📊 **Statistics (Today)**\n\n"
            if stats:
                text += f"📥 Processed: {stats['processed']}\n✅ Forwarded: {stats['forwarded']}\n🚫 Rejected: {stats['rejected']}\n❌ Errors: {stats['errors']}"
            else:
                text += "No activity today."
                
            await event.edit(text, buttons=[[Button.inline("⬅️ Back", b"main_menu")]])

        elif data == "menu_stat":
            conn = get_db()
            src_count = conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
            tgt_count = conn.execute("SELECT COUNT(*) FROM targets").fetchone()[0]
            conn.close()
            
            status = "🔴 PAUSED" if is_paused() else "🟢 ACTIVE"
            text = f"🔧 **System Status**\n\nTelegram: 🟢 Connected\nDatabase: 🟢 Connected\nForwarding: {status}\n\nSources: {src_count}\nTargets: {tgt_count}"
            await event.edit(text, buttons=[[Button.inline("⬅️ Back", b"main_menu")]])

    @client.on(events.NewMessage())
    async def state_input_handler(event):
        if event.sender_id != ADMIN_USER_ID or event.sender_id not in user_states:
            return
            
        state = user_states[event.sender_id]
        text = event.text.strip()
        
        try:
            if state == "WAIT_ADD_SRC":
                # Ensure bot has access
                entity = await client.get_entity(text)
                add_source(entity.id, text)
                await event.reply(f"✅ Source {text} added.", buttons=[[Button.inline("⬅️ Back", b"menu_src")]])
                
            elif state == "WAIT_ADD_TGT":
                entity = await client.get_entity(text)
                add_target(entity.id, text)
                await event.reply(f"✅ Target {text} added.", buttons=[[Button.inline("⬅️ Back", b"menu_tgt")]])
                
            elif state == "WAIT_ADD_RTG":
                if "->" not in text:
                    raise ValueError("Format must be: source -> target")
                src, tgt = [x.strip() for x in text.split("->")]
                add_route(src, tgt)
                await event.reply(f"✅ Route {src} -> {tgt} added.", buttons=[[Button.inline("⬅️ Back", b"main_menu")]])
                
            elif state.startswith("WAIT_FLT_"):
                f_type = state.split("_")[2].lower() # word, link, dom
                if f_type == 'dom': f_type = 'domain'
                add_filter(f_type, text)
                await event.reply(f"✅ {f_type.capitalize()} filter '{text}' added.", buttons=[[Button.inline("⬅️ Back", b"menu_flt")]])

        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}\n\nMake sure the format is correct and the bot is an admin in the channel.", buttons=[[Button.inline("⬅️ Back to Main", b"main_menu")]])
            
        finally:
            del user_states[event.sender_id]
