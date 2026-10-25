frappe.ready(function() {
    
    // 1. Handle "Reclaim" Button Click
    $('.btn-reclaim').on('click', function() {
        let slot_id = $(this).data('slot');
        let old_alloc = $(this).data('alloc');
        let owner_flat = $('#owner_flat').val();
        let $btn = $(this);

        frappe.confirm(`Are you sure you want to reclaim slot <b>${slot_id}</b> for your own use?`,
            () => {
                $btn.prop('disabled', true).text('Processing...');
                
                frappe.call({
                    method: 'society_erp.api.resident_portal.reallocate_parking',
                    args: {
                        slot_id: slot_id,
                        new_type: 'Self-Occupied',
                        occupant: owner_flat,
                        old_alloc: old_alloc
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.show_alert({message: 'Slot reclaimed successfully!', indicator: 'green'});
                            setTimeout(() => location.reload(), 1500);
                        } else {
                            $btn.prop('disabled', false).text('👤 Reclaim');
                        }
                    }
                });
            }
        );
    });

    // 2. Pre-fill modal data when "Rent" button is clicked
    $('.btn-rent').on('click', function() {
        $('#modal_slot_id').val($(this).data('slot'));
        $('#modal_old_alloc').val($(this).data('alloc'));
        $('#neighbor_flat').val('');
        $('#start_date').val(frappe.datetime.get_today());
        $('#end_date').val('');
    });

    // 3. Handle Rent Form Submission
    $('#rent-form').on('submit', function(e) {
        e.preventDefault();
        
        let neighbor = $('#neighbor_flat').val().trim().toUpperCase();
        let owner = $('#owner_flat').val().trim().toUpperCase();
        
        if (neighbor === owner) {
            frappe.msgprint('You cannot rent a slot to your own flat.');
            return;
        }

        let $btn = $('#btn-submit-rent');
        $btn.prop('disabled', true).text('Submitting...');

        frappe.call({
            method: 'society_erp.api.resident_portal.reallocate_parking',
            args: {
                slot_id: $('#modal_slot_id').val(),
                new_type: 'Private Neighbor Rental',
                occupant: neighbor,
                old_alloc: $('#modal_old_alloc').val(),
                start_date: $('#start_date').val(),
                end_date: $('#end_date').val() || null
            },
            callback: function(r) {
                if (!r.exc) {
                    $('#rentModal').modal('hide');
                    frappe.show_alert({message: 'Slot rented successfully!', indicator: 'green'});
                    setTimeout(() => location.reload(), 1500);
                } else {
                    $btn.prop('disabled', false).text('Confirm Rental');
                }
            }
        });
    });
});
