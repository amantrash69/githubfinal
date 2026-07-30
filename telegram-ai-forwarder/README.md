# Telegram AI Deal Rewriter & Forwarder

A standalone Render-ready service that watches public Telegram channels through an authorized **Telegram user session**, sends each complete post to your existing Telegram link-converter bot, then publishes that bot's complete reply to your channel. It never prompts for credentials in production.

## Architecture

`Source channel(s) -> Telethon user client -> existing converter bot -> target channel`

Posts with a photo, video, document, or caption reuse the original Telegram media reference with the rewritten caption. If that fails, the service sends the generated text. SQLite persists source channel, source message ID, processing status, target message ID, timestamps, and concise failure information.

## Included first release

- Multiple sources via `SOURCE_CHANNELS`
- Sends the full source caption/text to your existing converter bot, which handles Amazon-link replacement and formatting
- Duplicate protection that survives restarts
- One-at-a-time converter conversations so replies are matched to the correct source post
- Media preservation and safe text-only fallback
- `GET /` Render health endpoint

The first release deliberately does **not** include an admin Bot API layer: the automatic Telegram → GPT → Telegram pipeline is complete first.

## Local setup

1. Use Python 3.11+ and create a virtual environment.
2. Install: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and supply values.
4. Generate a session once: `python scripts/create_session.py`
5. Copy its `SESSION_STRING=` value into `.env`.
6. Start: `python main.py`
7. Open `http://localhost:10000/`, then publish a **new** source-channel post.

The session's Telegram account must belong to every source channel and have permission to post in `TARGET_CHANNEL`. Public `@usernames`, numeric IDs, and private `https://t.me/+...` invite links are supported. On the first run, a private invite link lets the session account join that chat; it still must be promoted to an administrator with posting permission in the target channel.

## Telegram session generation

Create `API_ID` and `API_HASH` at [my.telegram.org](https://my.telegram.org). On your trusted computer, put those values in `.env` and run `python scripts/create_session.py`. Telegram prompts for phone number, code, and optional 2FA **only for this one-time local step**. Store the output as Render's `SESSION_STRING` secret. It grants access to that account; do not commit or share it.

## Converter bot setup

Set `CONVERTER_BOT_USERNAME` to the public username of your existing bot (for example, `@my_amazon_converter_bot`). This is **not** its Bot API token. Before deploying, use the Telegram account behind `SESSION_STRING` to open a private chat with that bot and press **Start** once. The converter bot must accept a complete text/caption and reply with one complete final message. The forwarder keeps the original source media and uses that reply as its caption or text.

## Render deployment

Push this folder as a separate GitHub repository and create a Render **Web Service**.

- Build command: `pip install -r requirements.txt`
- Start command: `python main.py`
- Health check: `/`

Set all `.env.example` values in Render's Environment page. Attach a persistent disk and set `DATABASE_PATH=/var/data/forwarder.db`; an ephemeral filesystem would lose duplicate history after restarts. `render.yaml` provides the same blueprint values.

## Testing checklist

1. Start with a private test target channel where the session account is an admin.
2. Post text with an Amazon URL; verify one rewritten output.
3. Restart and confirm the same source post is not reposted.
4. Post a photo/video/document with caption; confirm media and generated caption appear.
5. Send a complete test post to the converter bot manually and verify it returns one complete final message; then test through the source channel.

Failed posts are recorded as `failed` rather than endlessly retried. After correcting configuration, intentionally retry by publishing a new source post (or carefully remove only that source row from SQLite).
