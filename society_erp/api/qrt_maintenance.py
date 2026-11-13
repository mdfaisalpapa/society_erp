import secrets
import frappe
from frappe import _
from frappe.utils import now_datetime, nowdate, format_datetime, get_url
import requests


def get_telegram_config() -> tuple:
    """Returns (bot_token, qrt_chat_id)."""
    settings = frappe.get_single("Society ERP Settings")
    token = None
    try:
        token = settings.get_password("telegram_bot_token", raise_exception=False)
    except Exception:
        token = None

    if not token:
        # Fallback to Bot Channel token
        try:
            bot_ch = frappe.get_doc("Bot Channel", "Telegram Demo Channel")
            token = bot_ch.get_password("telegram_bot_token", raise_exception=False)
        except Exception:
            token = None

    chat_id = settings.get("qrt_telegram_chat_id")
    return token, chat_id


def send_telegram_message(text: str, reply_markup: dict = None) -> bool:
    """Send a formatted markdown message to the QRT Telegram Group."""
    token, chat_id = get_telegram_config()
    if not token or not chat_id:
        frappe.logger("society_erp").warning(f"Telegram bot token or QRT chat ID not configured: token={bool(token)}, chat_id={chat_id}")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            return True
        else:
            frappe.logger("society_erp").error(f"Telegram API failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        frappe.logger("society_erp").error(f"Telegram request exception: {e}")
        return False


def generate_claim_key(ticket_name: str) -> str:
    """Generate or retrieve a secure token for technician magic link."""
    existing_key = frappe.db.get_value("Maintenance Ticket", ticket_name, "claim_key")
    if existing_key:
        return existing_key
    new_key = secrets.token_urlsafe(16)
    frappe.db.set_value("Maintenance Ticket", ticket_name, "claim_key", new_key)
    frappe.db.commit()
    return new_key


@frappe.whitelist()
def assign_ticket_and_notify_qrt(ticket_name: str, staff_id: str = None, remarks: str = None) -> dict:
    """
    Assign a ticket to staff (or leave open to claim) and post magic link to QRT Telegram Group.
    """
    if not ticket_name or not frappe.db.exists("Maintenance Ticket", ticket_name):
        frappe.throw(_("Ticket not found"))

    ticket = frappe.get_doc("Maintenance Ticket", ticket_name)
    staff_doc = None
    if staff_id:
        if not frappe.db.exists("Facility Staff", staff_id):
            frappe.throw(_("Staff member not found"))
        staff_doc = frappe.get_doc("Facility Staff", staff_id)
        ticket.assigned_staff = staff_id
        ticket.claimed_by = f"{staff_doc.full_name} ({staff_doc.role})"
        ticket.claimed_on = now_datetime()
        ticket.status = "Assigned"
    else:
        ticket.status = "Open"

    if remarks:
        existing = ticket.resolution_remarks or ""
        ticket.resolution_remarks = f"{existing}\n[{nowdate()}] Assignment: {remarks}".strip()

    if not ticket.claim_key:
        ticket.claim_key = secrets.token_urlsafe(16)

    claim_key = ticket.claim_key
    ticket.save(ignore_permissions=True)
    frappe.db.commit()

    # Build Magic Link URL
    base_url = get_url()
    magic_url = f"{base_url}/maintenance_job?id={ticket.name}&key={claim_key}"

    # Telegram Message Content
    assigned_str = f"👤 *Assigned To:* `{staff_doc.full_name} ({staff_doc.role})`" if staff_doc else "⚠️ *Assigned To:* `Unassigned (Open for Claim)`"
    lines = [
        f"🚨 *Maintenance Ticket Notification — #{ticket.name}*",
        f"🏢 *Flat:* `{ticket.resident or 'Common Area'}`",
        f"🛠️ *Category:* `{ticket.category}` | Priority: *{ticket.priority_level or 'Routine'}*",
        f"📝 *Description:* {ticket.description}",
        assigned_str
    ]
    if remarks:
        lines.append(f"💬 *Remarks:* _{remarks}_")

    lines.append(f"\n📲 *Claim / Submit Job Completion Details:*")
    lines.append(f"👉 [Click to Open Work Order Card]({magic_url})")

    # Inline Keyboard
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛠️ Open / Claim Job Card", "url": magic_url}
            ]
        ]
    }

    sent = send_telegram_message("\n".join(lines), reply_markup=reply_markup)

    return {
        "success": True,
        "message": f"Ticket #{ticket.name} updated. Posted to QRT Telegram Group: {sent}",
        "magic_url": magic_url,
        "telegram_sent": sent
    }


@frappe.whitelist()
def post_unassigned_tickets_summary(time_of_day: str = "Morning") -> dict:
    """
    Gathers all unassigned or pending maintenance tickets and posts a digest to QRT group.
    Scheduled for Morning (08:00) and Evening (18:00).
    """
    unassigned = frappe.get_all(
        "Maintenance Ticket",
        filters={"status": "Open", "assigned_staff": ("is", "not set")},
        fields=["name", "resident", "category", "priority_level", "description", "received_on", "claim_key"],
        order_by="creation asc",
        limit_page_length=50
    )

    if not unassigned:
        msg = f"☀️ *KVC3 Maintenance QRT — {time_of_day} Digest*\n\n✅ Great job! There are currently *zero unassigned maintenance tickets*."
        sent = send_telegram_message(msg)
        return {"count": 0, "telegram_sent": sent, "message": "No unassigned tickets"}

    lines = [
        f"📋 *KVC3 Maintenance QRT — {time_of_day} Unassigned Digest*",
        f"⚠️ There are *{len(unassigned)} unassigned tickets* requiring technician allocation:\n"
    ]

    base_url = get_url()

    for idx, t in enumerate(unassigned[:15], 1):
        key = t.claim_key or generate_claim_key(t.name)
        magic_url = f"{base_url}/maintenance_job?id={t.name}&key={key}"
        flat = t.resident or "Common"
        cat = t.category or "General"
        prio = t.priority_level or "Routine"
        desc = (t.description[:45] + "…") if t.description and len(t.description) > 45 else (t.description or "")
        lines.append(f"{idx}. *#{t.name}* ({flat}) [{cat} - `{prio}`]\n   _{desc}_\n   👉 [Claim Ticket]({magic_url})")

    if len(unassigned) > 15:
        lines.append(f"\n_...and {len(unassigned) - 15} more unassigned tickets._")

    lines.append(f"\n💡 *Staff instructions:* Tap any link above to claim the ticket and submit completion photo.")

    sent = send_telegram_message("\n".join(lines))
    return {
        "count": len(unassigned),
        "telegram_sent": sent,
        "message": f"Posted {len(unassigned)} unassigned tickets to QRT."
    }
