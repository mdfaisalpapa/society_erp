frappe.ready(function() {
    // Handle the profile update request button
    $('.btn-update-req').on('click', function(e) {
        e.preventDefault();
        
        frappe.msgprint({
            title: __('Update Request'),
            message: __('To maintain secure records, direct edits to Flat or Ownership details are disabled. <br><br>Please go to the <b>Maintenance</b> module and raise a ticket under the "Other" category to request an update to your contact information or flat details.'),
            indicator: 'blue',
            primary_action: {
                label: 'Go to Maintenance',
                action: function() {
                    window.location.href = '/resident/maintenance';
                }
            }
        });
    });
});
