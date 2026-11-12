import frappe
from society_erp.api.utils import portal_api


@frappe.whitelist()
@portal_api
def get_emergency_contacts() -> dict:
    """
    Fetch active emergency contacts categorized with complete phone and hours directory.
    """
    all_contacts = frappe.get_all(
        "Emergency Contact",
        filters={"enabled": 1},
        fields=["name", "title", "category", "phone", "operating_hours", "icon", "description", "sort_order"],
        order_by="sort_order asc, title asc"
    )

    internal_categories = ["Society Security", "Estate Office", "Maintenance & Utilities"]
    internal = []
    public = []

    int_lines = []
    pub_lines = []

    for c in all_contacts:
        item = {
            "title": c.title,
            "phone": c.phone,
            "hours": c.operating_hours or "24x7",
            "icon": c.icon or "📞",
            "description": c.description or "",
            "category": c.category
        }
        line = f"• {item['icon']} *{c.title}*: 📞 `{c.phone}` ({item['hours']})"
        if c.description:
            line += f"\n  _{c.description}_"

        if c.category in internal_categories:
            internal.append(item)
            int_lines.append(line)
        else:
            public.append(item)
            pub_lines.append(line)

    summary_text = "*Internal Security & Estate:*\n" + ("\n".join(int_lines) if int_lines else "• Main Gate Security: 📞 24x7 Intercom\n• Estate Office: 📞 044-24567890 (9 AM - 6 PM)\n• Electrician / Plumber on-duty")

    # Append live on-duty facility security & guard details
    try:
        from society_erp.api.facility_staff import get_on_duty_security_summary
        sec_summary = get_on_duty_security_summary()
        if sec_summary and sec_summary.get("guards"):
            summary_text += "\n\n" + sec_summary.get("summary_text", "")
    except Exception as e:
        frappe.log_error(f"Failed to fetch on-duty security in emergency API: {e}")

    if pub_lines:
        summary_text += "\n\n*Public Emergency Services:*\n" + "\n".join(pub_lines)

    return {
        "contacts": all_contacts,
        "internal": internal,
        "public": public,
        "count": len(all_contacts),
        "summary_text": summary_text
    }
