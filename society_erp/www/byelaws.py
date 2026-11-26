from __future__ import annotations

import json

import frappe
from society_erp.byelaws_api import get_consultation_data

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/byelaws"
        raise frappe.Redirect

    context.title = "Bye-Law Consultation"
    consultation_param = frappe.form_dict.get("consultation")
    context.initial_data = get_consultation_data(consultation=consultation_param)
    context.initial_data_json = json.dumps(context.initial_data, default=str)
    return context
