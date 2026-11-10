import frappe
from frappe import _
from frappe.utils import flt, fmt_money, format_date, get_first_day, get_last_day, today


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


def get_active_cost_centers(company, exclude_common=True):
    """
    Crucial Rule: Only fetch and return Cost Centers that currently have a non-zero
    ledger balance / activity in tabGL Entry. Exclude any zero-balance cost centers.
    For group Cost Centers, includes them if any descendant child has non-zero ledger activity.
    When exclude_common is True, strictly excludes the common cost center pool
    (e.g., 'Common - CHCR') and all its children/descendants (Community Hall, General Common,
    WTP & STP Operations) from the main Financial Statements cost center filter.
    """
    filters = {"company": company}
    if frappe.db.has_column("Cost Center", "disabled"):
        filters["disabled"] = 0

    all_ccs = frappe.get_all(
        "Cost Center",
        filters=filters,
        fields=["name", "cost_center_name", "parent_cost_center", "is_group", "lft", "rgt"],
        order_by="lft asc",
    )

    if not all_ccs:
        return []

    # Identify common pool names (e.g. Common - CHCR, Common - KVC3)
    common_pool_names = set()
    if exclude_common:
        for cc in all_ccs:
            c_name = (cc.name or "").lower()
            c_cname = (cc.cost_center_name or "").lower()
            if "common" in c_name or "common" in c_cname:
                common_pool_names.add(cc.name)

    # Get set of leaf cost centers with non-zero debits or credits
    active_leaf_ccs = set(
        frappe.db.sql_list(
            """
            SELECT DISTINCT cost_center 
            FROM `tabGL Entry` 
            WHERE company = %s 
              AND cost_center IS NOT NULL 
              AND cost_center != ''
              AND (debit != 0 OR credit != 0)
            """,
            (company,),
        )
    )

    # Filter out cost centers with no ledger balance / activity, and exclude common if requested
    active_cost_centers = []
    for cc in all_ccs:
        if exclude_common:
            # Strictly exclude common cost center and any cost center whose parent is in common pool
            if cc.name in common_pool_names or cc.parent_cost_center in common_pool_names:
                continue
            # Also exclude known common children by name if orphaned or mislinked
            if cc.cost_center_name in ["Community Hall", "WTP & STP Operations", "General Common"]:
                continue

        if cc.is_group:
            has_activity = frappe.db.sql(
                """
                SELECT 1 FROM `tabGL Entry` gle
                INNER JOIN `tabCost Center` child ON gle.cost_center = child.name
                WHERE gle.company = %s
                  AND child.lft >= %s AND child.rgt <= %s
                  AND (gle.debit != 0 OR gle.credit != 0)
                LIMIT 1
                """,
                (company, cc.lft, cc.rgt),
            )
            if has_activity:
                active_cost_centers.append(cc)
        else:
            if cc.name in active_leaf_ccs:
                active_cost_centers.append(cc)

    return active_cost_centers


def get_child_common_cost_centers(company):
    """
    Returns the available child common cost centers (e.g. Community Hall, General Common,
    WTP & STP Operations) for the Gross Common Expenses modal dropdown.
    """
    filters = {"company": company, "is_group": 0}
    if frappe.db.has_column("Cost Center", "disabled"):
        filters["disabled"] = 0

    all_leaves = frappe.get_all(
        "Cost Center",
        filters=filters,
        fields=["name", "cost_center_name", "parent_cost_center"],
        order_by="cost_center_name asc",
    )

    common_leaves = []
    for cc in all_leaves:
        p_name = (cc.parent_cost_center or "").lower()
        c_name = (cc.name or "").lower()
        if (
            "common" in p_name
            or "common" in c_name
            or cc.cost_center_name in ["Community Hall", "WTP & STP Operations", "General Common"]
        ):
            common_leaves.append(cc)

    return common_leaves


def get_context(context):
    """
    Renders the initial context for the Society Financials web page.
    - Enforces authentication and resident access control.
    - Pre-loads active, non-zero Cost Centers.
    - Pre-loads available Financial Years from the database.
    - Pre-loads submitted Purchase Invoices.
    - Pre-loads monthly Maintenance Billing Runs with FY tagging.
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

    # 5. Pre-load only Cost Centers with non-zero ledger balance (excluding common cost centers)
    context.cost_centers = get_active_cost_centers(default_company, exclude_common=True)

    # 5B. Pre-load child common cost centers for Gross Common Expenses modal
    context.child_common_cost_centers = get_child_common_cost_centers(default_company)

    # 6. Pre-load available Financial Years from the database
    fy_filters = {}
    if frappe.db.has_column("Fiscal Year", "disabled"):
        fy_filters["disabled"] = 0

    fiscal_years = frappe.get_all(
        "Fiscal Year",
        filters=fy_filters,
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
    )
    context.fiscal_years = fiscal_years

    # 7. Calculate default dates & active fiscal year
    today_date = today()
    default_from_date = None
    default_to_date = today_date

    try:
        from erpnext.accounts.utils import get_fiscal_year

        fy_details = get_fiscal_year(today_date, company=default_company)
        default_from_date = str(fy_details[1])
        context.current_fiscal_year = fy_details[0]
    except Exception:
        default_from_date = f"{today_date[:4]}-04-01"
        context.current_fiscal_year = fiscal_years[0].name if fiscal_years else ""

    context.default_from_date = default_from_date
    context.default_to_date = default_to_date
    currency = (
        frappe.db.get_value("Company", default_company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )
    context.currency = currency

    # 8. Fetch society's submitted Purchase Invoices (docstatus = 1) for transparency
    purchase_invoices = frappe.get_all(
        "Purchase Invoice",
        filters={
            "docstatus": 1,
            "company": default_company,
        },
        fields=[
            "name",
            "posting_date",
            "bill_no",
            "supplier_name",
            "grand_total",
            "status",
            "remarks",
        ],
        order_by="posting_date desc, creation desc",
    )

    for inv in purchase_invoices:
        inv.formatted_grand_total = fmt_money(inv.grand_total, currency=currency)
        inv.formatted_posting_date = (
            format_date(inv.posting_date) if inv.posting_date else "-"
        )

    context.purchase_invoices = purchase_invoices

    # 9. Determine resident's Block and UDS
    resident_block = None
    flat_uds = 0.0
    if context.flat_number and context.flat_number != "Office / Administration":
        flat_doc = frappe.db.get_value(
            "Customer",
            context.flat_number,
            ["custom_block", "custom_uds"],
            as_dict=True,
        )
        if flat_doc:
            resident_block = flat_doc.custom_block
            flat_uds = flt(flat_doc.custom_uds)

    context.resident_block = resident_block
    context.resident_uds = flat_uds

    # 10. Pre-load all submitted Maintenance Billing Runs with FY tagging
    context.maintenance_runs = get_maintenance_billing_runs_data(
        company=default_company,
        currency=currency,
        resident_block=resident_block,
        resident_uds=flat_uds,
    )

    return context


def get_maintenance_billing_runs_data(company, currency, resident_block=None, resident_uds=0.0):
    """
    Helper function to query and enrich all submitted Maintenance Billing Runs
    with Financial Year mapping, start/end dates, total billed amount, and block count.
    """
    raw_runs = frappe.get_all(
        "Maintenance Billing Run",
        filters={
            "docstatus": 1,
            "company": company,
        },
        fields=[
            "name",
            "billing_month",
            "posting_date",
            "total_billed_amount",
            "company",
            "generation_status",
        ],
        order_by="posting_date desc, creation desc",
    )

    fy_list = frappe.get_all(
        "Fiscal Year",
        fields=["name", "year_start_date", "year_end_date"],
        order_by="year_start_date desc",
    )

    enriched_runs = []
    for r in raw_runs:
        posting_d = r.posting_date
        matched_fy = ""
        for fy in fy_list:
            if fy.year_start_date <= posting_d <= fy.year_end_date:
                matched_fy = fy.name
                break

        start_date = get_first_day(posting_d)
        end_date = get_last_day(posting_d)

        block_rows = frappe.get_all(
            "Maintenance Block Details",
            filters={"parent": r.name},
            fields=["block", "cost_center", "total_expense", "total_block_uds", "rate_per_uds"],
        )
        total_block_expense = sum(flt(b.total_expense) for b in block_rows)

        enriched_runs.append({
            "name": r.name,
            "billing_month": r.billing_month or r.name,
            "posting_date": str(r.posting_date),
            "formatted_posting_date": format_date(r.posting_date) if r.posting_date else "-",
            "fiscal_year": matched_fy,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "total_billed_amount": flt(r.total_billed_amount or total_block_expense),
            "formatted_total_amount": fmt_money(r.total_billed_amount or total_block_expense, currency=currency),
            "blocks_count": len(block_rows),
            "generation_status": r.generation_status or "Completed",
        })

    return enriched_runs


@frappe.whitelist()
def get_maintenance_billing_runs(fiscal_year=None):
    """
    Secure endpoint to fetch Maintenance Billing Runs, optionally filtered by Financial Year.
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and members can view maintenance runs."),
            frappe.PermissionError,
        )

    company = (
        frappe.db.get_single_value("Global Defaults", "default_company")
        or frappe.db.get_value("Company", {}, "name")
    )
    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    flat_number = resident_info.get("flat")
    resident_block = None
    flat_uds = 0.0
    if flat_number and flat_number != "Office / Administration":
        flat_doc = frappe.db.get_value(
            "Customer",
            flat_number,
            ["custom_block", "custom_uds"],
            as_dict=True,
        )
        if flat_doc:
            resident_block = flat_doc.custom_block
            flat_uds = flt(flat_doc.custom_uds)

    all_runs = get_maintenance_billing_runs_data(
        company=company,
        currency=currency,
        resident_block=resident_block,
        resident_uds=flat_uds,
    )

    if fiscal_year and fiscal_year != "All Fiscal Years":
        filtered_runs = [r for r in all_runs if r.get("fiscal_year") == fiscal_year]
    else:
        filtered_runs = all_runs

    return {
        "runs": filtered_runs,
        "currency": currency,
        "fiscal_year": fiscal_year or "All",
        "resident_block": resident_block,
        "resident_uds": flat_uds,
    }


@frappe.whitelist()
def get_maintenance_run_invoices(billing_month_start_date=None, billing_month_end_date=None, run_id=None):
    """
    Fetches submitted Purchase Invoice records (docstatus = 1) falling within
    that billing month (Date, Invoice ID, Supplier Name, Grand Total).
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and members can view maintenance run invoices."),
            frappe.PermissionError,
        )

    company = None
    billing_month = ""

    if run_id and frappe.db.exists("Maintenance Billing Run", run_id):
        run = frappe.get_doc("Maintenance Billing Run", run_id)
        company = run.company
        billing_month = run.billing_month or run.name
        if not billing_month_start_date or not billing_month_end_date:
            billing_month_start_date = str(get_first_day(run.posting_date))
            billing_month_end_date = str(get_last_day(run.posting_date))

    if not billing_month_start_date or not billing_month_end_date:
        today_date = today()
        billing_month_start_date = str(get_first_day(today_date))
        billing_month_end_date = str(get_last_day(today_date))

    if not company:
        company = (
            frappe.db.get_single_value("Global Defaults", "default_company")
            or frappe.db.get_value("Company", {}, "name")
        )

    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    invoices = frappe.get_all(
        "Purchase Invoice",
        filters={
            "docstatus": 1,
            "company": company,
            "posting_date": ["between", [billing_month_start_date, billing_month_end_date]],
        },
        fields=[
            "name",
            "posting_date",
            "bill_no",
            "supplier",
            "supplier_name",
            "grand_total",
            "status",
        ],
        order_by="posting_date asc, name asc",
    )

    total_invoiced_amount = 0.0
    formatted_invoices = []

    for inv in invoices:
        g_total = flt(inv.grand_total)
        total_invoiced_amount += g_total
        formatted_invoices.append({
            "name": inv.name,
            "posting_date": format_date(inv.posting_date) if inv.posting_date else "-",
            "raw_posting_date": str(inv.posting_date),
            "bill_no": inv.bill_no or "-",
            "supplier_name": inv.supplier_name or inv.supplier,
            "supplier": inv.supplier,
            "grand_total": g_total,
            "formatted_grand_total": fmt_money(g_total, currency=currency),
            "status": inv.status,
        })

    return {
        "run_id": run_id or "",
        "billing_month": billing_month,
        "from_date": format_date(billing_month_start_date),
        "to_date": format_date(billing_month_end_date),
        "company": company,
        "currency": currency,
        "total_invoiced_amount": flt(total_invoiced_amount, 2),
        "formatted_total_invoiced": fmt_money(total_invoiced_amount, currency=currency),
        "count": len(formatted_invoices),
        "invoices": formatted_invoices,
    }


@frappe.whitelist()
def get_complete_society_gl(run_id=None, posting_date=None, from_date=None, to_date=None, company=None):
    """
    Refined "View Complete Society GL" (Account-Wise Consolidation):
    Displays the expenses consolidated account-wise (e.g., total "Electricity Expenses",
    total "Housekeeping") for the entire society for that month.
    Filters by root_type = 'Expense' and date range, explicitly using GROUP BY account
    without cost centers.
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and authorized members can view society GL entries."),
            frappe.PermissionError,
        )

    billing_month = ""
    if run_id and frappe.db.exists("Maintenance Billing Run", run_id):
        run = frappe.get_doc("Maintenance Billing Run", run_id)
        posting_date = run.posting_date
        company = run.company
        billing_month = run.billing_month or run.name

    if posting_date and (not from_date or not to_date):
        from_date = str(get_first_day(posting_date))
        to_date = str(get_last_day(posting_date))

    if not from_date or not to_date:
        today_date = today()
        from_date = str(get_first_day(today_date))
        to_date = str(get_last_day(today_date))

    if not company:
        company = (
            frappe.db.get_single_value("Global Defaults", "default_company")
            or frappe.db.get_value("Company", {}, "name")
        )

    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    # Consolidated Account-Wise Query: strictly GROUP BY ge.account, acc.account_name
    gl_entries = frappe.db.sql(
        """
        SELECT 
            ge.account,
            acc.account_name,
            (SUM(ge.debit) - SUM(ge.credit)) as net_expense
        FROM `tabGL Entry` ge
        JOIN `tabAccount` acc ON ge.account = acc.name
        WHERE ge.company = %s
          AND ge.is_cancelled = 0
          AND acc.root_type = 'Expense'
          AND ge.posting_date BETWEEN %s AND %s
        GROUP BY ge.account, acc.account_name
        HAVING net_expense != 0
        ORDER BY net_expense DESC, ge.account ASC
        """,
        (company, from_date, to_date),
        as_dict=True,
    )

    formatted_entries = []
    total_society_expense = 0.0

    for entry in gl_entries:
        net = flt(entry.net_expense)
        total_society_expense += net
        formatted_entries.append({
            "account": entry.account,
            "account_name": entry.account_name or entry.account,
            "net_expense": net,
            "formatted_net_expense": fmt_money(net, currency=currency),
        })

    return {
        "run_id": run_id or "",
        "billing_month": billing_month,
        "from_date": format_date(from_date) if from_date else "-",
        "to_date": format_date(to_date) if to_date else "-",
        "company": company,
        "currency": currency,
        "total_society_expense": flt(total_society_expense, 2),
        "formatted_total_society_expense": fmt_money(total_society_expense, currency=currency),
        "entries": formatted_entries,
    }


@frappe.whitelist()
def get_gross_common_expenses(
    specific_cost_center=None,
    month=None,
    financial_year=None,
    month_start_date=None,
    month_end_date=None,
    run_id=None,
    company=None,
):
    """
    Common Area Expense Breakdown:
    Returns the gross expenses/income booked to common cost centers (e.g., 'Community Hall - CHCR',
    'General Common - CHCR', 'WTP & STP Operations - CHCR') BEFORE ERPNext's Cost Center
    Allocation credits them out to individual blocks.
    - specific_cost_center: Optional specific child common cost center. If blank/null, fetches combined gross.
    - month: Month number (1-12) or name (e.g. 'March').
    - financial_year: Active Financial Year (e.g. '2025-2026'). Used to accurately calculate month start/end dates.
    - month_start_date, month_end_date, run_id: Fallback date sources.
    Strictly aggregates debits (for Expense) and credits (for Income) without subtracting allocation credits.
    """
    import calendar
    from frappe.utils import getdate

    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and authorized members can view common expenses."),
            frappe.PermissionError,
        )

    if not company:
        company = (
            frappe.db.get_single_value("Global Defaults", "default_company")
            or frappe.db.get_value("Company", {}, "name")
        )

    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    billing_month = ""

    # 1. Resolve posting date range from month and financial_year if provided
    if month:
        m = None
        try:
            m = int(month)
        except (ValueError, TypeError):
            month_names = {
                "january": 1, "february": 2, "march": 3, "april": 4,
                "may": 5, "june": 6, "july": 7, "august": 8,
                "september": 9, "october": 10, "november": 11, "december": 12
            }
            m = month_names.get(str(month).strip().lower(), None)

        if m and 1 <= m <= 12:
            if financial_year and frappe.db.exists("Fiscal Year", financial_year):
                fy = frappe.get_doc("Fiscal Year", financial_year)
                fy_start = getdate(fy.year_start_date)
                fy_end = getdate(fy.year_end_date)
                yr = fy_end.year if m < fy_start.month else fy_start.year
            else:
                yr = getdate().year

            last_day = calendar.monthrange(yr, m)[1]
            month_start_date = f"{yr}-{m:02d}-01"
            month_end_date = f"{yr}-{m:02d}-{last_day:02d}"
            billing_month = f"{calendar.month_name[m]} {yr}"

    # 2. Fallback to run_id if month not explicitly passed
    if not month_start_date and run_id and frappe.db.exists("Maintenance Billing Run", run_id):
        run = frappe.get_doc("Maintenance Billing Run", run_id)
        posting_date = run.posting_date
        billing_month = run.billing_month or run.name
        if not company:
            company = run.company
        if posting_date:
            month_start_date = str(get_first_day(posting_date))
            month_end_date = str(get_last_day(posting_date))

    # 3. Final fallback to current month
    if not month_start_date or not month_end_date:
        today_date = today()
        month_start_date = str(get_first_day(today_date))
        month_end_date = str(get_last_day(today_date))
        if not billing_month:
            billing_month = format_date(month_start_date, "MMMM YYYY")

    # Build SQL conditions dynamically
    conditions = [
        "ge.is_cancelled = 0",
        "acc.root_type IN ('Expense', 'Income')",
        "ge.company = %s",
        "ge.posting_date BETWEEN %s AND %s"
    ]
    values = [company, month_start_date, month_end_date]

    if specific_cost_center and specific_cost_center.strip() and specific_cost_center != "All Common Cost Centers":
        conditions.append("ge.cost_center = %s")
        values.append(specific_cost_center.strip())
    else:
        # Combined common cost centers
        conditions.append(
            "(cc.name LIKE '%%Common%%' OR cc.cost_center_name LIKE '%%Common%%' OR cc.parent_cost_center LIKE '%%Common%%')"
        )

    where_clause = " AND ".join(conditions)

    # Aggregate gross debits (for Expense) or credits (for Income)
    query = f"""
        SELECT 
            ge.account,
            acc.account_name,
            acc.root_type,
            SUM(CASE WHEN acc.root_type = 'Income' THEN ge.credit ELSE ge.debit END) as total_gross_amount
        FROM `tabGL Entry` ge
        JOIN `tabAccount` acc ON ge.account = acc.name
        JOIN `tabCost Center` cc ON ge.cost_center = cc.name
        WHERE {where_clause}
        GROUP BY ge.account, acc.account_name, acc.root_type
        HAVING total_gross_amount > 0
        ORDER BY total_gross_amount DESC, ge.account ASC
    """

    common_gl_entries = frappe.db.sql(query, tuple(values), as_dict=True)

    formatted_entries = []
    grand_total_gross = 0.0

    for entry in common_gl_entries:
        gross_amt = flt(entry.total_gross_amount, 2)
        grand_total_gross += gross_amt
        formatted_entries.append({
            "account": entry.account,
            "account_name": entry.account_name or entry.account,
            "root_type": entry.root_type or "Expense",
            "total_gross_debit": gross_amt,
            "formatted_gross_debit": fmt_money(gross_amt, currency=currency),
        })

    return {
        "run_id": run_id or "",
        "specific_cost_center": specific_cost_center or "",
        "billing_month": billing_month,
        "from_date": format_date(month_start_date) if month_start_date else "-",
        "to_date": format_date(month_end_date) if month_end_date else "-",
        "raw_from_date": month_start_date,
        "raw_to_date": month_end_date,
        "company": company,
        "currency": currency,
        "grand_total_gross": flt(grand_total_gross, 2),
        "formatted_grand_total_gross": fmt_money(grand_total_gross, currency=currency),
        "entries": formatted_entries,
        "count": len(formatted_entries),
    }




@frappe.whitelist()
def get_billing_run_blocks(run_id):
    """
    Level 1 Drill-Down: Fetches all Blocks, their calculated UDS, expenses,
    and rates from the Maintenance Block Details child table for a specific run.
    Returns the month's Total Society Expense, Complex UDS, and Comparative Rate/UDS
    for the compact modal header.
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and authorized society members can view maintenance run details."),
            frappe.PermissionError,
        )

    if not frappe.db.exists("Maintenance Billing Run", run_id):
        frappe.throw(_("Maintenance Billing Run {0} not found.").format(run_id), frappe.DoesNotExistError)

    run = frappe.get_doc("Maintenance Billing Run", run_id)
    currency = (
        frappe.db.get_value("Company", run.company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    flat_number = resident_info.get("flat")
    user_block = None
    user_uds = 0.0
    if flat_number and flat_number != "Office / Administration":
        flat_doc = frappe.db.get_value(
            "Customer",
            flat_number,
            ["custom_block", "custom_uds"],
            as_dict=True,
        )
        if flat_doc:
            user_block = flat_doc.custom_block
            user_uds = flt(flat_doc.custom_uds)

    blocks = []
    total_run_expense = 0.0
    total_run_uds = 0.0
    total_run_sba = 0.0

    # Fetch block master metadata to determine flat_type, per-flat UDS, and Super Builtup Area (square_feet)
    block_records = frappe.get_all(
        "Block",
        fields=["name", "flat_type", "uds", "square_feet", "number_of_flats"],
        order_by="name asc",
    )
    block_info_map = {
        b.name: {
            "flat_type": b.flat_type or "",
            "flat_uds": flt(b.uds),
            "flat_sba": flt(b.square_feet),
            "number_of_flats": b.number_of_flats or 0,
        }
        for b in block_records
    }

    user_sba = 0.0
    if user_block and user_block in block_info_map:
        user_sba = block_info_map[user_block]["flat_sba"]

    for row in run.get("block_details", []):
        total_exp = flt(row.total_expense)
        block_uds = flt(row.total_block_uds)
        rate_uds = flt(row.rate_per_uds, 6)
        total_run_expense += total_exp
        total_run_uds += block_uds

        b_meta = block_info_map.get(row.block, {})
        flat_type = b_meta.get("flat_type", "")
        per_flat_uds = b_meta.get("flat_uds", 0.0)
        per_flat_sba = b_meta.get("flat_sba", 0.0)
        num_flats = b_meta.get("number_of_flats", 0)

        # If per_flat_uds wasn't in Block record, try dividing total_block_uds / number_of_flats
        if per_flat_uds <= 0 and num_flats > 0:
            per_flat_uds = flt(block_uds / num_flats, 2)

        total_block_sba = flt(per_flat_sba * num_flats, 2)
        total_run_sba += total_block_sba

        rate_sba = flt(total_exp / total_block_sba, 6) if total_block_sba > 0 else 0.0

        is_user_block = (row.block == user_block)
        resident_share = flt(rate_uds * user_uds, 2) if (is_user_block and user_uds > 0) else None

        flat_maintenance = flt(rate_uds * per_flat_uds, 2) if per_flat_uds > 0 else 0.0

        blocks.append({
            "block": row.block,
            "cost_center": row.cost_center,
            "total_expense": total_exp,
            "formatted_total_expense": fmt_money(total_exp, currency=currency),
            "total_block_uds": block_uds,
            "total_block_sba": total_block_sba,
            "rate_per_uds": rate_uds,
            "rate_per_sba": rate_sba,
            "formatted_rate_per_uds": f"{flt(rate_uds, 4)} / sqft",
            "formatted_rate_per_sba": f"{flt(rate_sba, 4)} / sqft",
            "flat_type": flat_type,
            "flat_uds": per_flat_uds,
            "flat_sba": per_flat_sba,
            "flat_maintenance": flat_maintenance,
            "formatted_flat_maintenance": fmt_money(flat_maintenance, currency=currency),
            "is_user_block": is_user_block,
            "resident_share": resident_share,
            "formatted_resident_share": fmt_money(resident_share, currency=currency) if resident_share is not None else None,
        })

    # Calculate actual society-wide expense from GL for this month
    start_date = get_first_day(run.posting_date)
    end_date = get_last_day(run.posting_date)

    gl_expense_res = frappe.db.sql(
        """
        SELECT (SUM(ge.debit) - SUM(ge.credit)) as total_expense
        FROM `tabGL Entry` ge
        JOIN `tabAccount` acc ON ge.account = acc.name
        WHERE ge.company = %s
          AND ge.is_cancelled = 0
          AND acc.root_type = 'Expense'
          AND ge.posting_date BETWEEN %s AND %s
        """,
        (run.company, start_date, end_date),
        as_dict=True,
    )
    society_expense = flt(gl_expense_res[0].total_expense) if gl_expense_res else 0.0
    if society_expense <= 0:
        society_expense = total_run_expense

    comparative_rate_uds = flt(society_expense / total_run_uds, 4) if total_run_uds > 0 else 0.0
    comparative_rate_sba = flt(society_expense / total_run_sba, 4) if total_run_sba > 0 else 0.0

    user_block_rate = None
    user_block_rate_sba = None
    if user_block:
        for b in blocks:
            if b["block"] == user_block:
                user_block_rate = flt(b["rate_per_uds"], 4)
                user_block_rate_sba = flt(b["rate_per_sba"], 4)
                break

    # Standard flat type names: 1 BHK -> A Type, 2 BHK -> B Type, 3 BHK -> C Type, 4 BHK -> D Type
    type_display_names = {
        "1 BHK": "A Type",
        "2 BHK": "B Type",
        "3 BHK": "C Type",
        "4 BHK": "D Type",
    }

    # Precompute Single-Tier Flat Type comparison for the 4 distinct property types
    flat_type_comparison = []
    seen_types = {}
    for b in block_records:
        raw_type = b.flat_type or b.name
        display_name = type_display_names.get(raw_type, raw_type)
        f_uds = flt(b.uds)
        f_sba = flt(b.square_feet)
        if display_name not in seen_types:
            seen_types[display_name] = {
                "flat_type": display_name,
                "raw_type": raw_type,
                "uds": f_uds,
                "sba": f_sba,
                "blocks": [b.name],
            }
        else:
            seen_types[display_name]["blocks"].append(b.name)

    for t_name, t_info in sorted(seen_types.items(), key=lambda x: x[1]["uds"]):
        t_uds = t_info["uds"]
        t_sba = t_info["sba"]
        single_tier_maint_uds = flt(comparative_rate_uds * t_uds, 2)
        single_tier_maint_sba = flt(comparative_rate_sba * t_sba, 2)
        flat_type_comparison.append({
            "flat_type": t_name,
            "raw_type": t_info["raw_type"],
            "uds": t_uds,
            "sba": t_sba,
            "blocks": ", ".join(t_info["blocks"]),
            "rate_per_uds": comparative_rate_uds,
            "rate_per_sba": comparative_rate_sba,
            "total_maintenance_uds": single_tier_maint_uds,
            "total_maintenance_sba": single_tier_maint_sba,
            "formatted_total_maintenance_uds": fmt_money(single_tier_maint_uds, currency=currency),
            "formatted_total_maintenance_sba": fmt_money(single_tier_maint_sba, currency=currency),
            "formula_uds": f"₹ {comparative_rate_uds:.4f} × {t_uds} = {fmt_money(single_tier_maint_uds, currency=currency)}",
            "formula_sba": f"₹ {comparative_rate_sba:.4f} × {t_sba} = {fmt_money(single_tier_maint_sba, currency=currency)}",
        })

    return {
        "run_id": run.name,
        "billing_month": run.billing_month,
        "posting_date": format_date(run.posting_date) if run.posting_date else "-",
        "raw_posting_date": str(run.posting_date),
        "start_date": str(start_date),
        "end_date": str(end_date),
        "company": run.company,
        "currency": currency,
        "total_billed_amount": flt(run.total_billed_amount),
        "formatted_total_billed_amount": fmt_money(run.total_billed_amount or total_run_expense, currency=currency),
        "total_run_expense": flt(total_run_expense, 2),
        "formatted_total_run_expense": fmt_money(total_run_expense, currency=currency),
        "total_run_uds": flt(total_run_uds, 2),
        "total_run_sba": flt(total_run_sba, 2),
        "formatted_complex_uds": f"{total_run_uds:,.2f} sqft",
        "formatted_complex_sba": f"{total_run_sba:,.2f} sqft",
        "user_block": user_block,
        "user_uds": user_uds,
        "user_sba": user_sba,
        "user_block_rate": user_block_rate,
        "user_block_rate_sba": user_block_rate_sba,
        "total_society_expense": society_expense,
        "formatted_society_expense": fmt_money(society_expense, currency=currency),
        "comparative_rate_uds": comparative_rate_uds,
        "comparative_rate_sba": comparative_rate_sba,
        "formatted_comparative_rate_uds": f"₹ {comparative_rate_uds:.4f} / sqft",
        "formatted_comparative_rate_sba": f"₹ {comparative_rate_sba:.4f} / sqft",
        "flat_type_comparison": flat_type_comparison,
        "blocks": blocks,
    }


@frappe.whitelist()
def get_block_gl_entries(block_name, cost_center=None, run_id=None, from_date=None, to_date=None):
    """
    Level 2 Drill-Down: Fetches the General Ledger (GL Entry) breakdown
    for a specific Block's Cost Center during a specific billing month or date range.
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and authorized members can view GL entries."),
            frappe.PermissionError,
        )

    company = None
    billing_month = None

    if run_id and frappe.db.exists("Maintenance Billing Run", run_id):
        run = frappe.get_doc("Maintenance Billing Run", run_id)
        company = run.company
        billing_month = run.billing_month
        if not from_date or not to_date:
            from_date = str(get_first_day(run.posting_date))
            to_date = str(get_last_day(run.posting_date))

        if not cost_center:
            for row in run.get("block_details", []):
                if row.block == block_name:
                    cost_center = row.cost_center
                    break

    if not cost_center:
        cost_center = frappe.db.get_value("Block", block_name, "cost_center")
    if not cost_center:
        frappe.throw(
            _("Could not determine Cost Center for Block {0}.").format(block_name),
            frappe.ValidationError,
        )

    if not company:
        company = (
            frappe.db.get_value("Cost Center", cost_center, "company")
            or frappe.db.get_single_value("Global Defaults", "default_company")
        )

    if not from_date or not to_date:
        today_date = today()
        from_date = str(get_first_day(today_date))
        to_date = str(get_last_day(today_date))

    gl_entries = frappe.db.sql(
        """
        SELECT 
            ge.account,
            acc.account_name,
            acc.root_type,
            SUM(ge.debit) as total_debit,
            SUM(ge.credit) as total_credit,
            (SUM(ge.debit) - SUM(ge.credit)) as net_amount
        FROM `tabGL Entry` ge
        JOIN `tabAccount` acc ON ge.account = acc.name
        WHERE ge.cost_center = %s
          AND ge.company = %s
          AND ge.is_cancelled = 0
          AND acc.root_type IN ('Expense', 'Income')
          AND ge.posting_date BETWEEN %s AND %s
        GROUP BY ge.account, acc.account_name, acc.root_type
        ORDER BY net_amount DESC, ge.account ASC
        """,
        (cost_center, company, from_date, to_date),
        as_dict=True,
    )

    currency = (
        frappe.db.get_value("Company", company, "default_currency")
        or frappe.db.get_default("currency")
        or "INR"
    )

    formatted_entries = []
    total_expense = 0.0

    for entry in gl_entries:
        net = flt(entry.net_amount)
        if abs(net) < 0.001:
            continue
        total_expense += net
        formatted_entries.append({
            "account": entry.account,
            "account_name": entry.account_name or entry.account,
            "root_type": entry.root_type,
            "total_debit": flt(entry.total_debit),
            "total_credit": flt(entry.total_credit),
            "net_amount": net,
            "formatted_net_amount": fmt_money(net, currency=currency),
            "formatted_debit": fmt_money(entry.total_debit, currency=currency),
            "formatted_credit": fmt_money(entry.total_credit, currency=currency),
        })

    return {
        "block": block_name,
        "cost_center": cost_center,
        "run_id": run_id or "",
        "billing_month": billing_month or "",
        "from_date": format_date(from_date) if from_date else "-",
        "to_date": format_date(to_date) if to_date else "-",
        "company": company,
        "currency": currency,
        "total_expense": flt(total_expense, 2),
        "formatted_total_expense": fmt_money(total_expense, currency=currency),
        "entries": formatted_entries,
    }


@frappe.whitelist()
def get_maintenance_run_gl_breakdown(run_id, block_name):
    return get_block_gl_entries(block_name=block_name, run_id=run_id)


@frappe.whitelist()
def get_purchase_invoice_details(invoice_name):
    """
    Fetches and returns detailed Item child records and Taxes child records
    for a specific Purchase Invoice to provide transparency directly on screen.
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _("Access Denied: Only active residents and authorized members can view invoice details."),
            frappe.PermissionError,
        )

    if not frappe.db.exists("Purchase Invoice", invoice_name):
        frappe.throw(_("Purchase Invoice {0} not found.").format(invoice_name), frappe.DoesNotExistError)

    inv = frappe.get_doc("Purchase Invoice", invoice_name)
    currency = inv.currency or "INR"

    items = []
    for item in inv.get("items", []):
        items.append({
            "item_code": item.item_code,
            "item_name": item.item_name or item.item_code,
            "description": item.description or "",
            "qty": flt(item.qty),
            "rate": flt(item.rate),
            "amount": flt(item.amount),
            "formatted_rate": fmt_money(item.rate, currency=currency),
            "formatted_amount": fmt_money(item.amount, currency=currency),
            "cost_center": item.cost_center or "-",
            "uom": item.uom or "",
        })

    taxes = []
    for tax in inv.get("taxes", []):
        taxes.append({
            "account_head": tax.account_head,
            "description": tax.description or tax.account_head,
            "rate": flt(tax.rate),
            "tax_amount": flt(tax.tax_amount),
            "formatted_tax_amount": fmt_money(tax.tax_amount, currency=currency),
            "cost_center": tax.cost_center or "-",
        })

    return {
        "name": inv.name,
        "supplier": inv.supplier,
        "supplier_name": inv.supplier_name or inv.supplier,
        "posting_date": format_date(inv.posting_date) if inv.posting_date else "-",
        "due_date": format_date(inv.due_date) if inv.due_date else "-",
        "bill_no": inv.bill_no or "-",
        "bill_date": format_date(inv.bill_date) if inv.bill_date else "-",
        "status": inv.status,
        "currency": currency,
        "net_total": flt(inv.net_total),
        "formatted_net_total": fmt_money(inv.net_total, currency=currency),
        "total_taxes_and_charges": flt(inv.total_taxes_and_charges),
        "formatted_total_taxes": fmt_money(inv.total_taxes_and_charges, currency=currency),
        "grand_total": flt(inv.grand_total),
        "formatted_grand_total": fmt_money(inv.grand_total, currency=currency),
        "remarks": inv.remarks or "",
        "items": items,
        "taxes": taxes,
    }


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
    """
    has_access, resident_info = check_resident_access()
    if not has_access:
        frappe.throw(
            _(
                "Access Denied: Only active residents and authorized society members can view financial reports."
            ),
            frappe.PermissionError,
        )

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

    if not company:
        company = (
            frappe.db.get_single_value("Global Defaults", "default_company")
            or frappe.db.get_value("Company", {}, "name")
        )

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
