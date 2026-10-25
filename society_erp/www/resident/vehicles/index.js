frappe.ready(function() {
    
    // 1. Dynamic Make Dropdown
    $('#v_type').on('change', function() {
        let type = $(this).val();
        let $make = $('#make').empty().append('<option value="">Loading...</option>');
        $('#model').empty().append('<option value="">Select Make First</option>').prop('disabled', true);
        
        if (type) {
            frappe.call({
                method: 'society_erp.vehicle_portal.get_vehicle_form_options',
                args: { vehicle_type: type },
                callback: function(r) {
                    $make.empty().append('<option value="">Select Make</option>');
                    if (r.message && r.message.makes) {
                        r.message.makes.forEach(m => $make.append(new Option(m.make_name || m.name, m.name)));
                    }
                    $make.prop('disabled', false);
                }
            });
        }
    });

    // 2. Dynamic Model Dropdown
    $('#make').on('change', function() {
        let make = $(this).val();
        let type = $('#v_type').val();
        let $model = $('#model').empty().append('<option value="">Loading...</option>');
        
        if (make) {
            frappe.call({
                method: 'society_erp.vehicle_portal.get_vehicle_form_options',
                args: { vehicle_type: type, make: make },
                callback: function(r) {
                    $model.empty().append('<option value="">Select Model</option>');
                    if (r.message && r.message.models) {
                        r.message.models.forEach(m => $model.append(new Option(m.model_name || m.name, m.name)));
                    }
                    $model.prop('disabled', false);
                }
            });
        }
    });

    // 3. Toggle NOC Field based on Relationship
    $('#relationship').on('change', function() {
        let rel = $(this).val();
        if (rel === 'Self' || rel === 'Family(Residing)') {
            $('#noc-group').hide();
            $('#noc_file').prop('required', false);
        } else {
            $('#noc-group').show();
            $('#noc_file').prop('required', true);
        }
    });

    // 4. Submit Form Sequence
    $('#vehicle-form').on('submit', async function(e) {
        e.preventDefault();

        // Limit Check before API call
        let v_type = $('#v_type').val();
        let car_el = parseInt($('#car_eligible').val());
        let bike_el = parseInt($('#bike_eligible').val());

        if (v_type === 'Car' && car_el <= 0) {
            frappe.msgprint({title: 'Limit Reached', message: 'You have utilized all allocated reserved car slots.', indicator: 'red'});
            return;
        }
        if (v_type === 'Bike' && bike_el <= 0) {
            frappe.msgprint({title: 'Limit Reached', message: 'Maximum 2 bikes allowed per flat.', indicator: 'red'});
            return;
        }
        
        let $btn = $('#btn-submit').prop('disabled', true).text('Uploading Documents...');
        
        try {
            // Step A: Upload Files natively via Frappe
            let rcFile = $('#rc_file')[0].files[0];
            let nocFile = $('#noc_file')[0].files[0];
            
            let rc_url = await upload_file(rcFile);
            let noc_url = nocFile ? await upload_file(nocFile) : "";

            $btn.text('Registering Vehicle...');

            // Step B: Sanitize Registration Number (e.g. TN-01-AB-1234 -> TN01AB1234)
            let rawReg = $('#reg_no').val() || '';
            let cleanReg = rawReg.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();

            // Step C: Trigger Backend API
            frappe.call({
                method: 'society_erp.vehicle_portal.register_vehicle',
                args: {
                    flat: $('#flat_number').val(),
                    vehicle_type: v_type,
                    registration_number: cleanReg,
                    registered_owner_name: $('#owner_name').val(),
                    relationship_to_resident: $('#relationship').val(),
                    make: $('#make').val(),
                    model: $('#model').val(),
                    color: $('#color').val(),
                    is_electric: 0,
                    rc_copy: rc_url,
                    noc: noc_url
                },
                callback: function(r) {
                    if (r.exc) {
                        $btn.prop('disabled', false).text('Submit Registration');
                        // Frappe will automatically show the error msgprint
                    } else {
                        $('#addVehicleModal').modal('hide');
                        frappe.show_alert({message: 'Vehicle Registered Successfully!', indicator: 'green'});
                        setTimeout(() => location.reload(), 1500);
                    }
                }
            });
        } catch (err) {
            frappe.msgprint({title: 'Upload Error', message: 'Failed to securely upload documents. Please try again.', indicator: 'red'});
            $btn.prop('disabled', false).text('Submit Registration');
        }
    });

    // Helper: Natively upload file to Frappe using jQuery AJAX (Most resilient for Web Portals)
    function upload_file(file) {
        return new Promise((resolve, reject) => {
            let formData = new FormData();
            formData.append("file", file, file.name);
            formData.append("is_private", 1); 

            $.ajax({
                url: '/api/method/upload_file',
                type: 'POST',
                data: formData,
                processData: false,
                contentType: false,
                headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
                success: function(r) {
                    if (r.message && r.message.file_url) resolve(r.message.file_url);
                    else reject(r);
                },
                error: function(err) {
                    reject(err);
                }
            });
        });
    }
});
// ==========================================
    // PARKING MANAGEMENT LOGIC
    // ==========================================

    // 1. Reclaim Slot
    $('.btn-reclaim').on('click', function() {
        let slot_id = $(this).data('slot');
        let old_alloc = $(this).data('alloc');
        let owner_flat = $('#owner_flat').val() || $('#flat_number').val();
        let $btn = $(this);

        frappe.confirm(`Are you sure you want to reclaim slot <b>${slot_id}</b> for your own use?`, () => {
            $btn.prop('disabled', true).text('Processing...');
            frappe.call({
                method: 'society_erp.vehicle_portal.reallocate_parking_slot',
                args: {
                    slot_id: slot_id,
                    old_alloc_name: old_alloc,
                    new_type: 'Self-Occupied',
                    occupant: owner_flat,
                    start_date: frappe.datetime.get_today()
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
        });
    });

    // 2. Open Rent Modal & Pre-fill
    $('.btn-rent').on('click', function() {
        $('#modal_slot_id').val($(this).data('slot'));
        $('#modal_old_alloc').val($(this).data('alloc'));
        $('#neighbor_flat').val('');
        $('#start_date').val(frappe.datetime.get_today());
        $('#end_date').val('');
    });

    // 3. Submit Rent Form (With Strict Flat Validation)
    $('#rent-form').on('submit', function(e) {
        e.preventDefault();
        
        let neighbor = $('#neighbor_flat').val().trim().toUpperCase();
        let owner = $('#owner_flat').val() || $('#flat_number').val();
        
        // Build array of valid flats directly from the HTML datalist options
        let validFlats = [];
        $('#flat_list option').each(function() {
            validFlats.push($(this).val().toUpperCase());
        });

        if (!validFlats.includes(neighbor)) {
            frappe.msgprint({title: 'Invalid Flat', message: 'Please select a valid flat number from the search list.', indicator: 'red'});
            return;
        }
        
        if (neighbor === owner) {
            frappe.msgprint({title: 'Invalid Flat', message: 'You cannot rent a slot to your own flat.', indicator: 'red'});
            return;
        }

        let $btn = $('#btn-submit-rent').prop('disabled', true).text('Submitting...');

        frappe.call({
            method: 'society_erp.vehicle_portal.reallocate_parking_slot',
            args: {
                slot_id: $('#modal_slot_id').val(),
                old_alloc_name: $('#modal_old_alloc').val(),
                new_type: 'Private Neighbor Rental',
                occupant: neighbor,
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

// ==========================================
    // VEHICLE DELETION LOGIC
    // ==========================================

    $('.btn-delete-vehicle').on('click', function() {
        let vehicle_id = $(this).data('id');
        let reg_no = $(this).data('reg');
        let $btn = $(this);

        frappe.confirm(`Are you sure you want to delete the pending registration for <b>${reg_no}</b>?`, () => {
            $btn.prop('disabled', true).text('Deleting...');
            
            frappe.call({
                method: 'society_erp.vehicle_portal.delete_pending_vehicle', // Call the new whitelisted method
                args: {
                    vehicle_id: vehicle_id
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({message: `Vehicle ${reg_no} deleted successfully!`, indicator: 'green'});
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        $btn.prop('disabled', false).text('🗑️ Delete');
                    }
                }
            });
        });
    });

// 5. Disable Approved Vehicle
    $('.btn-disable-vehicle').on('click', function() {
        let vehicle_id = $(this).data('id');
        let reg_no = $(this).data('reg');
        let $btn = $(this);

        frappe.confirm(`Are you sure you want to disable <b>${reg_no}</b>? <br><br>This will permanently mark the vehicle as inactive and immediately free up your parking limits.`, () => {
            $btn.prop('disabled', true).text('Disabling...');
            
            frappe.call({
                method: 'society_erp.vehicle_portal.disable_active_vehicle', 
                args: {
                    vehicle_id: vehicle_id
                },
                callback: function(r) {
                    if (!r.exc) {
                        frappe.show_alert({message: `Vehicle ${reg_no} marked as inactive!`, indicator: 'green'});
                        setTimeout(() => location.reload(), 1500);
                    } else {
                        $btn.prop('disabled', false).text('🛑 Disable');
                    }
                }
            });
        });
    });
    // 4. View History
    $('.btn-history').on('click', function() {
        let slot_id = $(this).data('slot');
        $('#history_slot_title').text(slot_id);
        let $tbody = $('#history-table-body').empty().append('<tr><td colspan="5" class="text-center">Loading...</td></tr>');

        frappe.call({
            method: 'society_erp.vehicle_portal.get_parking_history',
            args: { slot_id: slot_id },
            callback: function(r) {
                $tbody.empty();
                if (r.message && r.message.length > 0) {
                    r.message.forEach(h => {
                        let statusIcon = h.status === 'Active' ? '🟢' : '⚪';
                        $tbody.append(`
                            <tr>
                                <td>${statusIcon} ${h.status}</td>
                                <td>${h.allocation_type}</td>
                                <td>Flat ${h.occupied_by}</td>
                                <td>${h.start_date || 'Unknown'}</td>
                                <td>${h.end_date || 'Present'}</td>
                            </tr>
                        `);
                    });
                } else {
                    $tbody.append('<tr><td colspan="5" class="text-center text-muted">No history found.</td></tr>');
                }
            }
        });
    });
