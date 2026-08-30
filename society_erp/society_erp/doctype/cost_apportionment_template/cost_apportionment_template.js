frappe.ui.form.on('Cost Apportionment Template', {
    refresh: function(frm) {
        calculate_remaining_percentage(frm);

        // Automatically fetch balance on load if parent cost center exists
        if (frm.doc.company && frm.doc.parent_cost_center && !frm.is_new()) {
            fetch_and_show_balances(frm, true);
        }

        // --- View Balances Button ---
        if (frm.doc.company && frm.doc.parent_cost_center) {
            frm.add_custom_button(__('Check Current Balances'), function() {
                fetch_and_show_balances(frm, false);
            }, __('Actions'));
        }

        // --- Generate Apportionment JE Button ---
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Generate Apportionment JEs'), function() {
                frappe.confirm('Generate new Journal Entries based on these locked rules?', () => {
                    frappe.call({
                        method: 'society_erp.society_erp.doctype.cost_apportionment_template.cost_apportionment_template.generate_apportionment_je',
                        args: { template_name: frm.doc.name },
                        freeze: true,
                        freeze_message: "Generating Apportionment Batch...",
                        callback: function(r) {
                            if (!r.exc && r.message) {
                                // Create clickable links for every generated JV
                                let jv_links = r.message.map(jv => `<a href="/app/journal-entry/${jv}"><b>${jv}</b></a>`).join("<br>");
                                
                                frappe.msgprint({
                                    title: __('Success'),
                                    indicator: 'green',
                                    message: `Draft Journal Entries successfully generated for each amenity:<br><br>${jv_links}`
                                });
                            }
                        }
                    });
                });
            }).addClass('btn-primary');
        }
    },
    
    parent_cost_center: function(frm) {
        if (frm.doc.company && frm.doc.parent_cost_center) {
            fetch_and_show_balances(frm, true);
        }
    },
    
    validate: function(frm) {
        let total = 0;
        if (frm.doc.allocation_rules) {
            frm.doc.allocation_rules.forEach(row => {
                total += flt(row.percentage);
            });
        }
        total = flt(total, 3);
        
        if (total !== 100.000) {
            frappe.msgprint({
                title: __('Validation Error'),
                indicator: 'red',
                message: __('The total allocation percentage must be exactly 100%. Currently, it is <b>' + total + '%</b>.')
            });
            frappe.validated = false;
        }
    }
});

frappe.ui.form.on('Cost Apportionment Template', {
    allocation_rules_add: function(frm) { calculate_remaining_percentage(frm); },
    allocation_rules_remove: function(frm) { calculate_remaining_percentage(frm); }
});

frappe.ui.form.on('Cost Apportionment Target', {
    percentage: function(frm, cdt, cdn) {
        calculate_remaining_percentage(frm);
    }
});

function fetch_and_show_balances(frm, silent = false) {
    frappe.call({
        method: 'society_erp.society_erp.doctype.cost_apportionment_template.cost_apportionment_template.check_unallocated_balance',
        args: { 
            template_name: frm.doc.name,
            parent_cost_center: frm.doc.parent_cost_center,
            company: frm.doc.company
        },
        freeze: !silent,
        callback: function(r) {
            if (!r.exc) {
                if (!silent) {
                    frappe.msgprint(`Currently unallocated balance: <b>₹${r.message}</b>`);
                }
                frm.set_value('latest_unallocated_balance', r.message);
            }
        }
    });
}

function calculate_remaining_percentage(frm) {
    let total = 0;
    if (frm.doc.allocation_rules) {
        frm.doc.allocation_rules.forEach(row => {
            total += flt(row.percentage);
        });
    }
    
    total = flt(total, 3); 
    let remaining = flt(100 - total, 3);

    frm.dashboard.clear_headline();

    if (remaining === 0) {
        frm.dashboard.set_headline_alert(
            '<div style="color: #155724; font-weight: bold;"><i class="fa fa-check"></i> Allocation is perfectly balanced at 100%. Ready to Save!</div>'
        );
    } else if (remaining > 0) {
        frm.dashboard.set_headline_alert(
            '<div style="color: #856404;"><i class="fa fa-exclamation-triangle"></i> You have <b>' + remaining + '%</b> remaining to allocate.</div>'
        );
    } else {
        frm.dashboard.set_headline_alert(
            '<div style="color: #721c24; font-weight: bold;"><i class="fa fa-times"></i> You have over-allocated by <b>' + Math.abs(remaining) + '%</b>. Please reduce the percentages.</div>'
        );
    }
}
