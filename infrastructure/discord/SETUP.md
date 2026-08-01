# Discord Bot Setup Guide

Step-by-step instructions to create and configure a Discord bot for Draftly — both **pipeline triggering** (messages → docs) and **review notifications** (approve/reject buttons).

## Prerequisites

- A Discord account
- A Discord server where you have **Manage Server** permissions
- The Draftly app running locally or deployed

---

## Step 1: Create a Discord Application

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** in the top-right
3. Enter a name (e.g., `Draftly`) and click **Create**
4. On the **General Information** page, copy the **Application ID**

---

## Step 2: Create the Bot

1. In the left sidebar, click **Bot**
2. Click **Add Bot** → confirm with **Yes, do it!**
3. Under the bot's username, click **Reset Token** to generate a new token
4. Copy the token immediately — you won't be able to see it again

### Enable Privileged Gateway Intents

Under **Privileged Gateway Intents**, enable:

- ✅ **MESSAGE CONTENT INTENT** — required to read messages and trigger the pipeline
- ❌ PRESENCE INTENT — off
- ❌ SERVER MEMBERS INTENT — off

---

## Step 3: Get the Public Key

1. In the left sidebar, click **General Information**
2. Copy the **Public Key** value
3. This is used for Ed25519 interaction signature verification (review buttons)

---

## Step 4: Configure Environment Variables

Add to your `.env` file:

```env
# Required for all Discord features
DISCORD_BOT_TOKEN=your-bot-token-here
DISCORD_PUBLIC_KEY=your-public-key-here
DISCORD_APP_ID=your-application-id-here

# Optional: default guild (Settings page linking overrides this)
DISCORD_GUILD_ID=your-guild-id-here
```

Verify they load correctly:

```bash
python3 -c "
from src.config import settings
print('Bot token set:', bool(settings.discord_bot_token.get_secret_value()))
print('Public key set:', bool(settings.discord_public_key.get_secret_value()))
print('App ID set:', bool(settings.discord_app_id))
"
```

---

## Step 5: Run the Database Migration

Apply the `discord_workflows` table:

```bash
uv run python scripts/init_db.py
```

Or manually:

```bash
psql $COCKROACHDB_URL < infrastructure/cockroachdb/migrations/011_add_discord_workflows.sql
```

---

## Step 6: Invite the Bot to Your Server

### Option A: Via Settings Page (Recommended)

1. Start the Draftly server: `uv run uvicorn src.api.app:app --reload`
2. Go to **Settings** → **Discord Integration**
3. Click **Add to Discord Server** — opens the invite URL
4. Select your server → **Authorize**

### Option B: Manual Invite URL

Build the URL with your Application ID:

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_APP_ID&permissions=34816&scope=bot
```

Permissions encoded in `34816`:

- Send Messages (2048)
- Send Messages in Threads (32768)

Open the URL → select your server → **Authorize**

---

## Step 7: Link Your Server to Draftly

### Via Settings Page

1. Go to **Settings** → **Discord Integration**
2. In Discord: right-click your server name → **Copy Server ID**
   - (Enable Developer Mode first: User Settings → Advanced → Developer Mode)
3. Paste the Guild ID into the **Server (Guild) ID** field
4. Click **Connect**

### Verify Connection

The Settings page should show:

```
Guild: 123456789012345678    [Connected]
```

---

## Step 8: Start the Server

The Discord Gateway WebSocket connects automatically on startup when `DISCORD_BOT_TOKEN` is set:

```bash
uv run uvicorn src.api.app:app --reload
```

Look for these log lines:

```
discord_gateway_starting
discord_gateway_connected
discord_gateway_identified
discord_gateway_ready session_id=...
```

No separate process needed — the Gateway runs inside the FastAPI lifespan.

---

## Step 9: Test Pipeline Triggering

1. In Discord, go to any channel the bot can see
2. Type a support question (e.g., "How do I reset my password?")
3. The bot should:
   - React with 👀 to acknowledge
   - Start the documentation pipeline
   - Reply with the draft in the thread (or channel)

---

## Step 10: Set Up Review Notifications

Each reviewer needs their Discord user ID stored in Draftly.

### Getting a Discord User ID

1. In Discord, go to **User Settings** → **Advanced** → enable **Developer Mode**
2. Right-click any user → **Copy User ID**

### Option A: Self-Registration (Reviewer)

In the Draftly frontend:

1. Navigate to **Reviewers** page
2. Click **Self Register**
3. Enter your Discord user ID
4. Toggle **Notify via Discord** on
5. Submit

### Option B: Admin Creates Reviewer

```bash
curl -X POST http://localhost:8000/api/reviewers \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "discord_user_id": "123456789012345678",
    "notify_discord": true
  }'
```

---

## Step 11: Test Review Notifications

1. Run the pipeline:

   ```bash
   uv run python -m src.cli.draftly "How do I configure SSO?" --org-id <your-org-id>
   ```

2. Check the reviewer's Discord DMs — they should receive an interactive card with:
   - Document title, source, and confidence score
   - Draft preview in a code block
   - **Approve**, **Reject**, and **Revise** buttons
   - Quick feedback dropdown

3. Click a button — the message should update to show the result

---

## Interactions Endpoint URL (for Review Buttons)

For button clicks to work in production, Discord needs to know where to send interactions:

1. In the Developer Portal, go to **General Information**
2. Under **Interactions Endpoint URL**, enter:
   ```
   https://your-app-url.com/api/discord/interactions
   ```
3. Discord will send a PING to verify — the endpoint must be live
4. For local development, use ngrok:
   ```bash
   ngrok http 8000
   ```
   Then set the ngrok URL (e.g., `https://abc123.ngrok.io/api/discord/interactions`)

---

## Environment Variables Reference

| Variable             | Required | Purpose                                      |
| -------------------- | -------- | -------------------------------------------- |
| `DISCORD_BOT_TOKEN`  | Yes      | Bot authentication for Gateway + REST API    |
| `DISCORD_PUBLIC_KEY` | Yes      | Ed25519 verification for interaction buttons |
| `DISCORD_APP_ID`     | Yes      | Application ID for invite URL generation     |
| `DISCORD_GUILD_ID`   | No       | Default guild (Settings linking overrides)   |

---

## Bot Permissions Summary

| Permission               | Required | Purpose                            |
| ------------------------ | -------- | ---------------------------------- |
| Send Messages            | Yes      | Send pipeline replies + review DMs |
| Send Messages in Threads | Yes      | Reply to originating threads       |
| Use Slash Commands       | No       | Reserved for future use            |
| Read Message History     | No       | Not needed (Gateway receives live) |
| Manage Messages          | No       | Not needed                         |

---

## Troubleshooting

### Bot doesn't react or respond to messages

- Verify `DISCORD_BOT_TOKEN` is set correctly in `.env`
- Verify **MESSAGE CONTENT INTENT** is enabled in Developer Portal
- Ensure the bot is in the server (check member list)
- Check bot permissions include **Send Messages**
- Look for `discord_gateway_ready` in server logs
- If not connecting, check `DISCORD_BOT_TOKEN` is valid (Bot → Reset Token)

### "Draftly is not linked" error

- The server's Guild ID isn't linked to a Draftly org
- Go to **Settings** → **Discord Integration** → paste Guild ID → **Connect**

### Gateway keeps reconnecting

- Token may be invalid — reset it in Developer Portal
- Check network connectivity to `wss://gateway.discord.gg`
- Verify `discord.py` is installed: `uv pip show discord.py`

### Button clicks don't work

- Verify `DISCORD_PUBLIC_KEY` is set correctly
- Ensure the interactions endpoint is reachable (use ngrok for local dev)
- Check that the Interactions Endpoint URL is configured in Developer Portal

### Token expired errors

- HMAC review tokens expire after 24 hours
- This is expected — reviewers must act within the window
- The dashboard link always works regardless of token expiry

---

## Server Setup Checklist

- [ ] Discord application created
- [ ] Bot created with token copied
- [ ] **MESSAGE CONTENT INTENT** enabled
- [ ] Application ID copied
- [ ] Public key copied
- [ ] `DISCORD_BOT_TOKEN` set in `.env`
- [ ] `DISCORD_PUBLIC_KEY` set in `.env`
- [ ] `DISCORD_APP_ID` set in `.env`
- [ ] Database migration applied (`011_add_discord_workflows.sql`)
- [ ] Bot invited to Discord server with correct permissions
- [ ] Server linked to Draftly org via Settings page
- [ ] Gateway connected (check logs for `discord_gateway_ready`)
- [ ] Test message triggers pipeline
- [ ] Interactions endpoint URL configured (for button functionality)
- [ ] At least one reviewer with `discord_user_id` and `notify_discord=true`
- [ ] Test review notification received in Discord DM
