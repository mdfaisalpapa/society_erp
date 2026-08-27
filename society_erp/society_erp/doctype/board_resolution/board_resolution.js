frappe.ui.form.on('Board Resolution', {
    // 1. AUTO-POPULATE MEMBERS (STATIC SNAPSHOT)
    onload: function(frm) {
        if (frm.is_new() && (!frm.doc.signatories || frm.doc.signatories.length === 0)) {
            frappe.call({
                method: 'society_erp.society_erp.doctype.board_resolution.board_resolution.get_active_committee_members',
                callback: function(r) {
                    if (r.message && r.message.length > 0) {
                        r.message.forEach(function(member) {
                            let row = frm.add_child('signatories');
                            
                            row.signatory = member.name;                 
                            row.role = member.designation;               
                            row.signatory_name = member.signatory_name;  
                            row.designation_name = member.designation_name; 
                            row.signature_status = 'Pending';
                        });
                        frm.refresh_field('signatories');
                        frappe.show_alert({
                            message: __('Active Committee Members auto-populated.'),
                            indicator: 'blue'
                        });
                    }
                }
            });
        }
    },

    refresh: function(frm) {
        // 2. LOCK THE TABLE UI 
        frm.set_df_property('signatories', 'cannot_add_rows', true);
        frm.set_df_property('signatories', 'cannot_delete_rows', true);
        frm.set_df_property('signatories', 'cannot_delete_all_rows', true);

        // 3. CHECK SIGNATURE COUNTS
        let has_at_least_one_signature = false;
        let all_signed = true;

        if (frm.doc.signatories && frm.doc.signatories.length > 0) {
            let signed_count = 0;
            frm.doc.signatories.forEach(row => {
                if (row.signature_status === 'Signed') {
                    signed_count++;
                } else {
                    all_signed = false;
                }
            });
            if (signed_count > 0) {
                has_at_least_one_signature = true;
            }
        } else {
            all_signed = false;
        }

        // 4. LOGIC FOR SAVED DRAFTS ONLY (NOT NEW UN-SAVED FORMS)
        if (!frm.is_new() && frm.doc.docstatus === 0) {
            
            // Lock text & title after the first signature
            if (has_at_least_one_signature) {
                frm.set_df_property('resolution_title', 'read_only', 1);
                frm.set_df_property('resolution_text', 'read_only', 1);
            } else {
                frm.set_df_property('resolution_title', 'read_only', 0);
                frm.set_df_property('resolution_text', 'read_only', 0);
            }

            // Hide the Submit button until everyone has signed
            if (!all_signed) {
                setTimeout(() => {
                    let primary_btn = frm.page.btn_primary;
                    if (primary_btn && primary_btn.text().trim() === __('Submit')) {
                        primary_btn.hide();
                    }
                }, 50);
            }

            // --- SHOW THE SIGN / RESPOND BUTTON ---
            frm.add_custom_button(__('Respond to Resolution'), function() {
                let d = new frappe.ui.Dialog({
                    title: __('Board Resolution Response'),
                    fields: [
                        {
                            fieldname: 'response_action',
                            fieldtype: 'Select',
                            label: __('Your Decision'),
                            options: 'Signed\nDeclined',
                            default: 'Signed',
                            reqd: 1,
                            change: function() {
                                let val = d.get_value('response_action');
                                if (val === 'Declined') {
                                    d.set_df_property('rejection_reason', 'hidden', 0);
                                    d.set_df_property('rejection_reason', 'reqd', 1);
                                } else {
                                    d.set_df_property('rejection_reason', 'hidden', 1);
                                    d.set_df_property('rejection_reason', 'reqd', 0);
                                    d.set_value('rejection_reason', ''); // Clear value if switched back
                                }
                            }
                        },
                        {
                            fieldname: 'rejection_reason',
                            fieldtype: 'Small Text',
                            label: __('Reason for Rejection'),
                            hidden: 1, // Hidden by default
                            reqd: 0
                        },
                        {
                            fieldname: 'note_html',
                            fieldtype: 'HTML',
                            options: '<p class="text-muted" style="font-size: 12px; margin-top: 5px;">Choosing "Signed" marks your acceptance. Choosing "Declined" requires a stated reason for rejection.</p>'
                        }
                    ],
                    primary_action_label: __('Submit Response'),
                    primary_action(values) {
                        d.hide();
                        frappe.call({
                            method: "society_erp.society_erp.doctype.board_resolution.board_resolution.sign_resolution",
                            args: { 
                                docname: frm.doc.name,
                                action: values.response_action,
                                rejection_reason: values.rejection_reason
                            },
                            callback: function(r) {
                                if (!r.exc) {
                                    frappe.show_alert({
                                        message: __('Response recorded successfully.'), 
                                        indicator: values.response_action === 'Signed' ? 'green' : 'red'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                });
                d.show();
            }).addClass('btn-primary');
        }
    }
});