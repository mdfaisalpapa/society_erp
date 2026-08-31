frappe.ui.form.on("Society ERP Settings", {
    refresh(frm) {
        // Only display the button if the item hasn't been mapped yet
        if (!frm.doc.monthly_maintenance_item) {
            frm.add_custom_button(__('Create Maintenance Item'), function() {
                frappe.call({
                    method: "society_erp.society_erp.doctype.society_erp_settings.society_erp_settings.create_maintenance_item",
                    freeze: true,
                    freeze_message: "Generating Service Item...",
                    callback: function(r) {
                        if (r.message) {
                            // Automatically set the linked field and save the form
                            frm.set_value("monthly_maintenance_item", r.message);
                            frm.save();
                            
                            frappe.msgprint({
                                title: __('Success'),
                                indicator: 'green',
                                message: __('Maintenance Item created and linked successfully!')
                            });
                        }
                    }
                }).addClass('btn-primary');
            });
        }
    }
});
