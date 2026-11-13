frappe.ready(function() {
    let allRoster = [];
    let allPosts = [];
    let allMusters = [];
    let previousMusters = [];
    let selectedMusterId = null;
    let html5QrCode = null;
    let selectedStaffForPost = null;

    // Load initial dashboard data
    loadAgencyDashboard();

    // Muster shortcut button
    $('#btn-open-muster-modal-2').on('click', function() {
        $('#btn-open-muster-modal').click();
    });

    // Scan QR button next to target muster
    $('#btn-open-qr-scanner-muster').on('click', function() {
        $('#btn-open-qr-scanner').click();
    });

    // Search filter
    $('#agency-search').on('input', function() {
        const query = $(this).val().toLowerCase().trim();
        renderRosterTable(allRoster.filter(item => {
            return (item.full_name && item.full_name.toLowerCase().includes(query)) ||
                   (item.role && item.role.toLowerCase().includes(query)) ||
                   (item.duty_post && item.duty_post.toLowerCase().includes(query)) ||
                   (item.gate_assigned && item.gate_assigned.toLowerCase().includes(query)) ||
                   (item.cost_center && item.cost_center.toLowerCase().includes(query)) ||
                   (item.status && item.status.toLowerCase().includes(query)) ||
                   (item.approval_status && item.approval_status.toLowerCase().includes(query));
        }));
    });

    // Toggle fresh water diversion reason box
    $('#water-divert-check').on('change', function() {
        if ($(this).is(':checked')) {
            $('#water-diversion-reason-box').removeClass('d-none');
        } else {
            $('#water-diversion-reason-box').addClass('d-none');
        }
    });

    // Open Water Sump & Pump Log Modal
    $('#btn-open-water-modal').on('click', function() {
        $('#form-water-log')[0].reset();
        $('#water-diversion-reason-box').addClass('d-none');
        $('#modal-water-log').modal('show');
    });

    // Open Water Tanker Log Modal
    $('#btn-open-tanker-modal').on('click', function() {
        $('#form-tanker-log')[0].reset();
        $('#modal-tanker-log').modal('show');
    });

    // Submit Water Tanker Log
    $('#form-tanker-log').on('submit', function(e) {
        e.preventDefault();
        const btn = $('#btn-submit-tanker-log');
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');

        const vehicleNo = $('#tanker-vehicle-no').val().trim().toUpperCase();
        const capacityKl = $('#tanker-capacity').val();
        const targetSump = $('#tanker-target-sump').val();
        const targetBlock = $('#tanker-target-block').val();
        const supplier = $('#tanker-supplier').val().trim();
        const challanNo = $('#tanker-challan-no').val().trim();
        const remarks = $('#tanker-remarks').val().trim();

        const challanFileInput = document.getElementById('tanker-challan-photo');
        const vehicleFileInput = document.getElementById('tanker-vehicle-photo');

        async function uploadIfPresent(fileInput) {
            if (fileInput.files && fileInput.files[0]) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('is_private', 0);
                formData.append('folder', 'Home');
                const resp = await fetch('/api/method/upload_file', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token }
                });
                const d = await resp.json();
                return d.message ? d.message.file_url : null;
            }
            return null;
        }

        (async () => {
            try {
                const challanPhotoUrl = await uploadIfPresent(challanFileInput);
                const vehiclePhotoUrl = await uploadIfPresent(vehicleFileInput);

                frappe.call({
                    method: 'society_erp.api.water.log_water_tanker',
                    args: {
                        vehicle_number: vehicleNo,
                        capacity_kl: capacityKl,
                        target_sump: targetSump,
                        target_block: targetBlock,
                        supplier: supplier,
                        delivery_challan_no: challanNo,
                        challan_photo: challanPhotoUrl,
                        tanker_photo: vehiclePhotoUrl,
                        remarks: remarks
                    },
                    callback: function(r) {
                        btn.prop('disabled', false).text('🚚 Save Tanker Delivery');
                        if (r.message && r.message.success) {
                            $('#modal-tanker-log').modal('hide');
                            showAlert('success', '🚚 ' + r.message.message);
                        } else {
                            frappe.msgprint(__('Failed to save tanker delivery: ' + (r.message ? r.message.message : 'Unknown error')));
                        }
                    },
                    error: function() {
                        btn.prop('disabled', false).text('🚚 Save Tanker Delivery');
                    }
                });
            } catch (err) {
                btn.prop('disabled', false).text('🚚 Save Tanker Delivery');
                frappe.msgprint(__('Error uploading tanker photo: ' + err));
            }
        })();
    });

    // Submit Water Log
    $('#form-water-log').on('submit', function(e) {
        e.preventDefault();
        const btn = $('#btn-submit-water-log');
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');

        const block = $('#water-block-select').val();
        const domLevel = $('#water-dom-level').val();
        const domPump = $('#water-dom-pump').val();
        const flushLevel = $('#water-flush-level').val();
        const flushPump = $('#water-flush-pump').val();
        const notes = $('#water-notes').val().trim();

        const domFileInput = document.getElementById('water-dom-photo');
        const flushFileInput = document.getElementById('water-flush-photo');

        async function uploadIfPresent(fileInput) {
            if (fileInput.files && fileInput.files[0]) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('is_private', 0);
                formData.append('folder', 'Home');
                const resp = await fetch('/api/method/upload_file', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token }
                });
                const d = await resp.json();
                return d.message ? d.message.file_url : null;
            }
            return null;
        }

        (async () => {
            try {
                const domPhotoUrl = await uploadIfPresent(domFileInput);
                const flushPhotoUrl = await uploadIfPresent(flushFileInput);

                frappe.call({
                    method: 'society_erp.api.water.log_block_water',
                    args: {
                        block: block,
                        domestic_level_ft: domLevel,
                        domestic_photo: domPhotoUrl,
                        domestic_pump_action: domPump,
                        flush_level_ft: flushLevel,
                        flush_photo: flushPhotoUrl,
                        flush_pump_action: flushPump,
                        fresh_water_diverted_to_flush: $('#water-divert-check').is(':checked') ? 1 : 0,
                        fresh_water_diversion_reason: $('#water-diversion-reason').val(),
                        notes: notes
                    },
                    callback: function(r) {
                        btn.prop('disabled', false).text('💧 Save Water Log');
                        if (r.message && r.message.status === 'success') {
                            $('#modal-water-log').modal('hide');
                            showAlert('success', '💧 ' + r.message.message);
                        } else {
                            frappe.msgprint(__('Failed to save water log.'));
                        }
                    },
                    error: function() {
                        btn.prop('disabled', false).text('💧 Save Water Log');
                    }
                });
            } catch (err) {
                btn.prop('disabled', false).text('💧 Save Water Log');
                frappe.msgprint(__('Error uploading sump photo: ' + err));
            }
        })();
    });

    // Open Tank Cleaning Modal
    $('#btn-open-tank-cleaning-modal').on('click', function() {
        $('#form-tank-cleaning')[0].reset();
        $('#modal-tank-cleaning').modal('show');
    });

    // Submit Tank Cleaning Log
    $('#form-tank-cleaning').on('submit', function(e) {
        e.preventDefault();
        const btn = $('#btn-submit-tank-cleaning');
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');

        const block = $('#tc-block').val();
        const tankType = $('#tc-tank-type').val();
        const activityDate = $('#tc-date').val();
        const agencyName = $('#tc-agency').val();
        const sediment = $('#tc-sediment-level').val();
        const chlorination = $('#tc-chlorination').is(':checked') ? 1 : 0;
        const remarks = $('#tc-remarks').val().trim();

        const beforeInput = document.getElementById('tc-photo-before');
        const afterInput = document.getElementById('tc-photo-after');

        async function uploadIfPresent(fileInput) {
            if (fileInput && fileInput.files && fileInput.files[0]) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('is_private', 0);
                formData.append('folder', 'Home');
                const resp = await fetch('/api/method/upload_file', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token }
                });
                const d = await resp.json();
                return d.message ? d.message.file_url : null;
            }
            return null;
        }

        (async () => {
            try {
                const beforeUrl = await uploadIfPresent(beforeInput);
                const afterUrl = await uploadIfPresent(afterInput);

                frappe.call({
                    method: 'society_erp.api.water.log_tank_cleaning',
                    args: {
                        block: block,
                        tank_type: tankType,
                        activity_date: activityDate,
                        cleaning_agency: agencyName,
                        photo_before: beforeUrl,
                        photo_after: afterUrl,
                        sediment_level_observed: sediment,
                        chlorination_done: chlorination,
                        remarks: remarks
                    },
                    callback: function(r) {
                        btn.prop('disabled', false).text('🚰 Save Cleaning Record');
                        if (r.message && r.message.success) {
                            $('#modal-tank-cleaning').modal('hide');
                            showAlert('success', '🚰 ' + r.message.message);
                        } else {
                            frappe.msgprint(__('Failed to save tank cleaning record.'));
                        }
                    },
                    error: function() {
                        btn.prop('disabled', false).text('🚰 Save Cleaning Record');
                    }
                });
            } catch (err) {
                btn.prop('disabled', false).text('🚰 Save Cleaning Record');
                frappe.msgprint(__('Error uploading cleaning inspection photos: ' + err));
            }
        })();
    });

    // Open Onboard Modal
    $('#btn-open-onboard-modal').on('click', function() {
        $('#form-onboard-staff')[0].reset();
        $('#modal-onboard-staff').modal('show');
    });

    // Open Muster Modal
    $('#btn-open-muster-modal').on('click', function() {
        $('#form-record-muster')[0].reset();
        $('#modal-muster').modal('show');
    });

    // Form submit: Onboard Staff
    $('#form-onboard-staff').on('submit', function(e) {
        e.preventDefault();
        const submitBtn = $('#btn-submit-onboard');
        submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status"></span> Submitting…');

        const agencyName = $('h3.font-weight-bold').first().text().trim();

        frappe.call({
            method: 'society_erp.api.facility_staff.onboard_facility_staff',
            args: {
                full_name: $('#staff-full-name').val().trim(),
                agency: agencyName,
                role: $('#staff-role').val(),
                contact_number: $('#staff-contact').val().trim(),
                gate_assigned: $('#staff-gate').val(),
                government_id_type: $('#staff-id-type').val(),
                government_id_number: $('#staff-id-number').val().trim(),
                police_verification_status: $('#staff-police').val(),
                notes: $('#staff-notes').val().trim()
            },
            callback: function(r) {
                submitBtn.prop('disabled', false).text('Submit for Committee Approval');
                if (r.message && r.message.status === 'success') {
                    $('#modal-onboard-staff').modal('hide');
                    showAlert('success', '✅ ' + (r.message.message || 'Staff submitted for Committee approval!'));
                    loadAgencyDashboard();
                } else {
                    frappe.msgprint(__('Failed to onboard staff.'));
                }
            },
            error: function() {
                submitBtn.prop('disabled', false).text('Submit for Committee Approval');
            }
        });
    });

    // Submit Chemical Log
    $('#btn-open-chemical-modal').on('click', function() {
        $('#form-chemical-log')[0].reset();
        $('#modal-chemical-log').modal('show');
    });

    $('#form-chemical-log').on('submit', function(e) {
        e.preventDefault();
        const btn = $('#btn-submit-chemical-log');
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving...');

        const chemName = $('#chem-select-name').val();
        const curStock = $('#chem-current-stock').val();
        const unit = $('#chem-unit').val();
        const consumption = $('#chem-consumption').val() || 0;
        const received = $('#chem-received').val() || 0;
        const threshold = $('#chem-threshold').val() || null;
        const remarks = $('#chem-remarks').val().trim();
        const photoInput = document.getElementById('chem-photo');

        async function uploadIfPresent(fileInput) {
            if (fileInput && fileInput.files && fileInput.files[0]) {
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('is_private', 0);
                formData.append('folder', 'Home');
                const resp = await fetch('/api/method/upload_file', {
                    method: 'POST',
                    body: formData,
                    headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token }
                });
                const d = await resp.json();
                return d.message ? d.message.file_url : null;
            }
            return null;
        }

        (async () => {
            try {
                const photoUrl = await uploadIfPresent(photoInput);
                frappe.call({
                    method: 'society_erp.api.stp_chemical.log_stp_chemical_stock',
                    args: {
                        chemical_name: chemName,
                        current_stock: curStock,
                        unit_of_measure: unit,
                        daily_consumption: consumption,
                        stock_received: received,
                        minimum_threshold: threshold,
                        stock_photo: photoUrl,
                        remarks: remarks
                    },
                    callback: function(r) {
                        btn.prop('disabled', false).text('🧪 Save Chemical Stock');
                        if (r.message && r.message.status === 'success') {
                            $('#modal-chemical-log').modal('hide');
                            const isLow = r.message.is_low_stock;
                            const alertType = isLow ? 'warning' : 'success';
                            const alertMsg = isLow 
                                ? '⚠️ Stock recorded! Warning: Current stock is below safety threshold!' 
                                : '🧪 ' + r.message.message;
                            showAlert(alertType, alertMsg);
                            loadAgencyDashboard();
                        } else {
                            frappe.msgprint(__('Failed to save chemical stock.'));
                        }
                    },
                    error: function() {
                        btn.prop('disabled', false).text('🧪 Save Chemical Stock');
                    }
                });
            } catch (err) {
                btn.prop('disabled', false).text('🧪 Save Chemical Stock');
                frappe.msgprint(__('Error uploading photo: ' + err));
            }
        })();
    });

    // Handle Upload / Update Photo button directly next to Active Target Muster
    $(document).on('click', '.btn-upload-active-muster-photo', function() {
        const musterId = $(this).data('id');
        const category = $(this).data('category');
        const shift = $(this).data('shift');

        // Pre-fill modal with active muster details
        $('#muster-shift').val(shift);
        $('#muster-category').val(category);
        $('#form-record-muster').data('target-muster-id', musterId);
        $('#modal-muster').modal('show');
    });

    // Form submit: Muster Photo Upload
    $('#form-record-muster').on('submit', function(e) {
        e.preventDefault();
        const submitBtn = $('#btn-submit-muster');
        const fileInput = document.getElementById('muster-photo-file');
        if (!fileInput.files || !fileInput.files[0]) {
            frappe.msgprint(__('Please attach or take a shift group photo.'));
            return;
        }

        submitBtn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Uploading photo…');
        const file = fileInput.files[0];
        const agencyName = $('h3.font-weight-bold').first().text().trim();
        const shiftVal = $('#muster-shift').val();
        const catVal = $('#muster-category').val();
        const countVal = parseInt($('#muster-count').val(), 10) || 0;
        const notesVal = $('#muster-notes').val().trim();

        const formData = new FormData();
        formData.append('file', file);
        formData.append('is_private', 0);
        formData.append('folder', 'Home');

        fetch('/api/method/upload_file', {
            method: 'POST',
            body: formData,
            headers: {
                'X-Frappe-CSRF-Token': frappe.csrf_token
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.message && data.message.file_url) {
                const fileUrl = data.message.file_url;
                const targetMusterId = $('#form-record-muster').data('target-muster-id');

                const apiMethod = targetMusterId 
                    ? 'society_erp.api.facility_staff.update_muster_photo'
                    : 'society_erp.api.facility_staff.record_shift_muster';

                const apiArgs = targetMusterId ? {
                    muster_id: targetMusterId,
                    muster_photo: fileUrl,
                    reported_count: countVal,
                    notes: notesVal
                } : {
                    agency: agencyName,
                    shift: shiftVal,
                    category: catVal,
                    muster_photo: fileUrl,
                    reported_count: countVal,
                    notes: notesVal
                };

                frappe.call({
                    method: apiMethod,
                    args: apiArgs,
                    callback: function(r) {
                        submitBtn.prop('disabled', false).text('📸 Save Muster Photo');
                        $('#form-record-muster').removeData('target-muster-id');
                        if (r.message && r.message.status === 'success') {
                            $('#modal-muster').modal('hide');
                            showAlert('success', '📸 ' + r.message.message);
                            loadAgencyDashboard();
                        } else {
                            frappe.msgprint(__('Failed to record shift muster.'));
                        }
                    }
                });
            } else {
                submitBtn.prop('disabled', false).text('📸 Save Muster Photo');
                frappe.msgprint(__('File upload failed.'));
            }
        })
        .catch(err => {
            submitBtn.prop('disabled', false).text('📸 Save Muster Photo');
            frappe.msgprint(__('Error uploading photo: ' + err));
        });
    });

    // Open QR Scanner
    $('#btn-open-qr-scanner').on('click', function() {
        $('#modal-qr-scanner').modal('show');
        $('#qr-reader-results').text('');
        startQrScanner();
    });

    $('#modal-qr-scanner').on('hidden.bs.modal', function() {
        stopQrScanner();
    });

    function startQrScanner() {
        if (typeof Html5Qrcode === 'undefined') {
            $('#qr-reader-results').text('QR Scanner library not loaded. Please ensure internet access.');
            return;
        }

        html5QrCode = new Html5Qrcode("qr-reader");
        const qrConfig = { fps: 10, qrbox: { width: 220, height: 220 } };

        html5QrCode.start(
            { facingMode: "environment" },
            qrConfig,
            onScanSuccess
        ).catch(err => {
            console.error("Unable to start scanner", err);
            $('#qr-reader-results').html(`<span class="text-danger">Camera error: ${err.message || err}. Please ensure camera permissions are granted.</span>`);
        });
    }

    function stopQrScanner() {
        if (html5QrCode) {
            html5QrCode.stop().then(() => {
                html5QrCode.clear();
                html5QrCode = null;
            }).catch(err => {
                console.error("Failed to stop scanner", err);
            });
        }
    }

    function onScanSuccess(decodedText) {
        // QR detected
        $('#qr-reader-results').html(`<div class="spinner-border spinner-border-sm text-success"></div> Scanned: <code>${decodedText}</code>. Punching...`);
        stopQrScanner();

        frappe.call({
            method: 'society_erp.api.facility_staff.punch_attendance',
            args: {
                qr_code: decodedText,
                punch_type: 'auto',
                muster_id: selectedMusterId,
                method: 'QR Kiosk Scan'
            },
            callback: function(r) {
                $('#modal-qr-scanner').modal('hide');
                if (r.message && r.message.status === 'success') {
                    showAlert('success', '⏱️ [QR Punch] ' + r.message.message);
                    loadAgencyDashboard();
                } else {
                    frappe.msgprint(__('Failed to process QR attendance: ' + (r.message ? r.message.message : 'Unknown error')));
                }
            },
            error: function(err) {
                $('#modal-qr-scanner').modal('hide');
            }
        });
    }

    // Dynamic Post Assignment Modal
    $(document).on('click', '.btn-assign-duty', function() {
        const btn = $(this);
        const staffId = btn.data('id');
        const staffName = btn.data('name');
        const staffRole = btn.data('role');
        const currentPost = btn.data('post') || '';
        const attId = btn.data('att-id') || '';

        selectedStaffForPost = { staffId, attId };

        $('#assign-staff-name').text(staffName);
        $('#assign-staff-role').text(staffRole + ' (' + staffId + ')');

        // Populate Duty Posts
        const select = $('#select-duty-post');
        select.empty();
        select.append('<option value="">-- Select Post / Block --</option>');
        allPosts.forEach(p => {
            const isSel = (p.name === currentPost) ? 'selected' : '';
            select.append(`<option value="${p.name}" data-cost-center="${p.cost_center}" ${isSel}>${p.post_name} [${p.zone_type}]</option>`);
        });

        updateCostCenterDisplay();
        $('#modal-assign-post').modal('show');
    });

    $('#select-duty-post').on('change', function() {
        updateCostCenterDisplay();
    });

    function updateCostCenterDisplay() {
        const selOpt = $('#select-duty-post option:selected');
        const cc = selOpt.data('cost-center') || 'None Selected';
        $('#assign-cost-center-display').text(cc);
    }

    $('#btn-save-post-assignment').on('click', function() {
        const chosenPost = $('#select-duty-post').val();
        if (!chosenPost) {
            frappe.msgprint(__('Please select a valid duty post.'));
            return;
        }

        const btn = $(this);
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span> Saving…');

        frappe.call({
            method: 'society_erp.api.facility_staff.assign_duty_post',
            args: {
                attendance_id: selectedStaffForPost.attId,
                staff_id: selectedStaffForPost.staffId,
                duty_post: chosenPost
            },
            callback: function(r) {
                btn.prop('disabled', false).text('Save Post Assignment');
                if (r.message && r.message.status === 'success') {
                    $('#modal-assign-post').modal('hide');
                    showAlert('success', '📍 ' + r.message.message);
                    loadAgencyDashboard();
                } else {
                    frappe.msgprint(__('Failed to assign duty post.'));
                }
            },
            error: function() {
                btn.prop('disabled', false).text('Save Post Assignment');
            }
        });
    });

    // Manual Punch In/Out button
    $(document).on('click', '.btn-agency-punch', function() {
        const btn = $(this);
        const staffId = btn.data('id');
        const currentPunch = btn.data('punch'); // 'in' or 'out'
        const nextAction = currentPunch === 'in' ? 'out' : 'in';

        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm"></span>');

        frappe.call({
            method: 'society_erp.api.facility_staff.punch_attendance',
            args: {
                staff_id: staffId,
                punch_type: nextAction,
                muster_id: selectedMusterId,
                method: 'Supervisor Punch'
            },
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    showAlert('success', '⏱️ ' + r.message.message);
                    loadAgencyDashboard();
                } else {
                    btn.prop('disabled', false);
                    frappe.msgprint(__('Punch failed.'));
                }
            },
            error: function() {
                btn.prop('disabled', false);
            }
        });
    });

    function loadAgencyDashboard() {
        frappe.call({
            method: 'society_erp.www.agency.index.get_agency_dashboard_data',
            callback: function(r) {
                if (r.message) {
                    const data = r.message;
                    $('#stat-on-duty').text(data.on_duty_count || 0);
                    $('#stat-pending').text(data.pending_approval_count || 0);
                    $('#stat-total').text(data.total_active_staff || 0);

                    // Update shift compliance KPI
                    const quota = data.active_shift_quota || 0;
                    const onDuty = data.on_duty_count || 0;
                    $('#stat-shift-compliance').text(`${onDuty} / ${quota}`);
                    $('#stat-shift-name').text(data.active_shift ? `${data.active_shift.slice(0, 22)}...` : 'Active Shift');
                    if (quota > 0 && onDuty < quota) {
                        $('#stat-shift-compliance').removeClass('text-purple text-success').addClass('text-danger');
                    } else if (quota > 0 && onDuty >= quota) {
                        $('#stat-shift-compliance').removeClass('text-purple text-danger').addClass('text-success');
                    }

                    allPosts = data.duty_posts || [];
                    allRoster = data.roster || [];
                    allMusters = data.today_musters || [];
                    previousMusters = data.previous_musters || [];

                    $('#count-today-musters').text(allMusters.length);
                    $('#count-prev-musters').text(previousMusters.length);

                    // Auto-select latest muster if none selected
                    if (!selectedMusterId && allMusters.length > 0) {
                        selectedMusterId = allMusters[0].name;
                    }

                    renderMustersList(allMusters);
                    renderPreviousMustersList(previousMusters);
                    renderRosterTable(allRoster);
                }
            }
        });
    }

    function renderMustersList(musters) {
        const container = $('#muster-sessions-container');
        if (!musters || musters.length === 0) {
            container.html(`
                <div class="alert alert-warning py-3 mb-0 small d-flex justify-content-between align-items-center flex-wrap">
                    <div>⚠️ <strong>No Shift Muster photo recorded yet today.</strong> Please record the shift lineup photo before punching in staff.</div>
                    <button class="btn btn-warning btn-sm font-weight-bold ml-md-2 mt-2 mt-md-0" onclick="$('#btn-open-muster-modal').click();">📸 Record Muster Now</button>
                </div>
            `);
            return;
        }

        let html = `<div class="row">`;
        musters.forEach(m => {
            const isSelected = (m.name === selectedMusterId);
            const borderStyle = isSelected ? 'border: 2px solid #007bff; background: #f0f7ff;' : 'border: 1px solid #dee2e6; background: #fff;';
            
            // Dept icons
            let deptIcon = '🛡️';
            if (m.category === 'Housekeeping') deptIcon = '🧹';
            else if (m.category === 'Maintenance' || m.category === 'Technical / Plant') deptIcon = '🔧';

            let photoBox = '';
            if (m.muster_photo && m.muster_photo !== 'DELETED_POST_BILLING_VERIFICATION') {
                photoBox = `
                    <a href="${m.muster_photo}" target="_blank" class="mr-2">
                        <img src="${m.muster_photo}" class="rounded border shadow-sm" style="width: 60px; height: 60px; object-fit: cover;" alt="Muster">
                    </a>
                `;
            } else {
                photoBox = `
                    <div class="mr-2 rounded border bg-light d-flex align-items-center justify-content-center text-muted" style="width: 60px; height: 60px; font-size: 1.5rem;" title="Muster auto-scheduled; lineup photo optional">
                        ${deptIcon}
                    </div>
                `;
            }

            // If active target muster, place the "📷 Scan ID QR" button directly next to it
            let actionHtml = '';
            const hasPhoto = (m.muster_photo && m.muster_photo !== 'DELETED_POST_BILLING_VERIFICATION');

            if (isSelected) {
                actionHtml = `
                    <div class="d-flex align-items-center flex-wrap gap-1">
                        <span class="badge badge-primary px-2 py-1 mr-1">Active Target Muster</span>
                        <button class="btn btn-sm ${hasPhoto ? 'btn-outline-info' : 'btn-danger'} py-0 px-2 font-weight-bold shadow-sm btn-upload-active-muster-photo mr-1" data-id="${m.name}" data-category="${frappe.utils.escape_html(m.category)}" data-shift="${frappe.utils.escape_html(m.shift)}" title="${hasPhoto ? 'Replace / Update Lineup Photo' : 'Upload Mandatory Lineup Photo'}">
                            📸 ${hasPhoto ? 'Update Photo' : 'Upload Photo *'}
                        </button>
                        ${hasPhoto ? `
                            <button class="btn btn-sm btn-primary py-0 px-2 font-weight-bold shadow-sm" onclick="$('#btn-open-qr-scanner').click();" title="Scan QR badge under this muster">
                                📷 Scan ID QR
                            </button>
                        ` : `
                            <button class="btn btn-sm btn-secondary py-0 px-2 font-weight-bold shadow-sm" disabled title="Muster roll photo is mandatory before punching in">
                                📷 Scan ID QR (Photo Required)
                            </button>
                        `}
                    </div>
                `;
            } else {
                actionHtml = `
                    <button class="btn btn-outline-primary btn-sm py-0 px-2 btn-select-muster font-weight-bold" data-id="${m.name}">
                        🎯 Select
                    </button>
                `;
            }

            html += `
                <div class="col-12 col-md-6 col-lg-4 mb-2">
                    <div class="card p-2 shadow-sm rounded h-100" style="${borderStyle}">
                        <div class="d-flex align-items-center">
                            ${photoBox}
                            <div class="flex-grow-1 min-width-0">
                                <div class="font-weight-bold text-dark text-truncate small">${deptIcon} ${frappe.utils.escape_html(m.category)} Muster</div>
                                <div class="text-muted small text-truncate">${frappe.utils.escape_html(m.shift)}</div>
                                <div class="small text-success font-weight-bold">✅ Verified Punches: <strong>${m.verified_punch_count || 0}</strong> / ${m.reported_count || 0}</div>
                            </div>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mt-2 pt-1 border-top flex-wrap">
                            <small class="text-muted font-family-monospace">${m.name.slice(-14)}</small>
                            <div>${actionHtml}</div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
        container.html(html);
    }

    function renderPreviousMustersList(musters) {
        const container = $('#previous-musters-container');
        if (!musters || musters.length === 0) {
            container.html(`
                <div class="text-center py-4 text-muted bg-light rounded border">
                    <div style="font-size: 1.8rem;">🗂️</div>
                    <div class="small font-weight-bold mt-1">No Previous Musters Found</div>
                    <div class="small text-muted">Past muster lineups from earlier dates will appear here for audit reference.</div>
                </div>
            `);
            return;
        }

        let html = `
            <div class="table-responsive">
                <table class="table table-sm table-hover align-middle mb-0 bg-white border">
                    <thead class="thead-light">
                        <tr>
                            <th>Lineup Photo</th>
                            <th>Muster ID & Date</th>
                            <th>Shift & Category</th>
                            <th>Physical Lineup</th>
                            <th>Punched Count</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        musters.forEach(m => {
            const isSelected = (m.name === selectedMusterId);
            const rowClass = isSelected ? 'table-primary' : '';
            const isPurged = m.muster_photo === 'DELETED_POST_BILLING_VERIFICATION';

            let photoCol = '';
            if (isPurged) {
                photoCol = '<span class="badge badge-light border text-muted">Purged &bull; 30d Audit</span>';
            } else if (m.muster_photo) {
                photoCol = `
                    <a href="${m.muster_photo}" target="_blank">
                        <img src="${m.muster_photo}" class="rounded border shadow-sm" style="width: 48px; height: 48px; object-fit: cover;" alt="Photo">
                    </a>
                `;
            } else {
                photoCol = '<span class="text-muted small">No Photo</span>';
            }

            html += `
                <tr class="${rowClass}">
                    <td style="width: 60px;">${photoCol}</td>
                    <td>
                        <div class="font-weight-bold text-dark font-family-monospace small">${frappe.utils.escape_html(m.name)}</div>
                        <span class="badge badge-secondary">${frappe.utils.escape_html(m.shift_date || '')}</span>
                    </td>
                    <td>
                        <div class="font-weight-bold small">${frappe.utils.escape_html(m.shift)}</div>
                        <small class="text-muted">${frappe.utils.escape_html(m.category)}</small>
                    </td>
                    <td>
                        <span class="badge badge-info px-2 py-1 font-weight-bold">${m.reported_count || 0} Reported</span>
                    </td>
                    <td>
                        <span class="badge badge-success px-2 py-1 font-weight-bold">${m.verified_punch_count || 0} Punched</span>
                    </td>
                    <td class="text-right">
                        ${isSelected ? `
                            <div class="d-flex justify-content-end align-items-center gap-1">
                                <span class="badge badge-primary px-2 py-1 mr-1">Active Target</span>
                                <button class="btn btn-sm btn-primary py-0 px-2 font-weight-bold" onclick="$('#btn-open-qr-scanner').click();">
                                    📷 Scan ID QR
                                </button>
                            </div>
                        ` : `
                            <button class="btn btn-outline-secondary btn-sm py-0 px-2 btn-select-muster font-weight-bold" data-id="${m.name}">
                                🎯 Select
                            </button>
                        `}
                    </td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;
        container.html(html);
    }

    $(document).on('click', '.btn-select-muster', function() {
        selectedMusterId = $(this).data('id');
        renderMustersList(allMusters);
        renderPreviousMustersList(previousMusters);
        renderRosterTable(allRoster);

        // Find selected muster details to populate friendly modal popup
        const target = allMusters.find(m => m.name === selectedMusterId) || previousMusters.find(m => m.name === selectedMusterId);
        if (target) {
            let deptIcon = '🛡️';
            if (target.category === 'Housekeeping') deptIcon = '🧹';
            else if (target.category === 'Maintenance' || target.category === 'Technical / Plant') deptIcon = '🔧';

            $('#muster-modal-icon').text(deptIcon);
            $('#muster-modal-title').text(`${deptIcon} ${target.category} Muster Activated`);
            $('#muster-modal-shift').text(`${target.shift} (${target.shift_date || ''})`);
            $('#muster-modal-id').text(target.name);
            $('#muster-modal-filter').text(`Only ${target.category} Staff`);

            const hasPhoto = Boolean(target.muster_photo && target.muster_photo !== 'DELETED_POST_BILLING_VERIFICATION');
            if (hasPhoto) {
                $('#muster-modal-photo-status').html('<span class="badge badge-success font-weight-bold">✅ Photo Uploaded</span>');
            } else {
                $('#muster-modal-photo-status').html('<span class="badge badge-danger font-weight-bold">⚠️ Photo Required</span>');
            }

            $('#modal-muster-activated').modal('show');
        }
    });

    function getSelectedMusterCategory() {
        if (!selectedMusterId) return null;
        const target = allMusters.find(m => m.name === selectedMusterId) || previousMusters.find(m => m.name === selectedMusterId);
        return target ? target.category : null;
    }

    function isSelectedMusterPhotoUploaded() {
        if (!selectedMusterId) return false;
        const target = allMusters.find(m => m.name === selectedMusterId) || previousMusters.find(m => m.name === selectedMusterId);
        return Boolean(target && target.muster_photo && target.muster_photo !== 'DELETED_POST_BILLING_VERIFICATION');
    }

    function isStaffEligibleForCategory(staffRole, category) {
        if (!category) return true;
        const role = (staffRole || '').toLowerCase();
        if (category === 'Security') {
            return role.includes('security');
        } else if (category === 'Housekeeping') {
            return role.includes('housekeeping');
        } else if (category === 'Maintenance' || category === 'Technical / Plant') {
            return !role.includes('security') && !role.includes('housekeeping');
        }
        return true;
    }

    function renderRosterTable(roster) {
        const container = $('#agency-roster-container');
        const activeCategory = getSelectedMusterCategory();

        // Filter roster strictly for the active target muster's department category
        const filteredRoster = (roster || []).filter(st => isStaffEligibleForCategory(st.role, activeCategory));
        const musterHasPhoto = isSelectedMusterPhotoUploaded();

        if (!filteredRoster || filteredRoster.length === 0) {
            container.html(`
                <div class="text-center py-5 text-muted bg-light rounded border">
                    <p class="mb-2" style="font-size: 2rem;">👤</p>
                    <h6 class="font-weight-bold text-dark mb-1">No Staff Available for Active ${activeCategory || ''} Muster</h6>
                    <p class="mb-0 small text-muted">Showing only personnel matching ${activeCategory || 'active'} department roles.</p>
                    <small>Click <strong>"➕ Onboard Staff"</strong> above if you need to register staff in this category.</small>
                </div>
            `);
            return;
        }

        // DESKTOP TABLE VIEW (Visible on d-none d-md-block)
        let desktopHtml = `
            <div class="d-none d-md-block">
                <table class="table table-hover align-middle mb-0">
                    <thead class="thead-light">
                        <tr>
                            <th>Staff Member</th>
                            <th>Role & Scannable QR</th>
                            <th>Physical Post & Cost Center</th>
                            <th>Status & Shift</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // MOBILE CARD VIEW (Visible on d-block d-md-none)
        let mobileHtml = `<div class="d-block d-md-none">`;

        filteredRoster.forEach(st => {
            const isApproved = st.approval_status === 'Approved';
            const isOnDuty = st.is_on_duty;

            let badgeApproval = '';
            if (st.approval_status === 'Pending') {
                badgeApproval = '<span class="badge badge-warning text-dark">⏳ Pending Approval</span>';
            } else if (st.approval_status === 'Approved') {
                badgeApproval = '<span class="badge badge-success">✅ Approved</span>';
            } else {
                badgeApproval = '<span class="badge badge-danger">❌ Rejected</span>';
            }

            let dutyBadge = isOnDuty 
                ? '<span class="badge badge-success px-2 py-1">🟢 On Duty</span>'
                : '<span class="badge badge-secondary px-2 py-1">⚪ Off Duty</span>';

            let punchTimes = '<span class="text-muted small">No punch today</span>';
            if (st.in_time) {
                const inTimeFormatted = st.in_time.substring(11, 16);
                const outTimeFormatted = st.out_time ? st.out_time.substring(11, 16) : null;
                if (outTimeFormatted) {
                    punchTimes = `<span class="small text-muted font-weight-bold">In: ${inTimeFormatted} &bull; Out: ${outTimeFormatted}</span>`;
                } else {
                    punchTimes = `<span class="small text-success font-weight-bold">In: ${inTimeFormatted} (Active Shift)</span>`;
                }
            }

            const postDisplay = st.duty_post 
                ? `<span class="font-weight-bold text-dark">📍 ${frappe.utils.escape_html(st.duty_post)}</span>`
                : `<span class="text-muted small font-italic">Unassigned Post</span>`;

            const ccDisplay = st.cost_center 
                ? `<div class="small text-primary font-family-monospace font-weight-bold">💼 ${frappe.utils.escape_html(st.cost_center)}</div>`
                : `<div class="small text-muted font-family-monospace">No Cost Center</div>`;

            // Desktop Buttons
            let desktopActions = '';
            // Mobile Buttons
            let mobileActions = '';

            if (!isApproved) {
                desktopActions = `<small class="text-muted font-italic">Awaiting Approval</small>`;
                mobileActions = `<div class="text-center text-muted small font-italic py-1">Awaiting Committee Approval</div>`;
            } else if (!musterHasPhoto && !isOnDuty) {
                desktopActions = `
                    <button class="btn btn-sm btn-outline-secondary font-weight-bold mr-1" disabled title="Shift Lineup Photo is mandatory! Upload photo next to Active Target Muster to enable punch-in.">
                        🔒 Photo Required
                    </button>
                    <button class="btn btn-sm btn-light text-muted border" disabled>
                        📍 Assign Post
                    </button>
                `;
                mobileActions = `
                    <button class="btn btn-outline-secondary btn-block font-weight-bold mb-2 py-2" disabled title="Shift Lineup Photo is mandatory! Upload photo next to Active Target Muster to enable punch-in.">
                        🔒 Punch In Locked (Photo Required)
                    </button>
                `;
            } else {
                const punchBtnDesktop = isOnDuty
                    ? `<button class="btn btn-sm btn-outline-danger btn-agency-punch font-weight-bold mr-1" data-id="${st.staff_id}" data-punch="in">⏹️ Punch Out</button>`
                    : `<button class="btn btn-sm btn-success btn-agency-punch font-weight-bold mr-1" data-id="${st.staff_id}" data-punch="out">▶️ Punch In</button>`;
                
                // Assign Post button is active ONLY when staff is punched in / on duty
                const assignBtnDesktop = isOnDuty ? `
                    <button class="btn btn-sm btn-outline-primary btn-assign-duty font-weight-bold" 
                            data-id="${st.staff_id}" 
                            data-name="${frappe.utils.escape_html(st.full_name)}" 
                            data-role="${frappe.utils.escape_html(st.role)}"
                            data-post="${frappe.utils.escape_html(st.duty_post || '')}"
                            data-att-id="${st.attendance_id || ''}">
                        📍 Assign Post
                    </button>
                ` : `
                    <button class="btn btn-sm btn-light text-muted border" disabled title="Staff must be punched in before assigning duty post">
                        📍 Assign Post
                    </button>
                `;
                desktopActions = punchBtnDesktop + assignBtnDesktop;

                const punchBtnMobile = isOnDuty
                    ? `<button class="btn btn-danger btn-block btn-agency-punch font-weight-bold mb-2 py-2" data-id="${st.staff_id}" data-punch="in">⏹️ Punch Out</button>`
                    : `<button class="btn btn-success btn-block btn-agency-punch font-weight-bold mb-2 py-2" data-id="${st.staff_id}" data-punch="out">▶️ Punch In</button>`;

                const assignBtnMobile = isOnDuty ? `
                    <button class="btn btn-outline-primary btn-block btn-assign-duty font-weight-bold py-2" 
                            data-id="${st.staff_id}" 
                            data-name="${frappe.utils.escape_html(st.full_name)}" 
                            data-role="${frappe.utils.escape_html(st.role)}"
                            data-post="${frappe.utils.escape_html(st.duty_post || '')}"
                            data-att-id="${st.attendance_id || ''}">
                        📍 Assign Duty Post / Block
                    </button>
                ` : `
                    <button class="btn btn-light text-muted btn-block py-2 border mb-0" disabled>
                        📍 Assign Post (Punch-in Required)
                    </button>
                `;
                mobileActions = punchBtnMobile + assignBtnMobile;
            }

            // Desktop Row
            desktopHtml += `
                <tr>
                    <td>
                        <div class="font-weight-bold text-dark">${frappe.utils.escape_html(st.full_name)}</div>
                        <small class="text-muted font-family-monospace">${st.staff_id} &bull; 📞 ${frappe.utils.escape_html(st.contact_number || 'N/A')}</small>
                    </td>
                    <td>
                        <div class="font-weight-bold">${frappe.utils.escape_html(st.role)}</div>
                        <div class="mt-1"><span class="badge badge-light border font-family-monospace text-secondary">🪪 ${frappe.utils.escape_html(st.qr_code_id || 'N/A')}</span></div>
                    </td>
                    <td>
                        <div>${postDisplay}</div>
                        ${ccDisplay}
                    </td>
                    <td>
                        <div class="mb-1">${dutyBadge} &bull; ${badgeApproval}</div>
                        <div>${punchTimes}</div>
                    </td>
                    <td class="text-right">
                        ${desktopActions}
                    </td>
                </tr>
            `;

            // Mobile Card Item (Stacked layout, zero horizontal scroll)
            const borderCol = !isApproved ? '#ffc107' : (isOnDuty ? '#28a745' : '#6c757d');
            mobileHtml += `
                <div class="card mb-3 shadow-sm border p-3 bg-white" style="border-left: 5px solid ${borderCol} !important;">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>${dutyBadge}</div>
                        <div>${badgeApproval}</div>
                    </div>
                    
                    <h5 class="font-weight-bold text-dark mb-1">${frappe.utils.escape_html(st.full_name)}</h5>
                    <div class="small text-muted mb-2">
                        <span class="badge badge-info bg-info text-white mr-1">${frappe.utils.escape_html(st.role)}</span>
                        <code>${st.staff_id}</code> &bull; 📞 ${frappe.utils.escape_html(st.contact_number || 'N/A')}
                    </div>

                    <div class="p-2 mb-2 bg-light rounded small">
                        <div><strong>Assigned Duty:</strong> ${postDisplay}</div>
                        <div><strong>Cost Center:</strong> ${ccDisplay}</div>
                        <div class="mt-1 pt-1 border-top"><strong>Shift Timings:</strong> ${punchTimes}</div>
                    </div>

                    <div class="pt-2 border-top">
                        ${mobileActions}
                    </div>
                </div>
            `;
        });

        desktopHtml += `
                    </tbody>
                </table>
            </div>
        `;
        mobileHtml += `</div>`;

        container.html(desktopHtml + mobileHtml);
    }

    function showAlert(type, msg) {
        const alertBox = $('#agency-alert');
        alertBox.removeClass('d-none alert-success alert-danger alert-warning alert-info')
                .addClass('alert-' + type)
                .html(msg);
        $('html, body').animate({ scrollTop: 0 }, 'fast');
        setTimeout(() => {
            alertBox.addClass('d-none');
        }, 5000);
    }
});
