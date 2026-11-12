import secrets
import frappe
from frappe.auth import LoginManager
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def generate_portal_link(for_user: str, target_route: str = "/resident") -> dict:
    """
    Generate an SSO magic link for Telegram WebApp or browser access.
    Expires in 15 minutes.
    """
    if not for_user or not frappe.db.exists("User", for_user):
        frappe.throw("Invalid user for portal link generation.")

    token = secrets.token_urlsafe(32)
    cache_key = f"portal_sso_{token}"
    frappe.cache.set_value(cache_key, for_user, expires_in_sec=900)

    # Use base url
    base_url = "https://giver-unwed-unleveled.ngrok-free.dev"
    sso_url = f"{base_url}/api/method/society_erp.api.sso.authenticate_sso?token={token}&redirect_to={target_route}"

    return {
        "url": sso_url,
        "token": token,
        "expires_in": 900
    }


@frappe.whitelist(allow_guest=True)
def authenticate_sso(token: str, redirect_to: str = "/resident"):
    """
    Consumes the one-time token, sets the session cookie, and redirects to target portal route.
    """
    if not token:
        frappe.respond_as_web_page("Invalid Request", "Missing authentication token.", http_status_code=400)
        return

    cache_key = f"portal_sso_{token}"
    user = frappe.cache.get_value(cache_key)

    if not user:
        frappe.respond_as_web_page("Session Expired", "This magic login link has expired or has already been used. Please request a new one from the bot.", http_status_code=403)
        return

    # Delete token so it cannot be reused
    frappe.cache.delete_value(cache_key)

    # Log in user
    frappe.local.login_manager = LoginManager()
    frappe.local.login_manager.login_as(user)

    clean_redirect = redirect_to if (redirect_to and redirect_to.startswith("/")) else "/resident"
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = clean_redirect
