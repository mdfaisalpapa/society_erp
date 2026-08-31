frappe.ui.form.on("Maintenance Billing Run", {
    refresh(frm) {
        // 1. Fetch Balances Button (Only in Draft State)
        if (frm.doc.docstatus === 0 && !frm.is_new()) {
            frm.add_custom_button(__('Fetch Balances'), function() {
                frappe.call({
                    method: 'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.fetch_and_calculate_blocks',
                    args: { doc_name: frm.doc.name },
                    freeze: true,
                    freeze_message: "Fetching GL Balances...",
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('Block details calculated successfully!')
                            });
                            frm.reload_doc();
                        }
                    }
                });
            }).addClass('btn-primary');
        }

        // 2. Invoice Generation Controls (Only in Submitted State)
        if (frm.doc.docstatus === 1) {
            if (frm.doc.generation_status === "Completed") {
                frm.dashboard.add_indicator(__('Invoices Generated'), 'green');
            } else if (frm.doc.generation_status === "Queued") {
                frm.dashboard.add_indicator(__('Generation in Progress (Check Background Jobs)'), 'orange');
            } else {
                // Pending State: Check if auto-generate is off, then show manual button
                frappe.db.get_single_value("Society ERP Settings", "auto_generate_invoices")
                    .then(auto_generate => {
                        if (!auto_generate) {
                            frm.add_custom_button(__('Generate Invoices'), function() {
                                frappe.call({
                                    method: 'society_erp.society_erp.doctype.maintenance_billing_run.maintenance_billing_run.trigger_invoice_generation',
                                    args: { doc_name: frm.doc.name },
                                    freeze: true,
                                    freeze_message: "Queuing Invoices...",
                                    callback: function(r) {
                                        if (!r.exc) {
                                            // Lock the UI immediately by switching status to Queued
                                            frappe.db.set_value('Maintenance Billing Run', frm.doc.name, 'generation_status', 'Queued')
                                                .then(() => {
                                                    frm.reload_doc();
                                                    frappe.msgprint({
                                                        title: __('Success'),
                                                        indicator: 'green',
                                                        message: __('Invoices queued for background generation.')
                                                    });
                                                });
                                        }
                                    }
                                });
                            }).addClass('btn-primary');
                        }
                    });
            }
        }
    }
});
