import frappe
from society_erp.www.resident.notices.index import get_resident_info


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # Contacts directory: Society Internal + Public Services (Always available)
    context.internal_contacts = [
        {"title": "Security Main Gate", "desc": "24x7 Visitor Entry & Gate Security", "phone": "080-23456781", "badge": "24x7 SOS", "icon": "👮"},
        {"title": "Estate / Facility Manager", "desc": "Society Office & Facility Operations", "phone": "080-23456782", "badge": "09:00 - 18:00", "icon": "🏢"},
        {"title": "Security Gate 2 (Rear)", "desc": "Service & Contractor Gate Checkpoint", "phone": "080-23456783", "badge": "24x7", "icon": "🚪"},
        {"title": "Electrician & Plumber Desk", "desc": "Emergency Common Maintenance", "phone": "080-23456784", "badge": "On Duty", "icon": "🔧"},
        {"title": "Clubhouse Reception", "desc": "Gym & Community Hall In-Charge", "phone": "080-23456785", "badge": "06:00 - 22:00", "icon": "🏛️"},
    ]

    context.public_emergencies = [
        {"title": "National Emergency SOS", "phone": "112", "desc": "All-in-one Emergency Helpline", "icon": "🚨"},
        {"title": "Police Control Room", "phone": "100", "desc": "Immediate Police Assistance", "icon": "🚓"},
        {"title": "Fire Brigade & Rescue", "phone": "101", "desc": "Fire Safety & Extinguisher SOS", "icon": "🚒"},
        {"title": "Ambulance / Medical Emergency", "phone": "108", "desc": "24x7 Emergency Medical Dispatch", "icon": "🚑"},
        {"title": "Women Safety Helpline", "phone": "1091", "desc": "Immediate Women Protection", "icon": "👩"},
        {"title": "Senior Citizens Helpline", "phone": "14567", "desc": "Elder Care Assistance & Help", "icon": "🧓"},
    ]

    res_info = get_resident_info()
    if not res_info:
        context.not_a_resident = False
        return context

    context.not_a_resident = False
    context.resident_info = res_info
    context.flat_number = res_info.get("flat")
    return context
