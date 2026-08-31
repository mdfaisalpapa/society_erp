// Copyright (c) 2026, Mohammed Faisal and contributors
// For license information, please see license.txt

frappe.ui.form.on("Maintenance Billing Run", {
	refresh(frm) {
        // 1. Fetch Balances Button (Only show if document is saved as Draft)
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__('Fetch Balances'), function() {
                frappe.call({
                    method: 'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.fetch_and_calculate_blocks',
                    args: {
                        doc_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: "Fetching GL Balances...",
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('Block details calculated successfully!')
                            });
                            frm.reload_doc(); // Reloads the page to show the populated table
                        }
                    }
                });
            }).addClass('btn-primary');
        }
	},
});
