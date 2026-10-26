import hashlib
import json
from werkzeug.wrappers import Response
import frappe
from frappe import _
from frappe.utils import now_datetime


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login is required"), frappe.PermissionError)


def _require_push_config():
    public_key = frappe.conf.get("push_vapid_public_key")
    private_key = frappe.conf.get("push_vapid_private_key")
    subject = frappe.conf.get("push_vapid_subject")

    if not public_key or not private_key or not subject:
        frappe.throw(
            _("Web Push is not configured by the administrator."),
            frappe.ValidationError,
        )

    return public_key, private_key, subject


def _subscription_name(endpoint):
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


@frappe.whitelist(methods=["POST"])
def get_public_config():
    """Return only the public VAPID key; never expose the private key."""
    _require_login()
    public_key, _, _ = _require_push_config()
    return {"public_key": public_key}



@frappe.whitelist(methods=["POST"])
def save_subscription(subscription):
    """Register or update a subscription for the currently logged-in user."""
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

    name = _subscription_name(endpoint)
    existing = frappe.db.exists("Push Subscription", name)

    if existing:
        record = frappe.get_doc("Push Subscription", name)

        if record.user != frappe.session.user:
            frappe.throw(
                _("This subscription is already associated with another user."),
                frappe.PermissionError,
            )

        record.endpoint = endpoint
        record.p256dh = p256dh
        record.auth = auth
        record.enabled = 1
        record.last_updated = now_datetime()
        record.save(ignore_permissions=True)

    else:
        record = frappe.get_doc({
            "doctype": "Push Subscription",
            "name": name,
            "user": frappe.session.user,
            "endpoint": endpoint,
            "p256dh": p256dh,
            "auth": auth,
            "enabled": 1,
            "last_updated": now_datetime(),
        })
        record.insert(ignore_permissions=True)

    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def remove_subscription(endpoint):
    """Remove only the current user's subscription."""
    _require_login()

    if not isinstance(endpoint, str) or not endpoint.startswith("https://"):
        frappe.throw(_("Invalid subscription endpoint"), frappe.ValidationError)

    name = _subscription_name(endpoint)
    if not frappe.db.exists("Push Subscription", name):
        return {"ok": True}

    record = frappe.get_doc("Push Subscription", name)
    if record.user != frappe.session.user:
        frappe.throw(_("Not permitted"), frappe.PermissionError)

    record.delete(ignore_permissions=True)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def send_test_notification():
    """Send a test notification only to the caller's own registered devices."""
    _require_login()
    _, private_key, subject = _require_push_config()

    subscriptions = frappe.get_all(
        "Push Subscription",
        filters={"user": frappe.session.user, "enabled": 1},
        fields=["name", "endpoint", "p256dh", "auth"],
        limit_page_length=100,
    )

    if not subscriptions:
        frappe.throw(_("No enabled subscriptions found for your account."))

    # Import only when sending so unrelated requests do not require the
    # delivery library to be loaded.
    from pywebpush import WebPushException, webpush

    sent = 0
    failed = 0

    for item in subscriptions:
        info = {
            "endpoint": item.endpoint,
            "keys": {"p256dh": item.p256dh, "auth": item.auth},
        }
        try:
            webpush(
                subscription_info=info,
                data=json.dumps({
                    "title": "KVC3 notification test",
                    "body": "Web Push is working on this device.",
                    "url": "/resident/",
                }),
                vapid_private_key=private_key,
                vapid_claims={"sub": subject},
            )
            sent += 1
        except WebPushException as exc:
            failed += 1
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (404, 410):
                frappe.delete_doc(
                    "Push Subscription",
                    item.name,
                    ignore_permissions=True,
                )
            frappe.log_error(
                title="Web Push delivery failed",
                message=f"Subscription {item.name}; HTTP status: {status}",
            )

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
