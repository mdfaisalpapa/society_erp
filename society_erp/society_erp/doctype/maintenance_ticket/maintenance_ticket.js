frappe.ui.form.on('Maintenance Ticket', {
    setup: function(frm) {
        frm.set_query("assigned_to", function() {
            return {
                filters: [
                    ["Authorized Bot Device", "device_role", "like", "Maintenance%"],
                    ["Authorized Bot Device", "is_active", "=", 1]
                ]
            };
        });
    }
});
