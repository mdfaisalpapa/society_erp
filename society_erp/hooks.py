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
    },
    "Purchase Invoice": {
        "validate": [
            "society_erp.accounting.ineligible_itc.validate_purchase_invoice"
        ]
    }
}

regional_overrides = {
    "India": {
        "erpnext.accounts.doctype.purchase_invoice.purchase_invoice.make_regional_gl_entries": (
            "society_erp.accounting.ineligible_itc.make_regional_gl_entries"
        ),
        "erpnext.stock.doctype.purchase_receipt.purchase_receipt.update_regional_gl_entries": (
            "society_erp.accounting.ineligible_itc.update_regional_gl_entries_pr"
        ),
        "erpnext.controllers.buying_controller.update_regional_item_valuation_rate": (
            "society_erp.accounting.ineligible_itc.update_valuation_rate"
        ),
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
web_include_js = [
    "/assets/society_erp/js/login_redirect.js",
    "/assets/society_erp/js/push_registration.js",
]

# Inject routing flag during authentication
on_login = "society_erp.hooks_override.redirect_after_login"
override_whitelisted_methods = {
    "frappe.core.doctype.user.user.update_password":
        "society_erp.password_reset.update_password",
}
doctype_js = {
    "Voting Poll": "public/js/voting_poll.js",
}
after_migrate = [
    "society_erp.migrations.ensure_voting_participation_unique_index",
    "society_erp.migrations.ensure_provisional_electorate_unique_index",
    "society_erp.migrations.ensure_push_subscription_endpoint_index",
]

consensus_voter_providers = [
    "society_erp.voting.provider.SocietyERPProvider"
]

consensus_secret_resolvers = [
    "society_erp.voting.secrets.SocietyERPSecretResolver"
]

