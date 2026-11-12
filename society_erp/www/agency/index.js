frappe.ready(function() {
    let allRoster = [];

    // Load initial dashboard data
    loadAgencyDashboard();

    // Search filter
    $('#agency-search').on('input', function() {
        const query = $(this).val().toLowerCase().trim();
        renderRosterTable(allRoster.filter(item => {
            return (item.full_name && item.full_name.toLowerCase().includes(query)) ||
                   (item.role && item.role.toLowerCase().includes(query)) ||
                   (item.gate_assigned && item.gate_assigned.toLowerCase().includes(query)) ||
                   (item.status && item.status.toLowerCase().includes(query)) ||
                   (item.approval_status && item.approval_status.toLowerCase().includes(query));
        }));
    });

    // Open Onboard Modal
    $('#btn-open-onboard-modal').on('click', function() {
        $('#form-onboard-staff')[0].reset();
        $('#modal-onboard-staff').modal('show');
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
            error: function(err) {
                submitBtn.prop('disabled', false).text('Submit for Committee Approval');
            }
        });
    });

    // Handle Punch Action
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

                    allRoster = data.roster || [];
                    renderRosterTable(allRoster);
                }
            }
        });
    }

    function renderRosterTable(roster) {
        const container = $('#agency-roster-container');
        if (!roster || roster.length === 0) {
            container.html(`
                <div class="text-center py-5 text-muted">
                    <p class="mb-2" style="font-size: 2rem;">👤</p>
                    <p class="mb-0">No staff members found in roster.</p>
                    <small>Click <strong>"➕ Onboard New Staff"</strong> above to register staff.</small>
                </div>
            `);
            return;
        }

        let html = `
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0">
                    <thead class="thead-light">
                        <tr>
                            <th>Staff Member</th>
                            <th>Role & Gate</th>
                            <th>Status & Approval</th>
                            <th>Today's Shift</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        roster.forEach(st => {
            const isApproved = st.approval_status === 'Approved';
            const isOnDuty = st.is_on_duty;
            const punch = st.today_punch;

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
            if (punch && punch.in_time) {
                const inTimeFormatted = punch.in_time.substring(11, 16);
                const outTimeFormatted = punch.out_time ? punch.out_time.substring(11, 16) : null;
                if (outTimeFormatted) {
                    punchTimes = `<span class="small text-muted font-weight-bold">In: ${inTimeFormatted} &bull; Out: ${outTimeFormatted}</span>`;
                } else {
                    punchTimes = `<span class="small text-success font-weight-bold">In: ${inTimeFormatted} (Active Shift)</span>`;
                }
            }

            let actionBtn = '';
            if (!isApproved) {
                actionBtn = `<small class="text-muted font-italic">Awaiting Committee Sign-off</small>`;
            } else if (isOnDuty) {
                actionBtn = `
                    <button class="btn btn-sm btn-outline-danger btn-agency-punch font-weight-bold" data-id="${st.name}" data-punch="in">
                        ⏹️ Punch Out
                    </button>
                `;
            } else {
                actionBtn = `
                    <button class="btn btn-sm btn-success btn-agency-punch font-weight-bold" data-id="${st.name}" data-punch="out">
                        ▶️ Punch In
                    </button>
                `;
            }

            html += `
                <tr>
                    <td>
                        <div class="font-weight-bold text-dark">${frappe.utils.escape_html(st.full_name)}</div>
                        <small class="text-muted font-family-monospace">${st.name} &bull; 📞 ${frappe.utils.escape_html(st.contact_number || 'N/A')}</small>
                    </td>
                    <td>
                        <div class="font-weight-bold">${frappe.utils.escape_html(st.role)}</div>
                        <small class="text-muted">📍 ${frappe.utils.escape_html(st.gate_assigned || 'All Gates')}</small>
                    </td>
                    <td>
                        <div class="mb-1">${badgeApproval}</div>
                        <div>${dutyBadge}</div>
                    </td>
                    <td>
                        <div>${punchTimes}</div>
                        ${punch && punch.shift ? `<small class="text-muted">${punch.shift}</small>` : ''}
                    </td>
                    <td class="text-right">
                        ${actionBtn}
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
