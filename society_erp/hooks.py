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
            ["name","in",["Society Committee Member"]]
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
