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
    """Uses API unshortener first to bypass Amazon bot blocks, then follows native redirects."""
    try:
        api_url = f"https://unshorten.me/s/{url}"
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            resolved = response.read().decode('utf-8').strip()
            if resolved.startswith('http') and resolved != url:
                url = resolved
    except:
        pass
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.geturl()
    except:
        return url

async def resolve_amazon_url(url):
    return await asyncio.to_thread(fetch_real_url, url)

def format_money(num):
    return f"{int(num):,}"

def format_single_deal(raw_block, final_link):
    mrp = 0
    deal_price = 0
    
    # 1. Extract prices (First pass: standard currency symbols)
    currency_regex = r'(?:₹|rs\.?|@)[\s]*([0-9,]+)'
    matches = re.findall(currency_regex, raw_block, re.IGNORECASE)
    
    # THE FIX: Fallback Scanner for lazy formatting (e.g. "https://amzn.to/... 202" or "202 https://amzn.to/...")
    if not matches:
        # Fallback 1: Number immediately AFTER the link
        matches += re.findall(r'https?://[^\s]+\s+([0-9,]{2,})', raw_block, re.IGNORECASE)
        if not matches:
            # Fallback 2: Number immediately BEFORE the link
            matches += re.findall(r'\b([0-9,]{2,})\s+https?://', raw_block, re.IGNORECASE)
        if not matches:
            # Fallback 3: Floating number at the very end of the message
            matches += re.findall(r'\b([0-9,]{2,})\s*$', raw_block)
            
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

    # 2. Extract Offers line by line
    offers_text = ""
    product_name = "🛍 Deal of the Day"
    
    text_without_link = re.sub(r'https?://[^\s]+', '', raw_block)
    raw_lines = [line.strip() for line in text_without_link.split('\n') if line.strip()]
    
    title_candidates = []
    
    for index, line in enumerate(raw_lines):
        line_lower = line.lower()
        if index == 0:
            title_candidates.append(line)
            continue
            
        if re.search(r'(coupon|credit card|debit card|bank|axis|hdfc|sbi|icici|apply\s+.*?off|extra\s+.*?off)', line_lower):
            offers_text += f"🎁 **Offer:** {line}\n"
        else:
            title_candidates.append(line)
            
    # 3. Clean up the product title
    if title_candidates:
        raw_title = title_candidates[0]
        clean_title = re.sub(r'\b(?:for|at|only|now)\b\s*(?:₹|rs\.?|@)?\s*[0-9,.]+', '', raw_title, flags=re.IGNORECASE)
        clean_title = re.sub(r'(?:₹|rs\.?|@)\s*[0-9,.]+', '', clean_title, flags=re.IGNORECASE)
        
        # If we used the Fallback Scanner, remove that stray number from the title so it looks clean!
        if deal_price > 0:
            deal_str = str(int(deal_price))
            clean_title = re.sub(rf'\b{deal_str}\b\s*$', '', clean_title).strip()
            clean_title = re.sub(rf'^\s*\b{deal_str}\b', '', clean_title).strip()
            
        clean_title = re.sub(r'^[.\s\-\:,]+|[.\s\-\:,]+$', '', clean_title) 
        clean_title = re.sub(r'#[^\s]+', '', clean_title, flags=re.IGNORECASE).strip()
        
        if len(clean_title) > 3:
            product_name = clean_title

    # 4. Build final response
    response = f"🛍 **Product**\n{product_name}\n\n"
    
    if deal_price > 0:
        if mrp > deal_price:
            savings = mrp - deal_price
            discount = round(((mrp - deal_price) / mrp) * 100)
            response += f"💰 **MRP:** ~~₹{format_money(mrp)}~~\n"
            response += f"🔥 **Deal Price: ₹{format_money(deal_price)}**\n"
            response += f"💸 **Save:** ₹{format_money(savings)}\n"
            response += f"🏷 **Discount:** {discount}% OFF\n\n"
        else:
            response += f"💰 **Deal Price: ₹{format_money(deal_price)}**\n\n"
    
    if offers_text:
        response += f"{offers_text}\n"
        
    response += f"🛒 **Buy Now 👇**\n{final_link}"
    return response


async def process_new_message(client, message):
    print("\n--- 🟢 NEW MESSAGE DETECTED ---")
    if is_paused(): return

    chat = await message.get_chat()
    if not chat: return
        
    chat_id = getattr(chat, 'id', None)
    chat_username = getattr(chat, 'username', None)
    conn = get_db()
    
    try:
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

        if "amazon" not in original_text_lower and "amzn" not in original_text_lower: return
        
        is_blocked, blocked_word = check_blacklist(original_text, conn)
        if is_blocked:
            print(f"🚫 MESSAGE BLOCKED: Contains '{blocked_word}'")
            return

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
                primary_short_url = urls_in_line[0].rstrip('.,;:"\'()')
                real_url = await resolve_amazon_url(primary_short_url)
                
                asin_match = re.search(r'(?:/dp/|/gp/product/|/ASIN/|/d/|%2Fdp%2F|%2Fgp%2Fproduct%2F)([A-Z0-9]{10})', real_url, re.IGNORECASE)
                
                if asin_match:
                    asin = asin_match.group(1).upper()
                    domain_match = re.search(r'amazon\.[a-z\.]+', real_url, re.IGNORECASE)
                    domain = domain_match.group(0).lower() if domain_match else "amazon.in"
                    final_link = f"https://www.{domain}/dp/{asin}?tag={AFFILIATE_TAG}"
                else:
                    if re.search(r'amazon\.', real_url, re.IGNORECASE):
                        parts = real_url.split('#', 1)
                        base_url = parts[0]
                        hash_part = f"#{parts[1]}" if len(parts) > 1 else ""
                        clean_url = re.sub(r'([?&])tag=[^&]+', r'\1', base_url)
                        clean_url = clean_url.replace('&&', '&').replace('?&', '?').rstrip('?&')
                        if '?' in clean_url:
                            final_link = f"{clean_url}&tag={AFFILIATE_TAG}{hash_part}"
                        else:
                            final_link = f"{clean_url}?tag={AFFILIATE_TAG}{hash_part}"
                    else:
                        final_link = real_url
                
                formatted_deal = format_single_deal(current_block, final_link)
                if formatted_deal:
                    final_output += formatted_deal + "\n\n━━━━━━━━━━━━━━━\n\n"
                    found_deals += 1
                current_block = ""
        
        final_output = final_output.strip()

        if found_deals == 0:
            print("❌ Could not detect valid product details or ASINs.")
            return

        is_blocked, blocked_word = check_blacklist(final_output, conn)
        if is_blocked:
            print(f"🚫 BLOCKED POST-CONVERSION: Contains '{blocked_word}'")
            return

        delay = random.randint(2, 5)
        print(f"⏱️ HUMAN DELAY: Waiting {delay} seconds before posting...")
        await asyncio.sleep(delay)

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
