from __future__ import annotations

from collections.abc import Mapping
from string import Template
from typing import Any

import structlog

from src.config import settings

logger = structlog.get_logger()

REVIEW_NOTIFICATION_TEMPLATE = Template("""\
<!DOCTYPE html>
<html>
<head>
    <style>
        .container { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }
        .header { background: #4A90D9; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .confidence { font-size: 24px; font-weight: bold; }
        .actions { margin: 20px 0; }
        .btn {
            display: inline-block; padding: 10px 20px;
            margin: 5px; text-decoration: none; border-radius: 5px;
        }
        .btn-approve { background: #28a745; color: white; }
        .btn-reject { background: #dc3545; color: white; }
        .btn-revise { background: #ffc107; color: black; }
        .footer { color: #666; font-size: 12px; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Documentation Review Required</h1>
        </div>
        <div class="content">
            <h2>${title}</h2>
            <p><strong>Source:</strong> ${source}</p>
            <p><strong>Confidence:</strong> <span class="confidence">${confidence}%</span></p>
            <p><strong>Original Question:</strong></p>
            <blockquote>${question}</blockquote>
            <div class="actions">
                <form method="POST" action="${app_url}/api/review/${token}/action" target="_blank">
                    <input type="hidden" name="action" value="approve">
                    <button type="submit" class="btn btn-approve">Approve</button>
                </form>
                <form method="POST" action="${app_url}/api/review/${token}/action" target="_blank">
                    <input type="hidden" name="action" value="reject">
                    <button type="submit" class="btn btn-reject">Reject</button>
                </form>
                <form method="POST" action="${app_url}/api/review/${token}/action" target="_blank">
                    <input type="hidden" name="action" value="revise">
                    <button type="submit" class="btn btn-revise">Request Changes</button>
                </form>
            </div>
            <p>
                Or <a href="${dashboard_url}/review/${review_id}">
                    review in dashboard
                </a> for detailed editing.
            </p>
        </div>
        <div class="footer">
            <p>This review was requested by Draftly AI. Link expires in 24 hours.</p>
        </div>
    </div>
</body>
</html>
""")


async def send_email(to: str, subject: str, html_content: str) -> dict:
    """Send email via SendGrid API."""
    import httpx

    api_key = settings.sendgrid_api_key.get_secret_value()
    if not api_key:
        logger.warning("sendgrid_not_configured")
        return {"ok": False, "status": "skipped", "reason": "no_api_key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {
            "email": settings.sendgrid_from_email,
            "name": settings.sendgrid_from_name,
        },
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code not in (200, 201, 202):
            logger.error("sendgrid_send_failed", status=resp.status_code, body=resp.text)
            return {"ok": False, "status": "failed", "error": resp.text}
        return {"ok": True, "status": "sent"}


async def send_review_notification(
    to: str,
    reviewer_name: str,
    state: Mapping[str, Any],
    review_id: str,
    token: str,
) -> dict:
    """Send review notification email to a reviewer."""
    title = state.get("draft_title", "Untitled")
    confidence = state.get("confidence_score", 0)
    source = state.get("source_type", "unknown")
    question = state["question"]

    html_content = REVIEW_NOTIFICATION_TEMPLATE.substitute(
        title=title,
        source=source,
        confidence=f"{confidence:.0%}",
        question=question,
        app_url=settings.app_url,
        dashboard_url=settings.review_dashboard_url,
        review_id=review_id,
        token=token,
    )

    subject = f"Review Required: {title}"
    return await send_email(to, subject, html_content)


IMPROVEMENT_NOTIFICATION_TEMPLATE = Template("""\
<!DOCTYPE html>
<html>
<head>
    <style>
        .container { font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }
        .header { background: #4A90D9; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; }
        .proposal { border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; }
        .btn {
            display: inline-block; padding: 10px 20px; margin: 5px;
            text-decoration: none; border-radius: 5px;
        }
        .btn-approve { background: #28a745; color: white; }
        .btn-reject { background: #dc3545; color: white; }
        .footer { color: #666; font-size: 12px; text-align: center; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Draftly Improvement Suggestions</h1>
        </div>
        <div class="content">
            <p>${summary}</p>
            <p><strong>${proposal_count}</strong> improvement suggestions found:</p>
            <ul>
                <li>${prompt_count} prompt rewrites</li>
                <li>${rubric_count} rubric updates</li>
                <li>${tool_count} tool suggestions</li>
            </ul>
            ${proposals_html}
            <p>
                <a href="${dashboard_url}/improvements" class="btn btn-approve">
                    View All in Dashboard
                </a>
            </p>
        </div>
        <div class="footer">
            <p>Sent by Draftly AI. Links expire in 24 hours.</p>
        </div>
    </div>
</body>
</html>
""")


async def send_improvement_notification(
    to: str,
    reviewer_name: str,
    proposal_count: int,
    prompt_count: int,
    rubric_count: int,
    tool_count: int,
    summary: str,
    dashboard_url: str,
    tokens: list[dict],
) -> dict:
    proposals_html = ""
    for t in tokens[:5]:
        proposal = t["proposal"]
        label = (
            proposal.get("proposed_changes", {}).get("node")
            or proposal.get("proposed_changes", {}).get("criterion")
            or proposal.get("proposed_changes", {}).get("name", "unknown")
        )
        token = t["token"]
        approve_url = (
            f"{dashboard_url}/api/improvements/token/{token}/action"
            "?action=approve"
        )
        reject_url = (
            f"{dashboard_url}/api/improvements/token/{token}/action"
            "?action=reject"
        )
        proposals_html += f"""
        <div class="proposal">
            <p><strong>{label}</strong> ({proposal['improvement_type']})</p>
            <a href="{approve_url}" class="btn btn-approve">Approve</a>
            <a href="{reject_url}" class="btn btn-reject">Reject</a>
        </div>
        """

    html = IMPROVEMENT_NOTIFICATION_TEMPLATE.substitute(
        summary=summary or "AI analysis complete.",
        proposal_count=proposal_count,
        prompt_count=prompt_count,
        rubric_count=rubric_count,
        tool_count=tool_count,
        proposals_html=proposals_html,
        dashboard_url=dashboard_url,
    )

    s = "s" if proposal_count != 1 else ""
    subject = f"Draftly: {proposal_count} improvement suggestion{s}"
    return await send_email(to, subject, html)
