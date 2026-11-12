import frappe


def seed_duty_posts():
    posts = [
        # 10 Residential Blocks
        {'post_name': 'A1 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'A1 Block - KVC3'},
        {'post_name': 'A2 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'A2 Block - KVC3'},
        {'post_name': 'B1 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'B1 Block - KVC3'},
        {'post_name': 'B2 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'B2 Block - KVC3'},
        {'post_name': 'C1 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'C1 Block - KVC3'},
        {'post_name': 'C2 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'C2 Block - KVC3'},
        {'post_name': 'C3 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'C3 Block - KVC3'},
        {'post_name': 'D1 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'D1 Block - KVC3'},
        {'post_name': 'D2 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'D2 Block - KVC3'},
        {'post_name': 'D3 Block - Housekeeping', 'category': 'Housekeeping', 'zone_type': 'Residential Block', 'cost_center': 'D3 Block - KVC3'},
        
        # Common Security & Infrastructure
        {'post_name': 'Main Gate - Security Post', 'category': 'Security', 'zone_type': 'Security Gate', 'cost_center': 'General Common - KVC3'},
        {'post_name': 'Back Gate - Security Post', 'category': 'Security', 'zone_type': 'Security Gate', 'cost_center': 'General Common - KVC3'},
        {'post_name': 'Roads & Perimeter Patrol', 'category': 'Security', 'zone_type': 'Road & Perimeter', 'cost_center': 'General Common - KVC3'},
        {'post_name': 'Community Center & Gym', 'category': 'Housekeeping', 'zone_type': 'Common Facility', 'cost_center': 'Community Hall - KVC3'},
        {'post_name': 'WTP & STP Plant Operations', 'category': 'Technical / Plant', 'zone_type': 'Utility Plant', 'cost_center': 'WTP & STP Operations - KVC3'},
    ]

    for p in posts:
        if not frappe.db.exists('Facility Duty Post', p['post_name']):
            doc = frappe.get_doc({
                'doctype': 'Facility Duty Post',
                'post_name': p['post_name'],
                'category': p['category'],
                'zone_type': p['zone_type'],
                'cost_center': p['cost_center'],
                'is_active': 1,
                'target_staff_quota': 1
            })
            doc.insert(ignore_permissions=True)
            print(f"Inserted: {p['post_name']}")

    # Update QR codes on existing staff
    all_staff = frappe.get_all('Facility Staff', fields=['name', 'qr_code_id'])
    for s in all_staff:
        qr = f"KVC3-STAFF-{s.name}"
        frappe.db.set_value('Facility Staff', s.name, 'qr_code_id', qr)

    frappe.db.commit()
    print("Seeded duty posts and staff QR codes successfully!")
