import frappe


def create_supplier_and_link():
    sup_name = 'Premier Security & Facility Services'
    if not frappe.db.exists('Supplier', sup_name):
        doc = frappe.get_doc({
            'doctype': 'Supplier',
            'supplier_name': sup_name,
            'supplier_group': 'Services',
            'supplier_type': 'Company',
            'country': 'India'
        })
        doc.insert(ignore_permissions=True)
        print('Created Supplier:', sup_name)

    frappe.db.set_value('Facility Agency', sup_name, 'supplier', sup_name)
    frappe.db.commit()
    print('Linked Supplier to Facility Agency successfully')
