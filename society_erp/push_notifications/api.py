import json
import urllib.parse
from werkzeug.wrappers import Response
import frappe
from frappe import _
from frappe.utils import now_datetime

try:
    from pywebpush import WebPushException, webpush
    PYWEBPUSH_AVAILABLE = True
except ImportError:
    webpush = None
    WebPushException = Exception
    PYWEBPUSH_AVAILABLE = False


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)


def _require_push_config():
    """Retrieve VAPID keys, checking both push_vapid_* and standard vapid_* keys."""
    public_key = frappe.conf.get("push_vapid_public_key") or frappe.conf.get("vapid_public_key")
    private_key = frappe.conf.get("push_vapid_private_key") or frappe.conf.get("vapid_private_key")
    subject = (
        frappe.conf.get("push_vapid_subject")
        or frappe.conf.get("vapid_sub")
        or "mailto:admin@kvc3.local"
    )

    if not public_key or not private_key or not subject:
        frappe.throw(
            _("Web Push is not configured by the administrator."),
            frappe.ValidationError,
        )

    return public_key, private_key, subject


@frappe.whitelist(methods=["POST"])
def get_public_config():
    """Return only the public VAPID key; never expose the private key."""
    _require_login()
    public_key, _, _unused = _require_push_config()
    return {"public_key": public_key}


@frappe.whitelist(methods=["POST"])
def save_subscription(subscription):
    """Register or update a subscription for the currently logged-in user.
    Deduplicates by endpoint so multiple devices for the same user coexist."""
    _require_login()

    if isinstance(subscription, str):
        subscription = json.loads(subscription)

    endpoint = subscription.get("endpoint")
    keys = subscription.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not all(
        isinstance(value, str) and value
        for value in (endpoint, p256dh, auth)
    ):
        frappe.throw(_("Invalid push subscription"), frappe.ValidationError)

    if not endpoint.startswith("https://"):
        frappe.throw(_("Invalid subscription endpoint"), frappe.ValidationError)

    # Find existing subscription by endpoint (unique per browser/device profile)
    existing_name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")

    if existing_name:
        record = frappe.get_doc("Push Subscription", existing_name)
        # Update user association, keys, and status
        record.user = frappe.session.user
        record.p256dh = p256dh
        record.auth = auth
        record.enabled = 1
        record.last_updated = now_datetime()
        record.save(ignore_permissions=True)
    else:
        record = frappe.get_doc({
            "doctype": "Push Subscription",
            "user": frappe.session.user,
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "enabled": 1,
            "last_updated": now_datetime(),
        })
        record.insert(ignore_permissions=True)

    return {"ok": True, "subscription_id": record.name}


@frappe.whitelist(methods=["POST"])
def remove_subscription(endpoint):
    """Remove only the current user's subscription."""
    _require_login()

    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        frappe.throw(_("Invalid subscription endpoint"), frappe.ValidationError)

    existing_name = frappe.db.get_value("Push Subscription", {"endpoint": endpoint}, "name")
    if not existing_name:
        return {"ok": True}

    record = frappe.get_doc("Push Subscription", existing_name)
    if record.user != frappe.session.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    record.delete(ignore_permissions=True)
    return {"ok": True}


def send_web_push(subscription_info, payload_data, private_key, subject, sub_record_name=None):
    """Low-level helper to dispatch a web push notification via pywebpush.
    Automatically handles 404 / 410 Gone responses by removing stale subscriptions."""
    if not PYWEBPUSH_AVAILABLE:
        frappe.log_error("pywebpush is not installed", "Web Push Delivery Error")
        return False

    endpoint = subscription_info.get("endpoint", "")
    parsed = urllib.parse.urlparse(endpoint)
    aud = f"{parsed.scheme}://{parsed.netloc}"

    claims = {
        "sub": subject,
        "aud": aud,
    }

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload_data) if isinstance(payload_data, dict) else payload_data,
            vapid_private_key=private_key,
            vapid_claims=claims,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410) and sub_record_name:
            try:
                frappe.delete_doc("Push Subscription", sub_record_name, ignore_permissions=True)
                frappe.db.commit()
            except Exception:
                pass
        frappe.log_error(
            title="Web Push delivery failed",
            message=f"Subscription {sub_record_name or endpoint}; HTTP status: {status}; Error: {exc}",
        )
        return False
    except Exception as exc:
        frappe.log_error(
            title="Web Push delivery unexpected exception",
            message=f"Subscription {sub_record_name or endpoint}; Error: {exc}",
        )
        return False


def _send_push_notification_worker(user=None, title="KVC3 Notification", body="", url="/resident/", data=None):
    """Background worker queued via frappe.enqueue to dispatch pushes without blocking HTTP cycles."""
    _unused_pub, private_key, subject = _require_push_config()

    filters = {"enabled": 1}
    if user:
        filters["user"] = user

    subscriptions = frappe.get_all(
        "Push Subscription",
        filters=filters,
        fields=["name", "user", "endpoint", "p256dh", "auth"],
        limit_page_length=500,
    )

    if not subscriptions:
        return {"sent": 0, "failed": 0}

    payload = {
        "title": title,
        "body": body,
        "url": url,
    }
    if data and isinstance(data, dict):
        payload.update(data)

    sent = 0
    failed = 0

    for item in subscriptions:
        info = {
            "endpoint": item.endpoint,
            "keys": {"p256dh": item.p256dh, "auth": item.auth},
        }
        success = send_web_push(
            subscription_info=info,
            payload_data=payload,
            private_key=private_key,
            subject=subject,
            sub_record_name=item.name,
        )
        if success:
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed}


@frappe.whitelist(methods=["POST"])
def send_push_notification(user=None, title="KVC3 Notification", body="", url="/resident/", data=None, async_send=True):
    """Asynchronously queue push notification dispatch for a user or all users."""
    if isinstance(async_send, str):
        async_send = async_send.lower() in ("true", "1")

    if async_send:
        frappe.enqueue(
            "society_erp.push_notifications.api._send_push_notification_worker",
            queue="short",
            user=user,
            title=title,
            body=body,
            url=url,
            data=data,
        )
        return {"enqueued": True}
    else:
        return _send_push_notification_worker(user=user, title=title, body=body, url=url, data=data)


@frappe.whitelist(methods=["POST"])
def send_test_notification():
    """Send a test notification only to the caller's own registered devices."""
    _require_login()
    _unused_pub, private_key, subject = _require_push_config()

    subscriptions = frappe.get_all(
        "Push Subscription",
        filters={"user": frappe.session.user, "enabled": 1},
        fields=["name", "endpoint", "p256dh", "auth"],
        limit_page_length=100,
    )

    if not subscriptions:
        frappe.throw(_("No enabled subscriptions found for your account."))

    sent = 0
    failed = 0

    for item in subscriptions:
        info = {
            "endpoint": item.endpoint,
            "keys": {"p256dh": item.p256dh, "auth": item.auth},
        }
        success = send_web_push(
            subscription_info=info,
            payload_data={
                "title": "KVC3 Notification Test",
                "body": "Web Push is working on this device.",
                "url": "/resident/",
            },
            private_key=private_key,
            subject=subject,
            sub_record_name=item.name,
        )
        if success:
            sent += 1
        else:
            failed += 1

    return {"sent": sent, "failed": failed}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def service_worker():
    """Serve the push worker as JavaScript with the required scope header."""
    from pathlib import Path

    worker_path = (
        Path(frappe.get_app_path("society_erp"))
        / "push_notifications"
        / "service_worker.js"
    )

    return Response(
        worker_path.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
        headers={
            "Service-Worker-Allowed": "/resident/",
            "Cache-Control": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@frappe.whitelist()
def validate_vapid_setup():
    """Diagnostic check to validate VAPID configuration and active subscriptions."""
    public_key, private_key, subject = _require_push_config()
    subs_count = frappe.db.count("Push Subscription", {"enabled": 1})
    return {
        "status": "configured",
        "public_key": public_key,
        "private_key_set": bool(private_key),
        "subject": subject,
        "active_subscriptions": subs_count,
    }
