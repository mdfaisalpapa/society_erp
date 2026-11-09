import frappe
from frappe import _
from frappe.utils import flt, today


def check_resident_access():
    """
    Verifies that the session user is an active resident (Owner or Tenant)
    or authorized society staff.
    """
    if frappe.session.user == "Guest":
        return False, None

    user = frappe.session.user
    user_email = (user or "").strip().lower()

    # 1. Allow Society Staff / System Managers
    user_roles = frappe.get_roles(user)
    if any(
        r in user_roles
        for r in ["System Manager", "Accounts User", "Accounts Manager"]
    ):
        full_name = frappe.db.get_value("User", user, "full_name") or user
        return True, {
            "flat": "Office / Administration",
            "name": full_name,
            "type": "Staff",
        }

    # 2. Check active Tenants
    tenant = frappe.db.get_value(
        "Tenants",
        {"email": user_email, "active": 1},
        ["flat", "tenant_name"],
        as_dict=True,
    )
    if tenant and tenant.flat:
        return True, {
            "flat": tenant.flat,
            "name": tenant.tenant_name,
            "type": "Tenant",
        }

    # 3. Check active Owners (by email or user ID)
    owner = frappe.db.get_value(
        "Owners",
        {"email": user_email, "active": 1},
        ["flat", "owner_name"],
        as_dict=True,
    )
    if not owner:
        owner = frappe.db.get_value(
            "Owners",
            {"name": user, "active": 1},
            ["flat", "owner_name"],
            as_dict=True,
        )

    if owner and owner.flat:
        return True, {
            "flat": owner.flat,
            "name": owner.owner_name,
            "type": "Owner",
        }

    # 4. Fallback to resident_portal helper
    try:
        from society_erp.resident_portal import get_verified_owner_records

        records = get_verified_owner_records()
        if records:
            rec = records[0]
            return True, {
                "flat": rec.flat,
                "name": getattr(
                    rec, "resident_name", getattr(rec, "owner_name", "")
                ),
                "type": getattr(rec, "resident_type", "Owner"),
            }
    except Exception:
        pass

    return False, None


def get_context(context):
    """
    Renders the initial context for the Society Financials web page.
    - Enforces authentication and resident access control.
    - Pre-loads filter options: Companies, Cost Centers, Fiscal Years, and Default Dates.
    """
    # 1. Require authentication
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    # 2. Enforce active resident verification
    has_access, resident_info = check_resident_access()
    if not has_access:
        context.not_a_resident = True
        return context

    context.not_a_resident = False
    context.flat_number = resident_info.get("flat")
    context.resident_name = resident_info.get("name")
    context.resident_type = resident_info.get("type")
    context.title = _("Society Financials — Statements & Reports")

    # 3. Resolve primary company
    default_company = (
        frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name")
    )
    context.default_company = default_company

    # 4. Fetch available companies
    companies = frappe.get_all(
        "Company",
        fields=["name", "company_name"],
        order_by="name asc",
    )
    context.companies = companies

    # 5. Pre-load Cost Centers for filtering
    # Fetch active Cost Centers belonging to the society company
    cost_center_filters = {"company": default_company}
    if frappe.db.has_column("Cost Center", "disabled"):
        cost_center_filters["disabled"] = 0

    cost_centers = frappe.get_all(
        "Cost Center",
        filters=cost_center_filters,
        fields=["name", "cost_center_name", "is_group"],
        order_by="is_group desc, name asc",
    )
    context.cost_centers = cost_centers

    # 6. Pre-load Fiscal Years and calculate default Date Range
    fiscal_years = frappe.get_all(
        "Fiscal Year",
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
    )
    context.fiscal_years = fiscal_years

    today_date = today()
    default_from_date = None
    default_to_date = today_date

    try:
        from erpnext.accounts.utils import get_fiscal_year

        fy_details = get_fiscal_year(today_date, company=default_company)
        default_from_date = str(fy_details[1])
    except Exception:
        default_from_date = f"{today_date[:4]}-04-01"

    context.default_from_date = default_from_date
    context.default_to_date = default_to_date
    context.currency = (
        frappe.db.get_value("Company", default_company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    return context


@frappe.whitelist()
def get_financial_report(
    report_name,
    from_date=None,
    to_date=None,
    cost_center=None,
    company=None,
    periodicity="Yearly",
):
    """
    Secure API endpoint for the resident portal frontend.
    Executes ERPNext's native `frappe.desk.query_report.run` for:
      - 'Profit and Loss Statement'
      - 'Balance Sheet'
    Bridges report execution safely for verified residents without exposing
    unauthorized desk report capabilities.
    """
    # 1. Access Control: resident check
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _(
                "Access Denied: Only active residents and authorized society members can view financial reports."
            ),
            frappe.PermissionError,
        )

    # 2. Strict whitelist of reports allowed through this resident portal
    allowed_reports = {
        "Profit and Loss Statement": "Profit and Loss Statement",
        "Balance Sheet": "Balance Sheet",
    }
    if report_name not in allowed_reports:
        frappe.throw(
            _(
                "Invalid report requested. Only 'Profit and Loss Statement' and 'Balance Sheet' are permitted."
            ),
            frappe.ValidationError,
        )

    # 3. Resolve Company
    if not company:
        company = (
            frappe.db.get_single_value("Global Defaults", "default_company")
            or frappe.db.get_value("Company", {}, "name")
        )

    # 4. Resolve Date Range and Fiscal Year details
    today_date = today()
    if not to_date:
        to_date = today_date
    if not from_date:
        try:
            from erpnext.accounts.utils import get_fiscal_year

            from_date = str(get_fiscal_year(to_date, company=company)[1])
        except Exception:
            from_date = f"{to_date[:4]}-04-01"

    from erpnext.accounts.utils import get_fiscal_year

    try:
        from_fy = get_fiscal_year(from_date, company=company)[0]
    except Exception:
        from_fy = None

    try:
        to_fy = get_fiscal_year(to_date, company=company)[0]
    except Exception:
        to_fy = from_fy

    # 5. Build report filters expected by ERPNext's query_report engine
    report_filters = {
        "company": company,
        "filter_based_on": "Date Range",
        "period_start_date": from_date,
        "period_end_date": to_date,
        "from_date": from_date,
        "to_date": to_date,
        "periodicity": periodicity or "Yearly",
    }

    if from_fy:
        report_filters["from_fiscal_year"] = from_fy
    if to_fy:
        report_filters["to_fiscal_year"] = to_fy

    if cost_center and cost_center != "All Cost Centers":
        report_filters["cost_center"] = (
            [cost_center] if isinstance(cost_center, str) else cost_center
        )

    # 6. Securely elevate execution context to run ERPNext desk script report
    from frappe.desk.query_report import run

    current_user = frappe.session.user
    frappe.set_user("Administrator")
    try:
        report_data = run(
            report_name=report_name,
            filters=report_filters,
            user="Administrator",
            are_default_filters=False,
        )
    finally:
        frappe.set_user(current_user)

    company_currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    return {
        "report_name": report_name,
        "columns": report_data.get("columns", []),
        "result": report_data.get("result", []),
        "chart": report_data.get("chart"),
        "report_summary": report_data.get("report_summary"),
        "company": company,
        "currency": company_currency,
        "from_date": from_date,
        "to_date": to_date,
        "cost_center": cost_center or "All Cost Centers",
    }
