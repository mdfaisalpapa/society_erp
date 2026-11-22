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
                    let data = (r.message && r.message.data) ? r.message.data : r.message;
                    if (data && data.makes) {
                        data.makes.forEach(m => $make.append(new Option(m.make_name || m.name, m.name)));
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
                    let data = (r.message && r.message.data) ? r.message.data : r.message;
                    if (data && data.models) {
                        data.models.forEach(m => $model.append(new Option(m.model_name || m.name, m.name)));
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

    // Set default payment date to today
    if ($('#payment_date').length && !$('#payment_date').val()) {
        const todayStr = new Date().toISOString().split('T')[0];
        $('#payment_date').val(todayStr);
    }

    // Helper to parse UPI text (from pasted text or text files)
    function parseAndPopulateUPIText(rawText) {
        if (!rawText) return false;
        
        // Regex 1: Explicit labels (Google Pay, PhonePe, Paytm, BHIM)
        // e.g. "UPI transaction ID: 632391942268" or "Google transaction ID: CICAg..." or "UTR: 412389123456"
        let utr = null;
        const utrLabelRegex = /(?:UPI\s*(?:transaction\s*ID|Ref\s*No|UTR|Reference)|UTR(?:\s*No)?)\s*[:\n\r\s]+([0-9]{12})/i;
        const labelMatch = rawText.match(utrLabelRegex);
        if (labelMatch) {
            utr = labelMatch[1];
        } else {
            // Regex 2: Any 12 consecutive digits
            const digitMatch = rawText.match(/\b([0-9]{12})\b/);
            if (digitMatch) {
                utr = digitMatch[1];
            }
        }

        if (utr) {
            $('#payment_reference_no').val(utr);
        }

        // Date extraction e.g. "19 Nov 2026" or "19/11/2026" or "2026-11-19"
        const dateRegex = /(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})/i;
        const dateMatch = rawText.match(dateRegex);
        if (dateMatch) {
            const months = {jan:"01",feb:"02",mar:"03",apr:"04",may:"05",jun:"06",jul:"07",aug:"08",sep:"09",oct:"10",nov:"11",dec:"12"};
            const mm = months[dateMatch[2].toLowerCase().slice(0,3)] || "01";
            const dd = String(dateMatch[1]).padStart(2, '0');
            const yyyy = dateMatch[3];
            $('#payment_date').val(`${yyyy}-${mm}-${dd}`);
        }

        return Boolean(utr);
    }

    // 1-Click Clipboard Paste button for Mobile & Desktop
    $('#btn-paste-clipboard').on('click', async function() {
        if (navigator.clipboard && navigator.clipboard.readText) {
            try {
                const clipText = await navigator.clipboard.readText();
                if (clipText) {
                    if (parseAndPopulateUPIText(clipText)) {
                        const utr = $('#payment_reference_no').val();
                        $('#ocr_status').show().html(`✅ Pasted UTR: <strong class="text-success">${utr}</strong> from clipboard!`);
                    } else {
                        // If user just copied the raw 12 digits directly
                        const cleanDigits = clipText.replace(/\D/g, '');
                        if (cleanDigits.length === 12) {
                            $('#payment_reference_no').val(cleanDigits);
                            $('#ocr_status').show().html(`✅ Pasted 12-digit UTR: <strong class="text-success">${cleanDigits}</strong>!`);
                        } else {
                            $('#payment_reference_no').val(clipText.trim());
                        }
                    }
                }
            } catch (err) {
                // Clipboard permission blocked; focus field so user can paste natively
                $('#payment_reference_no').focus();
            }
        } else {
            $('#payment_reference_no').focus();
        }
    });

    // Client-side ephemeral screenshot / shared file OCR reader using Tesseract.js (processes locally in browser)
    $('#upi_screenshot_file').on('change', async function(e) {
        const file = e.target.files[0];
        if (!file) return;

        const $status = $('#ocr_status').show().html('⏳ <span class="spinner-border spinner-border-sm" role="status"></span> Scanning receipt / file for UPI details...');

        // 1. If user uploaded a text file or shared receipt file
        if (file.type === "text/plain" || file.name.endsWith(".txt")) {
            const reader = new FileReader();
            reader.onload = function(evt) {
                if (parseAndPopulateUPIText(evt.target.result)) {
                    const utr = $('#payment_reference_no').val();
                    $status.html(`✅ Extracted UTR: <strong class="text-success">${utr}</strong> from shared receipt file!`);
                } else {
                    $status.html('⚠️ Could not detect 12-digit UTR. Please enter it manually below.');
                }
            };
            reader.readAsText(file);
            return;
        }

        // 2. Quick check: If 12-digit UTR is already in the filename
        const nameMatch = file.name.match(/\b\d{12}\b/);
        if (nameMatch) {
            $('#payment_reference_no').val(nameMatch[0]);
            $status.html('✅ Extracted 12-digit UTR <strong>' + nameMatch[0] + '</strong> from filename!');
            return;
        }

        // 3. Perform OCR via Tesseract.js in the browser (for images)
        if (window.Tesseract && window.Tesseract.recognize) {
            try {
                const res = await window.Tesseract.recognize(file, 'eng', {
                    logger: m => {
                        if (m && m.status === 'recognizing text' && m.progress) {
                            $status.html(`🔍 OCR scanning in progress (${Math.round(m.progress * 100)}%)...`);
                        }
                    }
                });

                const text = (res && res.data && res.data.text) || '';
                if (parseAndPopulateUPIText(text)) {
                    const utr = $('#payment_reference_no').val();
                    $status.html(`✅ Extracted UTR: <strong class="text-success">${utr}</strong>! Please verify.`);
                } else {
                    $status.html('⚠️ UTR not detected (GPay may have hidden it in screenshot). Tap <strong>Share Receipt</strong> in GPay and paste the text or share image.');
                }

            } catch (err) {
                console.warn('OCR Recognition failed:', err);
                $status.html('ℹ️ Screenshot loaded. Please enter the 12-digit UPI UTR Number below.');
            }
        } else {
            $status.html('ℹ️ Screenshot loaded. Please enter the 12-digit UPI UTR Number below.');
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

        let utrNo = ($('#payment_reference_no').val() || '').trim();
        if (!utrNo || utrNo.length < 5) {
            frappe.msgprint({title: 'Payment Details Missing', message: 'Please enter at least the last 5 digits of the UPI Transaction ID / UTR.', indicator: 'red'});
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
                    payment_reference_no: utrNo,
                    payment_date: $('#payment_date').val(),
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

    // Helper: Natively upload file to Frappe using jQuery AJAX (Most resilient for Web Portals) with 1MB Validation
    function upload_file(file) {
        return new Promise((resolve, reject) => {
            if (file && file.size > 1 * 1024 * 1024) {
                frappe.msgprint({
                    title: 'File Too Large',
                    message: `File <b>${file.name}</b> exceeds the <b>1 MB</b> limit. Please upload a smaller file.`,
                    indicator: 'red'
                });
                return reject(new Error('File exceeds 1 MB'));
            }

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
        let $cards = $('#history-cards-body').empty().append('<div class="text-center py-3 text-muted">Loading...</div>');

        frappe.call({
            method: 'society_erp.vehicle_portal.get_parking_history',
            args: { slot_id: slot_id },
            callback: function(r) {
                $tbody.empty();
                $cards.empty();
                if (r.message && r.message.length > 0) {
                    r.message.forEach(h => {
                        let statusIcon = h.status === 'Active' ? '🟢' : '⚪';
                        // Desktop Table Row
                        $tbody.append(`
                            <tr>
                                <td>${statusIcon} ${h.status}</td>
                                <td>${h.allocation_type}</td>
                                <td>Flat ${h.occupied_by}</td>
                                <td>${h.start_date || 'Unknown'}</td>
                                <td>${h.end_date || 'Present'}</td>
                            </tr>
                        `);
                        // Mobile Card
                        $cards.append(`
                            <div class="card mb-2 p-3 bg-white border rounded shadow-sm">
                                <div class="d-flex justify-content-between align-items-start mb-1">
                                    <div>
                                        <div class="font-weight-bold text-dark">${statusIcon} ${h.allocation_type}</div>
                                        <small class="text-muted">Occupied by: Flat <strong>${h.occupied_by}</strong></small>
                                    </div>
                                    <span class="badge badge-${h.status === 'Active' ? 'success' : 'secondary'} px-2 py-1">${h.status}</span>
                                </div>
                                <div class="d-flex justify-content-between align-items-center small text-muted pt-2 border-top mt-1">
                                    <span>From: <strong>${h.start_date || 'Unknown'}</strong></span>
                                    <span>To: <strong>${h.end_date || 'Present'}</strong></span>
                                </div>
                            </div>
                        `);
                    });
                } else {
                    $tbody.append('<tr><td colspan="5" class="text-center text-muted">No history found.</td></tr>');
                    $cards.append('<div class="text-center py-4 text-muted">No history found.</div>');
                }
            }
        });
    });
