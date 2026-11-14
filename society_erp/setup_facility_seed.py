import base64
import json
import os
import frappe
from frappe.utils import get_site_path


AGENCY_NAME = "Premier Security & Facility Services"

REQUIRED_SHIFTS = [
    "Security & Maintenance Shift (Day)",
    "Security & Maintenance Shift (Night)",
    "Housekeeping Shift (Morning)",
]

OBSOLETE_SHIFTS = [
    "Security Shift A",
    "Security Shift B",
    "Security Shift C",
]

REQUIRED_DUTY_POSTS = [
    "A1 Block - Housekeeping",
    "A2 Block - Housekeeping",
    "B1 Block - Housekeeping",
    "B2 Block - Housekeeping",
    "C1 Block - Housekeeping",
    "C2 Block - Housekeeping",
    "C3 Block - Housekeeping",
    "D1 Block - Housekeeping",
    "D2 Block - Housekeeping",
    "D3 Block - Housekeeping",
    "Main Gate - Security Post",
    "Back Gate - Security Post",
    "Roads & Perimeter Patrol",
    "Community Center & Gym",
    "WTP & STP Plant Operations",
]


def audit_seed_status():
    """
    Checks if all required records exist and are correctly configured.
    Returns: (is_fully_seeded: bool, missing_summary: dict)
    """
    missing = {
        "agency": False,
        "missing_shifts": [],
        "obsolete_active_shifts": [],
        "missing_duty_posts": [],
        "missing_vapid_keys": False,
    }

    # 1. Agency Check
    agency = frappe.db.get_value(
        "Facility Agency", AGENCY_NAME, ["name", "contract_status"], as_dict=True
    )
    if not agency or agency.contract_status != "Active":
        missing["agency"] = True

    # 2. Shift Checks
    for s in REQUIRED_SHIFTS:
        shift_enabled = frappe.db.get_value("Facility Shift", s, "enabled")
        if shift_enabled is None or shift_enabled != 1:
            missing["missing_shifts"].append(s)

    for old_s in OBSOLETE_SHIFTS:
        if frappe.db.get_value("Facility Shift", old_s, "enabled") == 1:
            missing["obsolete_active_shifts"].append(old_s)

    # 3. Duty Posts Check
    for post in REQUIRED_DUTY_POSTS:
        if not frappe.db.exists("Facility Duty Post", post):
            missing["missing_duty_posts"].append(post)

    # 4. VAPID Keys Check
    config_path = get_site_path("site_config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
            if (
                "push_vapid_public_key" not in config
                or "push_vapid_private_key" not in config
            ):
                missing["missing_vapid_keys"] = True

    is_fully_seeded = not any([
        missing["agency"],
        missing["missing_shifts"],
        missing["obsolete_active_shifts"],
        missing["missing_duty_posts"],
        missing["missing_vapid_keys"],
    ])

    return is_fully_seeded, missing


def run_all_seeds(force=False):
    """
    Entry point. Checks first before executing any writes.
    Pass force=True to bypass pre-flight check and re-apply.
    """
    print("\n🔍 Running Pre-Flight Check for Foundational Records...")
    print("-" * 60)

    is_seeded, missing = audit_seed_status()

    if is_seeded and not force:
        print("✅ ALL FOUNDATIONAL RECORDS ARE ALREADY PRESENT & CONFIGURED:")
        print(f"  • Facility Agency    : '{AGENCY_NAME}' is Active")
        print(
            f"  • Facility Shifts    : All {len(REQUIRED_SHIFTS)} 12h/9h shifts enabled; obsolete 8h shifts disabled"
        )
        print(f"  • Facility Duty Posts: All {len(REQUIRED_DUTY_POSTS)} posts exist")
        print("  • VAPID Push Keys    : Present in site_config.json")
        print("-" * 60)
        print("⏩ No database changes needed. Exiting cleanly.\n")
        return

    print("⚠️ Missing or incomplete configuration detected:")
    if missing["agency"]:
        print(f"  [!] Agency missing or not active: {AGENCY_NAME}")
    if missing["missing_shifts"]:
        print(f"  [!] Missing/Disabled shifts: {missing['missing_shifts']}")
    if missing["obsolete_active_shifts"]:
        print(f"  [!] Obsolete shifts still active: {missing['obsolete_active_shifts']}")
    if missing["missing_duty_posts"]:
        print(
            f"  [!] Missing duty posts ({len(missing['missing_duty_posts'])}): {missing['missing_duty_posts']}"
        )
    if missing["missing_vapid_keys"]:
        print("  [!] Missing VAPID push notification keys in site_config.json")

    print("\n🛠️ Seeding missing records now...")
    print("-" * 60)

    company = _get_default_company()
    seed_cost_centers(company)
    seed_facility_agency(company)
    seed_facility_shifts()
    seed_duty_posts(company)
    ensure_vapid_keys()

    frappe.db.commit()
    print("-" * 60)
    print("🎉 Seeding completed and committed successfully!\n")


def _get_default_company():
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        companies = frappe.get_all("Company", pluck="name", limit=1)
        company = companies[0] if companies else "Kendriya Vihar Chennai 3"
    return company


def seed_facility_agency(company):
    if not frappe.db.exists("Facility Agency", AGENCY_NAME):
        doc = frappe.get_doc({
            "doctype": "Facility Agency",
            "agency_name": AGENCY_NAME,
            "company": company if frappe.db.exists("Company", company) else None,
            "contract_status": "Active",
            "service_types": "Security\nHousekeeping\nTechnical / Plant Maintenance",
            "primary_contact_person": "Operations Supervisor",
            "primary_phone": "9876543210",
            "primary_email": "operations@premierfacility.in",
            "notes": (
                "Primary vendor contracted for security, housekeeping, and technical plant operators."
            ),
        })
        doc.insert(ignore_permissions=True)
        print(f"  ✔ Created Facility Agency: {AGENCY_NAME}")
    else:
        frappe.db.set_value("Facility Agency", AGENCY_NAME, "contract_status", "Active")
        print(f"  ✔ Agency '{AGENCY_NAME}' verified active.")


def seed_facility_shifts():
    shifts = [
        {
            "shift_name": "Security & Maintenance Shift (Day)",
            "start_time": "06:00:00",
            "end_time": "18:00:00",
            "duration_hours": 12.0,
            "is_night_shift": 0,
            "grace_period_mins": 15,
            "enabled": 1,
        },
        {
            "shift_name": "Security & Maintenance Shift (Night)",
            "start_time": "18:00:00",
            "end_time": "06:00:00",
            "duration_hours": 12.0,
            "is_night_shift": 1,
            "grace_period_mins": 15,
            "enabled": 1,
        },
        {
            "shift_name": "Housekeeping Shift (Morning)",
            "start_time": "07:30:00",
            "end_time": "16:30:00",
            "duration_hours": 9.0,
            "is_night_shift": 0,
            "grace_period_mins": 15,
            "enabled": 1,
        },
    ]

    for s in shifts:
        if not frappe.db.exists("Facility Shift", s["shift_name"]):
            frappe.get_doc({"doctype": "Facility Shift", **s}).insert(ignore_permissions=True)
            print(f"  ✔ Created Shift: {s['shift_name']}")
        else:
            frappe.db.set_value("Facility Shift", s["shift_name"], s)
            print(f"  ✔ Updated/Enabled Shift: {s['shift_name']}")

    for old_s in OBSOLETE_SHIFTS:
        if frappe.db.exists("Facility Shift", old_s):
            frappe.db.set_value("Facility Shift", old_s, "enabled", 0)
            print(f"  ⚠ Disabled obsolete shift: {old_s}")


def seed_cost_centers(company):
    if not frappe.db.exists("Company", company):
        return

    company_abbr = frappe.get_value("Company", company, "abbr") or "CHCR"
    main_group = f"{company} - {company_abbr}"
    if not frappe.db.exists("Cost Center", main_group):
        root_cc = frappe.get_all(
            "Cost Center",
            filters={"company": company, "is_group": 1, "parent_cost_center": None},
            pluck="name",
            limit=1,
        )
        main_group = root_cc[0] if root_cc else None

    common_group = f"Common - {company_abbr}"
    if main_group and not frappe.db.exists("Cost Center", common_group):
        try:
            frappe.get_doc({
                "doctype": "Cost Center",
                "cost_center_name": "Common",
                "company": company,
                "is_group": 1,
                "parent_cost_center": main_group,
            }).insert(ignore_permissions=True)
        except Exception:
            pass

    cost_centers = [
        ("A1 Block", main_group),
        ("A2 Block", main_group),
        ("B1 Block", main_group),
        ("B2 Block", main_group),
        ("C1 Block", main_group),
        ("C2 Block", main_group),
        ("C3 Block", main_group),
        ("D1 Block", main_group),
        ("D2 Block", main_group),
        ("D3 Block", main_group),
        ("General Common", common_group or main_group),
        ("Community Hall", common_group or main_group),
        ("WTP & STP Operations", common_group or main_group),
    ]

    for name, parent in cost_centers:
        full_name = f"{name} - {company_abbr}"
        if not frappe.db.exists("Cost Center", full_name) and parent:
            try:
                frappe.get_doc({
                    "doctype": "Cost Center",
                    "cost_center_name": name,
                    "company": company,
                    "is_group": 0,
                    "parent_cost_center": parent,
                }).insert(ignore_permissions=True)
                print(f"  ✔ Created Cost Center: {full_name}")
            except Exception:
                pass


def seed_duty_posts(company):
    company_abbr = (
        frappe.get_value("Company", company, "abbr")
        if frappe.db.exists("Company", company)
        else "CHCR"
    )

    posts = [
        {
            "post_name": "A1 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"A1 Block - {company_abbr}",
        },
        {
            "post_name": "A2 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"A2 Block - {company_abbr}",
        },
        {
            "post_name": "B1 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"B1 Block - {company_abbr}",
        },
        {
            "post_name": "B2 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"B2 Block - {company_abbr}",
        },
        {
            "post_name": "C1 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"C1 Block - {company_abbr}",
        },
        {
            "post_name": "C2 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"C2 Block - {company_abbr}",
        },
        {
            "post_name": "C3 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"C3 Block - {company_abbr}",
        },
        {
            "post_name": "D1 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"D1 Block - {company_abbr}",
        },
        {
            "post_name": "D2 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"D2 Block - {company_abbr}",
        },
        {
            "post_name": "D3 Block - Housekeeping",
            "category": "Housekeeping",
            "zone_type": "Residential Block",
            "cost_center": f"D3 Block - {company_abbr}",
        },
        {
            "post_name": "Main Gate - Security Post",
            "category": "Security",
            "zone_type": "Security Gate",
            "cost_center": f"General Common - {company_abbr}",
        },
        {
            "post_name": "Back Gate - Security Post",
            "category": "Security",
            "zone_type": "Security Gate",
            "cost_center": f"General Common - {company_abbr}",
        },
        {
            "post_name": "Roads & Perimeter Patrol",
            "category": "Security",
            "zone_type": "Road & Perimeter",
            "cost_center": f"General Common - {company_abbr}",
        },
        {
            "post_name": "Community Center & Gym",
            "category": "Housekeeping",
            "zone_type": "Common Facility",
            "cost_center": f"Community Hall - {company_abbr}",
        },
        {
            "post_name": "WTP & STP Plant Operations",
            "category": "Technical / Plant",
            "zone_type": "Utility Plant",
            "cost_center": f"WTP & STP Operations - {company_abbr}",
        },
    ]

    for p in posts:
        cc = p["cost_center"] if frappe.db.exists("Cost Center", p["cost_center"]) else None
        if not frappe.db.exists("Facility Duty Post", p["post_name"]):
            frappe.get_doc({
                "doctype": "Facility Duty Post",
                "post_name": p["post_name"],
                "category": p["category"],
                "zone_type": p["zone_type"],
                "cost_center": cc,
                "is_active": 1,
                "target_staff_quota": 1,
            }).insert(ignore_permissions=True)
            print(f"  ✔ Created Duty Post: {p['post_name']}")
        else:
            if cc:
                frappe.db.set_value("Facility Duty Post", p["post_name"], "cost_center", cc)

    if frappe.db.table_exists("Facility Staff"):
        for s in frappe.get_all("Facility Staff", fields=["name", "qr_code_id"]):
            if not s.qr_code_id:
                frappe.db.set_value(
                    "Facility Staff", s.name, "qr_code_id", f"KVC3-STAFF-{s.name}"
                )


def ensure_vapid_keys():
    config_path = get_site_path("site_config.json")
    if not os.path.exists(config_path):
        return

    with open(config_path, "r") as f:
        config = json.load(f)

    if "push_vapid_public_key" not in config or "push_vapid_private_key" not in config:
        config["push_vapid_public_key"] = (
            "BHTbZHxXpRxkRG6HOYLefuIb8ccLoNflB7L6zCVExzl3t0RkJIOfmtNMnIaTVaDKEsq24JoHEpIzHTP-IeWTjaU"
        )
        config["push_vapid_private_key"] = (
            "PaqsjJFTr3kNxzIHxbgmiA3NDr1lFr1urKSOU8O53mQ"
        )
        config["push_vapid_subject"] = "mailto:kvc3aoa@gmail.com"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=1)
        print("  ✔ Injected VAPID keys into site_config.json.")


def create_test_agency_user(email="agency@qpms.in", password=None, full_name="QPMS Agency Supervisor"):
    """
    Provisions a dedicated agency operator account, sets password (generated randomly or from env/parameter),
    assigns the 'Facility Agency Manager' role, and links it to the active Facility Agency.
    """
    import os
    import secrets

    # If no password provided, check env or generate a secure random one
    generated = False
    if not password:
        password = os.environ.get("AGENCY_SEED_PASSWORD")
        if not password:
            password = secrets.token_urlsafe(12)
            generated = True

    print(f"\n[*] Provisioning Agency Operator User: {email}...")

    # 1. Create or update user
    if not frappe.db.exists("User", email):
        user_doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": full_name,
            "enabled": 1,
            "send_welcome_email": 0,
            "user_type": "System User",
            "roles": [{"doctype": "Has Role", "role": "Facility Agency Manager"}]
        })
        user_doc.insert(ignore_permissions=True)
        print(f"  ✔ Created user account: {email}")
    else:
        user_doc = frappe.get_doc("User", email)
        user_doc.enabled = 1
        user_doc.flags.ignore_permissions = True
        roles = [r.role for r in user_doc.roles]
        if "Facility Agency Manager" not in roles:
            user_doc.append("roles", {"doctype": "Has Role", "role": "Facility Agency Manager"})
            user_doc.save(ignore_permissions=True)
            print("  ✔ Assigned 'Facility Agency Manager' role.")
        else:
            print("  ✔ User exists with 'Facility Agency Manager' role.")

    # 2. Set user password
    from frappe.utils.password import update_password
    update_password(email, password)
    print("  ✔ Password updated successfully.")

    # 3. Link this user to the Facility Agency
    if frappe.db.exists("Facility Agency", AGENCY_NAME):
        frappe.db.set_value("Facility Agency", AGENCY_NAME, "portal_user", email)
        print(f"  ✔ Linked {email} as authorized portal user for '{AGENCY_NAME}'.")

    frappe.db.commit()
    print("-" * 60)
    print("🎉 Agency Operator Ready!")
    print(f"   URL      : /agency")
    print(f"   Username : {email}")
    if generated:
        print(f"   Temporary Password (Generated) : {password}")
        print("   ⚠️  Please change this password upon first login or store it securely.")
    else:
        print("   Password set from provided input / environment.")
    print("-" * 60 + "\n")

