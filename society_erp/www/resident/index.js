frappe.ready(function() {
    // Resident Portal Dashboard Controller
    class ResidentDashboard {
        constructor() {
            this.setup_defaults();
            this.bind_events();
        }

        setup_defaults() {
            // Add any initialization logic here (e.g., setting up tooltips or UI states)
            console.log("Resident Portal Initialized");
        }

        bind_events() {
            // 1. Handle Logout explicitly if you add a .btn-logout class to your UI
            $('.btn-logout').on('click', (e) => {
                e.preventDefault();
                this.logout_user();
            });

            // 2. Example: Interactive button to acknowledge/dismiss a notice
            $('.acknowledge-notice-btn').on('click', (e) => {
                e.preventDefault();
                let $btn = $(e.currentTarget);
                let notice_id = $btn.data('notice-id');
                
                // Disable button to prevent double-clicks
                $btn.prop('disabled', true).text('Processing...');
                
                this.acknowledge_notice(notice_id, $btn);
            });
        }

        logout_user() {
            frappe.call({
                method: 'logout',
                callback: function(r) {
                    if (!r.exc) {
                        // Redirect to login page after successful logout
                        window.location.href = '/login';
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: __('Failed to log out. Please try again.')
                        });
                    }
                }
            });
        }

        acknowledge_notice(notice_id, $btn) {
            // Example custom API call (you would need to create this python method)
            frappe.call({
                method: 'society_erp.api.resident_portal.acknowledge_notice',
                args: {
                    notice_id: notice_id
                },
                callback: function(r) {
                    if (!r.exc && r.message) {
                        // Remove the notice from the UI dynamically with a fade effect
                        $btn.closest('.list-group-item').fadeOut(300, function() {
                            $(this).remove();
                        });
                        frappe.show_alert({message: __('Notice Acknowledged'), indicator: 'green'});
                    } else {
                        $btn.prop('disabled', false).text('Acknowledge');
                        frappe.msgprint(__('Something went wrong.'));
                    }
                }
            });
        }
    }

    // Initialize the dashboard scripts
    new ResidentDashboard();
});
