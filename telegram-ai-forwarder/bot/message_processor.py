import datetime
import asyncio
import random
import re
import urllib.request
from telethon import events
from telethon.tl.types import MessageMediaWebPage
from bot.database import get_db, is_paused

AFFILIATE_TAG = "Uehd-21"

def check_blacklist(text, conn):
    if not text: return False, None
    text_lower = str(text).lower()
    try:
        filters = conn.execute("SELECT * FROM filters").fetchall()
        for f in filters:
            for val in tuple(f):
                clean_val = str(val).lower().strip()
                if clean_val in ['word', 'link', 'domain', 'none', ''] or clean_val.isdigit():
                    continue
                if clean_val in text_lower:
                    return True, clean_val
    except Exception as e:
        print(f"⚠️ Filter read error: {e}")
    return False, None

def fetch_real_url(url):
    """Natively follows redirects to bypass double-shorteners without API limits"""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.geturl()
    except Exception as e:
        print(f"⚠️ URL Resolve Error: {e}")
        return url

async def resolve_amazon_url(url):
    return await asyncio.to_thread(fetch_real_url, url)

def format_money(num):
    return f"{int(num):,}"

def format_single_deal(raw_block, final_link):
    mrp = 0
    deal_price = 0
    
    # Extract prices
    currency_regex = r'(?:₹|rs\.?|@)[\s]*([0-9,]+)'
    matches = re.findall(currency_regex, raw_block, re.IGNORECASE)
    amounts = []
    for m in matches:
        try:
            amounts.append(float(m.replace(',', '')))
        except:
            pass
            
    if len(amounts) >= 2:
        amounts.sort(reverse=True)
        mrp = amounts[0]
        deal_price = amounts[-1]
    elif len(amounts) == 1:
        deal_price = amounts[0]
        
    # Extract Coupon
    coupon_text = ""
    coupon_regex = r'(?:apply|extra|get|use)\s*(?:₹|rs\.?)?\s*\d+\s*(?:%|rs\.?)?\s*(?:off|discount)|(?:apply|extra|get|use)?\s*(?:₹|rs\.?)?\s*\d+\s*(?:%|rs\.?)?\s*coupon|bank\s+offers?'
    coupon_match = re.search(coupon_regex, raw_block, re.IGNORECASE)
    if coupon_match:
        coupon_text = coupon_match.group(0).strip().title()

    if deal_price > 0 and final_link:
        clean_text = re.sub(r'https?://[^\s]+', '', raw_block, flags=re.IGNORECASE)
        if coupon_match:
            clean_text = clean_text.replace(coupon_match.group(0), '')
            
        clean_text = re.sub(r'\b\d+\s*%\s*off\b[\s:\-]*', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'(?:for|at)\s*(?:₹|rs\.?|@)\s*[0-9,.]+', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'(?:₹|rs\.?|@)\s*[0-9,.]+', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'\b(for|at|only|now)\b', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'#[^\s]+', '', clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r'^[.\s\-\:]+|[.\s\-\:]+$', '', clean_text)
        
        lines = [line.strip() for line in clean_text.split('\n') if line.strip()]
        product_name = "Unknown Product"
        
        for line in lines:
            trimmed = re.sub(r'[.:\-,]+$', '', line).strip()
            if len(trimmed) > 3:
                with_match = re.search(r'^(.*?)\s+with\s+', trimmed, re.IGNORECASE)
                if with_match and len(with_match.group(1)) > 15:
                    product_name = with_match.group(1)
                elif len(trimmed) > 60:
                    product_name = trimmed[:60].strip() + "..."
                else:
                    product_name = trimmed
                break

        response = f"🛍 **Product**\n{product_name}\n\n"
        
        if mrp > deal_price:
            savings = mrp - deal_price
            discount = round(((mrp - deal_price) / mrp) * 100)
            response += f"💰 **MRP:** ~~₹{format_money(mrp)}~~\n"
            response += f"🔥 **Deal Price: ₹{format_money(deal_price)}**\n"
            response += f"💸 **Save:** ₹{format_money(savings)}\n"
            response += f"🏷 **Discount:** {discount}% OFF\n\n"
        else:
            response += f"💰 **Deal Price: ₹{format_money(deal_price)}**\n\n"
            
        if coupon_text:
            response += f"🎟 **Coupon**\n{coupon_text}\n\n"
            
        response += f"🛒 **Buy Now 👇**\n{final_link}"
        return response
        
    elif final_link:
        return f"🛒 **Buy Now 👇**\n{final_link}"
        
    return ""


async def process_new_message(client, message):
    print("\n--- 🟢 NEW MESSAGE DETECTED ---")
    if is_paused(): return

    chat = await message.get_chat()
    if not chat: return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)
    conn = get_db()
    
    try:
        # ==========================================
        # 1. VERIFY SOURCE & FIND ROUTE
        # ==========================================
        matched_source_name = None
        for s in conn.execute("SELECT * FROM sources").fetchall():
            s_tup = tuple(s)
            s_id, s_name = str(s_tup[0]), str(s_tup[1]) if len(s_tup) > 1 else str(s_tup[0])
            clean_s_name = s_name.replace('@', '').lower()
            if str(chat_id) in [s_id, f"-100{s_id}"] or (chat_username and clean_s_name == chat_username.lower()):
                matched_source_name = s_name
                break
                
        if not matched_source_name: return

        target_names = [str(tuple(r)[1]) for r in conn.execute("SELECT * FROM routes").fetchall() if str(tuple(r)[0]).lower() == matched_source_name.lower()]
        if not target_names: return

        original_text = message.text or message.caption or getattr(message, 'message', '') or ""
        original_text_lower = original_text.lower()

        # ==========================================
        # 2. AMAZON WHITELIST & PRE-BLACKLIST
        # ==========================================
        if "amazon" not in original_text_lower and "amzn" not in original_text_lower: return
        
        is_blocked, blocked_word = check_blacklist(original_text, conn)
        if is_blocked:
            print(f"🚫 MESSAGE BLOCKED: Contains '{blocked_word}'")
            return

        # ==========================================
        # 3. THE NATIVE LINK SWAPPER (Option B)
        # ==========================================
        print("🚀 Processing native link conversion...")
        
        url_pattern = r'https?://(?:amzn\.[a-z\.]+|amazon\.[a-z\.]+|amzn-to\.co|amz\.in|a\.co|link\.amazon)/[^\s]+'
        
        lines = original_text.split('\n')
        current_block = ""
        final_output = "━━━━━━━━━━━━━━━\n\n"
        found_deals = 0
        
        for line in lines:
            current_block += line + "\n"
            urls_in_line = re.findall(url_pattern, line, re.IGNORECASE)
            
            if urls_in_line:
                primary_short_url = urls_in_line[0]
                real_url = await resolve_amazon_url(primary_short_url)
                
                asin_match = re.search(r'(?:/dp/|/gp/product/|/ASIN/|/d/|%2Fdp%2F|%2Fgp%2Fproduct%2F)([A-Z0-9]{10})', real_url, re.IGNORECASE)
                final_link = real_url
                
                if asin_match:
                    asin = asin_match.group(1).upper()
                    domain_match = re.search(r'amazon\.[a-z\.]+', real_url, re.IGNORECASE)
                    domain = domain_match.group(0).lower() if domain_match else "amazon.in"
                    final_link = f"https://www.{domain}/dp/{asin}?tag={AFFILIATE_TAG}"
                
                formatted_deal = format_single_deal(current_block, final_link)
                if formatted_deal:
                    final_output += formatted_deal + "\n\n━━━━━━━━━━━━━━━\n\n"
                    found_deals += 1
                current_block = ""
        
        final_output = final_output.strip()

        if found_deals == 0:
            print("❌ Could not detect valid product details or ASINs.")
            return

        # ==========================================
        # 4. POST-BLACKLIST CHECK
        # ==========================================
        is_blocked, blocked_word = check_blacklist(final_output, conn)
        if is_blocked:
            print(f"🚫 BLOCKED POST-CONVERSION: Contains '{blocked_word}'")
            return

        # ==========================================
        # 5. THE HUMAN DELAY (Anti-Ban)
        # ==========================================
        delay = random.randint(2, 5)
        print(f"⏱️ HUMAN DELAY: Waiting {delay} seconds before posting to avoid Telegram spam filters...")
        await asyncio.sleep(delay)

        # ==========================================
        # 6. SEND TO TARGET(S)
        # ==========================================
        for t_name in target_names:
            try:
                print(f"➡️ Forwarding to Target: {t_name}")
                if message.media and not isinstance(message.media, MessageMediaWebPage):
                    await client.send_file(t_name, message.media, caption=final_output)
                else:
                    await client.send_message(t_name, final_output)
                print(f"🎉 SUCCESS! Message posted.")
                
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                conn.execute("INSERT OR IGNORE INTO statistics (date, processed, forwarded, rejected, errors) VALUES (?, 0, 0, 0, 0)", (today,))
                conn.execute("UPDATE statistics SET processed = processed + 1, forwarded = forwarded + 1 WHERE date=?", (today,))
                conn.commit()
            except Exception as e:
                print(f"❌ Failed to post in Target: {e}")

    finally:
        print("--- 🏁 PROCESS FINISHED ---\n")
        conn.close()
