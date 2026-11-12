import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, nowtime, get_datetime, time_diff_in_hours


@frappe.whitelist()
def log_block_water(
    block: str,
    domestic_level_ft: float = None,
    domestic_photo: str = None,
    domestic_pump_action: str = None,  # 'start', 'stop', 'running', 'off'
    flush_level_ft: float = None,
    flush_photo: str = None,
    flush_pump_action: str = None,
    notes: str = None,
    source: str = "Manual Staff Entry"
) -> dict:
    """
    Records daily water sump levels and OHT pump switching for a residential block.
    Can be called by mobile operator or IoT telemetry webhooks.
    """
    if not block or not frappe.db.exists("Block", block):
        frappe.throw(_("Invalid residential block: {0}").format(block))

    today = nowdate()
    now_dt = now_datetime()
    user = frappe.session.user

    # Find if there is an active log for today to update, or create a new entry
    existing_log = frappe.db.get_value(
        "Block Water Log",
        {"block": block, "log_date": today},
        ["name", "domestic_pump_status", "domestic_pump_start", "flush_pump_status", "flush_pump_start"],
        as_dict=True
    )

    if existing_log:
        doc = frappe.get_doc("Block Water Log", existing_log.name)
    else:
        doc = frappe.get_doc({
            "doctype": "Block Water Log",
            "block": block,
            "log_date": today,
            "log_time": nowtime(),
            "logged_by": user,
            "reading_source": source
        })

    # Update domestic sump readings
    if domestic_level_ft is not None:
        doc.domestic_level_ft = float(domestic_level_ft)
        # Approximate standard sump capacity % (assume 8.0 ft max capacity)
        doc.domestic_capacity_pct = min(100.0, round((float(domestic_level_ft) / 8.0) * 100, 1))

    if domestic_photo:
        doc.domestic_photo = domestic_photo

    # Handle Domestic Pump actions
    if domestic_pump_action == "start":
        doc.domestic_pump_status = "Running"
        doc.domestic_pump_start = now_dt
        doc.domestic_pump_stop = None
    elif domestic_pump_action == "stop":
        doc.domestic_pump_status = "Off"
        doc.domestic_pump_stop = now_dt
        if doc.domestic_pump_start:
            doc.domestic_run_hours = round(time_diff_in_hours(now_dt, doc.domestic_pump_start), 2)
    elif domestic_pump_action:
        doc.domestic_pump_status = domestic_pump_action.capitalize()

    # Update flush sump readings
    if flush_level_ft is not None:
        doc.flush_level_ft = float(flush_level_ft)
        doc.flush_capacity_pct = min(100.0, round((float(flush_level_ft) / 7.0) * 100, 1))

    if flush_photo:
        doc.flush_photo = flush_photo

    # Handle Flush Pump actions
    if flush_pump_action == "start":
        doc.flush_pump_status = "Running"
        doc.flush_pump_start = now_dt
        doc.flush_pump_stop = None
    elif flush_pump_action == "stop":
        doc.flush_pump_status = "Off"
        doc.flush_pump_stop = now_dt
        if doc.flush_pump_start:
            doc.flush_run_hours = round(time_diff_in_hours(now_dt, doc.flush_pump_start), 2)
    elif flush_pump_action:
        doc.flush_pump_status = flush_pump_action.capitalize()

    if notes:
        doc.notes = notes

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "log_id": doc.name,
        "block": doc.block,
        "domestic_level_ft": doc.domestic_level_ft,
        "flush_level_ft": doc.flush_level_ft,
        "is_low_level_alert": doc.is_low_level_alert,
        "message": _("Water log recorded for Block {0}.").format(doc.block)
    }


@frappe.whitelist()
def get_daily_water_summary(date: str = None) -> dict:
    """
    Returns latest water levels and pump status across all 10 residential blocks.
    Used for Agency Portal, Committee Dashboard, and Telegram Bot.
    """
    target_date = date or nowdate()
    blocks = frappe.get_all("Block", fields=["name", "block_name"], order_by="name asc")
    logs = frappe.get_all(
        "Block Water Log",
        filters={"log_date": target_date},
        fields=[
            "name", "block", "log_date", "log_time", "reading_source",
            "domestic_level_ft", "domestic_capacity_pct", "domestic_photo", "domestic_pump_status", "domestic_run_hours",
            "flush_level_ft", "flush_capacity_pct", "flush_photo", "flush_pump_status", "flush_run_hours",
            "is_low_level_alert", "notes"
        ]
    )
    log_by_block = {l.block: l for l in logs}

    block_data = []
    total_domestic_hours = 0.0
    total_flush_hours = 0.0
    low_alert_blocks = []

    for b in blocks:
        l = log_by_block.get(b.name)
        item = {
            "block": b.name,
            "has_reading": bool(l),
            "log_id": l.name if l else None,
            "log_time": str(l.log_time)[:5] if (l and l.log_time) else None,
            "domestic_level_ft": l.domestic_level_ft if l else 0.0,
            "domestic_capacity_pct": l.domestic_capacity_pct if l else 0.0,
            "domestic_photo": l.domestic_photo if l else None,
            "domestic_pump_status": l.domestic_pump_status if l else "Off",
            "domestic_run_hours": l.domestic_run_hours if l else 0.0,
            "flush_level_ft": l.flush_level_ft if l else 0.0,
            "flush_capacity_pct": l.flush_capacity_pct if l else 0.0,
            "flush_photo": l.flush_photo if l else None,
            "flush_pump_status": l.flush_pump_status if l else "Off",
            "flush_run_hours": l.flush_run_hours if l else 0.0,
            "is_low_level_alert": bool(l and l.is_low_level_alert),
            "notes": l.notes if l else ""
        }
        if l:
            total_domestic_hours += float(l.domestic_run_hours or 0)
            total_flush_hours += float(l.flush_run_hours or 0)
            if l.is_low_level_alert:
                low_alert_blocks.append(b.name)

        block_data.append(item)

    # Telegram bot summary text
    lines = [f"💧 *KVC3 Daily Water Status ({target_date})*"]
    if low_alert_blocks:
        lines.append(f"⚠️ *LOW WATER WARNING:* Blocks `{', '.join(low_alert_blocks)}`")

    for bd in block_data:
        dom_status = f"{bd['domestic_level_ft']}ft ({int(bd['domestic_capacity_pct'])}%)" if bd['has_reading'] else "No Log"
        flush_status = f"{bd['flush_level_ft']}ft ({int(bd['flush_capacity_pct'])}%)" if bd['has_reading'] else "No Log"
        pump_icon = "⚡" if (bd['domestic_pump_status'] == "Running" or bd['flush_pump_status'] == "Running") else "⚪"
        lines.append(f"• *Block {bd['block']}*: Dom: `{dom_status}` | Flush: `{flush_status}` {pump_icon}")

    lines.append(f"\n⏱️ Total Pump Run Hours Today: *{round(total_domestic_hours + total_flush_hours, 1)} hrs*")

    # Add Water Tanker Deliveries for today
    tankers = frappe.get_all(
        "Water Tanker Log",
        filters={"delivery_date": target_date},
        fields=["name", "delivery_time", "supplier", "vehicle_number", "capacity_kl", "target_block", "target_sump", "challan_photo", "tanker_photo", "cost_per_tanker"]
    )
    total_tanker_kl = sum(float(t.capacity_kl or 0) for t in tankers)
    total_tanker_cost = sum(float(t.cost_per_tanker or 0) for t in tankers)

    if tankers:
        lines.append(f"\n🚚 *Water Tanker Inflow:* {len(tankers)} tankers ({round(total_tanker_kl, 1)} kL total)")

    return {
        "date": target_date,
        "blocks": block_data,
        "total_logged_blocks": len(logs),
        "total_domestic_run_hours": round(total_domestic_hours, 2),
        "total_flush_run_hours": round(total_flush_hours, 2),
        "low_alert_blocks": low_alert_blocks,
        "tankers": tankers,
        "tanker_count": len(tankers),
        "total_tanker_kl": round(total_tanker_kl, 1),
        "total_tanker_cost": round(total_tanker_cost, 2),
        "summary_text": "\n".join(lines)
    }


@frappe.whitelist()
def log_water_tanker(
    delivery_date: str = None,
    vehicle_number: str = None,
    capacity_kl: float = 36.0,
    target_sump: str = "Domestic Sump",
    target_block: str = None,
    supplier: str = None,
    delivery_challan_no: str = None,
    cost_per_tanker: float = None,
    challan_photo: str = None,
    tanker_photo: str = None,
    water_quality_check: str = "Clear & Odorless",
    remarks: str = None
) -> dict:
    """
    Records private water tanker deliveries hired due to poor borewell yields.
    """
    if not delivery_date:
        delivery_date = nowdate()

    if not vehicle_number:
        frappe.throw(_("Vehicle number is required"))

    doc = frappe.get_doc({
        "doctype": "Water Tanker Log",
        "delivery_date": delivery_date,
        "delivery_time": nowtime(),
        "supplier": supplier or "Private Water Vendor",
        "delivery_challan_no": delivery_challan_no,
        "vehicle_number": vehicle_number.strip().upper(),
        "capacity_kl": float(capacity_kl or 36.0),
        "cost_per_tanker": float(cost_per_tanker or 0.0),
        "target_block": target_block if target_block else None,
        "target_sump": target_sump or "Domestic Sump",
        "water_quality_check": water_quality_check or "Acceptable",
        "challan_photo": challan_photo,
        "tanker_photo": tanker_photo,
        "remarks": remarks
    })

    # Link staff if logged by an agency or security user
    if frappe.session.user != "Administrator":
        staff = frappe.db.get_value("Facility Staff", {"user": frappe.session.user}, "name")
        if staff:
            doc.received_by_staff = staff

    doc.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "message": f"Water Tanker {doc.vehicle_number} ({doc.capacity_kl} kL) logged successfully.",
        "tanker_log_id": doc.name
    }

