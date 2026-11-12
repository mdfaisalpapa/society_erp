frappe.query_reports["Facility Deployment Variance"] = {
    "filters": [
        {
            "fieldname": "date",
            "label": __("Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "agency",
            "label": __("Agency"),
            "fieldtype": "Link",
            "options": "Facility Agency"
        }
    ]
};
