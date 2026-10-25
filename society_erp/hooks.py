app_name = "society_erp"
app_title = "Society Erp"
app_publisher = "Mohammed Faisal"
app_description = "ERPNext App for Management of Apartment Societies"
app_email = "smsgatewaypgt@gmail.com"
app_license = "mit"

after_install = "society_erp.setup.after_install"
permission_query_conditions = {
    "Board Resolution": "society_erp.society_erp.doctype.board_resolution.board_resolution.get_permission_query_conditions",
}

has_permission = {
    "Board Resolution": "society_erp.society_erp.doctype.board_resolution.board_resolution.has_permission",
}
portal_menu_items = [
    {"title": "My Profile", "route": "/resident/profile", "role": "Website User"},
    {"title": "My Vehicles", "route": "/resident/vehicles", "role": "Website User"},
    {"title": "Maintenance", "route": "/resident/maintenance", "role": "Website User"},
    {"title": "Work Permits", "route": "/resident/work_permits", "role": "Website User"},
    {"title": "Gate Passes", "route": "/resident/visitors", "role": "Website User"},
    {"title": "Board Resolutions", "route": "/resident/board_resolutions", "role": "Website User"}
]
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [
            ["module", "=", "Society Erp"]
        ]
    },
    {
        "dt": "Property Setter",
        "filters": [
            ["module", "=", "Society Erp"]
        ]
    },
    {
        "dt": "Server Script",
        "filters": [
            ["module", "=", "Society Erp"]
        ]
    },
    {
        "dt": "Client Script",
        "filters": [
            ["module", "=", "Society Erp"]
        ]
    },
    
{
    "dt": "Role",
    "filters": [
        ["name", "in", [
            "Society Committee Member",
            "Society Bot",
            "Maintenance Staff",
            "Estate Office Maintenance"
        ]]
    ]
}

]
doc_events = {
    "GL Entry": {
        "validate": [
            "society_erp.accounting.cost_center_validation.validate_required_cost_center"
        ]
    }
}

scheduler_events = {
    "daily": [
        "society_erp.parking_rental.expire_due_parking_rentals"
    ]
}

# Include custom frontend script on public/login pages
#app_include_js = "/assets/society_erp/js/login_redirect.js"
# Inject script into the public frontend (including the /login page)
web_include_js = "/assets/society_erp/js/login_redirect.js"

# Inject routing flag during authentication
on_login = "society_erp.hooks_override.flag_desk_users"
