# SendGrid Email Setup Guide

Step-by-step instructions to configure SendGrid for Draftly review notifications.

## Prerequisites

- A SendGrid account (free tier: 100 emails/day)
- A domain you can add DNS records to (or a verified email address)
- The Draftly app running locally or deployed

---

## Step 1: Create a SendGrid Account

1. Go to [SendGrid](https://sendgrid.com/) and click **Start for Free**
2. Complete the signup process and verify your email

---

## Step 2: Create an API Key

1. In the SendGrid dashboard, go to **Settings** → **API Keys**
2. Click **Create API Key**
3. Name it (e.g., `Draftly`)
4. Select **Restricted Access** and grant:
   - **Mail Send** → Full Access
5. Click **Create & View**
6. Copy the key immediately — it starts with `SG.` and won't be shown again

---

## Step 3: Verify a Sender

SendGrid requires a verified sender before it will deliver emails.

### Option A: Single Sender Verification (Quick)

1. Go to **Settings** → **Sender Authentication**
2. Click **Verify a Single Sender**
3. Fill in the form:
   - From Email: `noreply@yourdomain.com` (or any email you control)
   - From Name: `Draftly`
   - Reply To: your personal email (optional)
4. Check your inbox for the verification email and click the link
5. Your sender is now verified

### Option B: Domain Authentication (Production)

1. Go to **Settings** → **Sender Authentication**
2. Click **Authenticate Your Domain** → select your DNS provider
3. Enter your domain (e.g., `yourdomain.com`)
4. SendGrid will give you DNS records to add:
   - **CNAME** records for SPF/DKIM signing
5. Add each record to your DNS provider
6. Return to SendGrid and click **Verify**
7. This can take up to 48 hours for DNS propagation

Domain authentication improves deliverability and reduces spam scoring.

---

## Step 4: Configure Environment Variables

Add to your `.env` file:

```env
SENDGRID_API_KEY=SG.your-api-key-here
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_FROM_NAME=Draftly
```

**Important:** `SENDGRID_FROM_EMAIL` must match a verified sender in SendGrid. If you used Single Sender Verification, use the exact email you verified.

Verify the config loads correctly:

```bash
python3 -c "
from src.config import settings
key = settings.sendgrid_api_key.get_secret_value()
print(f'API key set: {bool(key)}')
print(f'From email: {settings.sendgrid_from_email}')
print(f'From name: {settings.sendgrid_from_name}')
"
```

---

## Step 5: Set the App URL

Email review buttons POST to `{APP_URL}/api/review/{token}/action`. This must be publicly accessible.

```env
APP_URL=https://your-app-url.com
REVIEW_DASHBOARD_URL=https://your-app-url.com
```

For local development:

```env
APP_URL=http://localhost:8000
REVIEW_DASHBOARD_URL=http://localhost:5173
```

Note: Email buttons won't work locally unless you have a public URL (use ngrok):

```bash
ngrok http 8000
# Set APP_URL to the https ngrok URL
```

---

## Step 6: Set Up Reviewers

Each reviewer needs their email address and `notify_email` enabled.

### Getting a Reviewer's Email

The email comes from the reviewer's Clerk account (auto-filled during self-registration) or is set manually by an admin.

### Option A: Self-Registration (Reviewer)

In the Draftly frontend:

1. Navigate to **Reviewers** page
2. Click **Self Register**
3. Your email is pre-filled from your Clerk account
4. Toggle **Notify via Email** on
5. Submit

### Option B: Admin Creates Reviewer

```bash
curl -X POST http://localhost:8000/api/reviewers \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "notify_email": true
  }'
```

### Option C: Update Existing Reviewer

```bash
curl -X PUT http://localhost:8000/api/reviewers/<reviewer-id> \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "notify_email": true
  }'
```

---

## Step 7: Test the Integration

1. Ensure the server is running:

   ```bash
   uv run uvicorn src.api.app:app --reload
   ```

2. Run the pipeline with a test question:

   ```bash
   uv run python -m src.cli.draftly "How do I configure SSO?" --org-id <your-org-id>
   ```

3. Check the reviewer's inbox — they should receive an HTML email with:
   - Blue header: "Documentation Review Required"
   - Document title, source, and confidence score
   - Original question in a blockquote
   - Three colored buttons:
     - **Approve** (green) → `POST /api/review/{token}/action` with `action=approve`
     - **Reject** (red) → `POST /api/review/{token}/action` with `action=reject`
     - **Request Changes** (yellow) → `POST /api/review/{token}/action` with `action=revise`
   - "Review in dashboard" fallback link
   - Expiry notice: "Link expires in 24 hours"

4. Click a button — it opens a new tab and submits the form. The review is processed and the LangGraph pipeline resumes.

---

## How It Works (Technical)

The notification flow:

```
Pipeline reaches human_review_node
  → notify_reviewers() iterates active reviewers
  → For email-enabled reviewers:
    1. Generate HMAC review token (security/tokens.py, 24h expiry)
    2. Build HTML email from template (integrations/email.py)
    3. Send via SendGrid API (POST /v3/mail/send)
  → Reviewer receives email with form buttons
  → Button click POSTs to /api/review/{token}/action
  → verify_review_token() validates HMAC + expiry
  → complete_review() updates review_sessions table
  → resume_review() resumes LangGraph pipeline
```

---

## Troubleshooting

### Emails not arriving

- Verify `SENDGRID_API_KEY` is set and starts with `SG.`
- Check the sender email matches a verified sender exactly
- Go to SendGrid **Activity** dashboard to see delivery status
- Check server logs for `sendgrid_send_failed` errors

### Emails going to spam

- Complete domain authentication in SendGrid (Step 3, Option B)
- Add SPF, DKIM, and DMARC DNS records as SendGrid instructs
- Use a domain-based sender (`noreply@yourdomain.com`), not Gmail/Yahoo
- Avoid spam trigger words in the subject line

### Email buttons return "Invalid or expired token"

- HMAC tokens expire after 24 hours — this is expected behavior
- Reviewers must act within the 24-hour window
- The dashboard link (`REVIEW_DASHBOARD_URL/review/{review_id}`) always works regardless of token expiry

### Email buttons open but nothing happens

- `APP_URL` must be publicly accessible for form POSTs to work
- For local development, use ngrok to expose your local server
- Verify `/api/review/{token}/action` is reachable by visiting it in a browser
- Check that the token hasn't expired

### SendGrid returns 403

- Your API key may not have **Mail Send** permission
- Create a new API key with full Mail Send access

### SendGrid returns 401

- Your API key is invalid or revoked
- Generate a new API key in SendGrid dashboard

### `sendgrid_not_configured` warning in logs

- `SENDGRID_API_KEY` is empty or not set
- Add it to your `.env` file and restart the server

---

## Email Template

The HTML email template is defined in `src/integrations/email.py:11-68`. It includes:

| Element        | Description                                      |
| -------------- | ------------------------------------------------ |
| Header         | Blue banner with "Documentation Review Required" |
| Title          | Document title (h2)                              |
| Source         | Original platform (Slack, Discord, GitHub, CLI)  |
| Confidence     | Confidence score as percentage (large, bold)     |
| Question       | Original user question in a blockquote           |
| Approve button | Green `#28a745` — POSTs `action=approve`         |
| Reject button  | Red `#dc3545` — POSTs `action=reject`            |
| Revise button  | Yellow `#ffc107` — POSTs `action=revise`         |
| Dashboard link | Fallback link to full review UI                  |
| Footer         | "Link expires in 24 hours" notice                |

To customize the template, edit `REVIEW_NOTIFICATION_TEMPLATE` in `src/integrations/email.py`.

---

## Configuration Reference

| Variable               | Required | Default                 | Description                          |
| ---------------------- | -------- | ----------------------- | ------------------------------------ |
| `SENDGRID_API_KEY`     | Yes      | `""`                    | SendGrid API key (starts with `SG.`) |
| `SENDGRID_FROM_EMAIL`  | Yes      | `noreply@draftly.app`   | Verified sender email                |
| `SENDGRID_FROM_NAME`   | No       | `Draftly`               | Sender display name                  |
| `APP_URL`              | Yes      | `http://localhost:5173` | Base URL for email button POST URLs  |
| `REVIEW_DASHBOARD_URL` | No       | `http://localhost:5173` | Fallback link in email body          |

---

## Setup Checklist

- [ ] SendGrid account created
- [ ] API key created with Mail Send access
- [ ] Sender email verified (single sender or domain auth)
- [ ] `SENDGRID_API_KEY` set in `.env`
- [ ] `SENDGRID_FROM_EMAIL` set in `.env` (matches verified sender)
- [ ] `APP_URL` set to a publicly accessible URL
- [ ] At least one reviewer with `email` and `notify_email=true`
- [ ] Test email received in reviewer inbox
- [ ] Email buttons successfully process review action
