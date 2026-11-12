/**
 * Committee Member Portal Client Script
 * Handles real-time search, responsive card & table rendering, approval/rejection actions, and notice posting.
 */
frappe.ready(function () {
    const $loading = $("#committee-loading");
    const $panes = $("#committeeTabPanes");
    const $searchInput = $("#committee-search-input");
    const $switchPending = $("#switch-pending-only");
    const $selectResolutionFilter = $("#select-resolution-filter");
    const $filterResGroup = $("#filter-resolutions-group");
    const $filterPendingSwitchGroup = $("#filter-pending-switch-group");
    const $alert = $("#committee-alert");

    // Modal elements
    const $actionModal = $("#modal-action-confirm");
    const $actionTitle = $("#modalActionTitle");
    const $actionSummary = $("#modal-action-summary");
    const $actionRemarks = $("#action-remarks");
    const $btnConfirmAction = $("#btn-confirm-action");

    const $noticeModal = $("#modal-post-notice");
    const $btnSubmitNotice = $("#btn-submit-notice");

    let committeeData = {
        tenants: [],
        vehicles: [],
        work_permits: [],
        family: [],
        pets: [],
        tickets: [],
        notices: [],
        resolutions: [],
        facility_bookings: [],
        classifieds: [],
        facility_staff: [],
        facility_musters: [],
        counts: {}
    };

    let pendingActionData = null;

    function showAlert(msg, type) {
        $alert.removeClass("d-none alert-success alert-danger alert-info alert-warning")
              .addClass("alert-" + (type || "info"))
              .html(msg);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    function hideAlert() {
        $alert.addClass("d-none").empty();
    }

    function escapeHtml(str) {
        if (!str) return "";
        return $("<div>").text(str).html();
    }

    function formatDate(val) {
        if (!val) return "-";
        // Parse YYYY-MM-DD or ISO string and format as DD-MM-YYYY
        const clean = val.split(" ")[0].split("T")[0];
        const parts = clean.split("-");
        if (parts.length === 3 && parts[0].length === 4) {
            return `${parts[2]}-${parts[1]}-${parts[0]}`;
        }
        return clean;
    }

    function getStatusBadge(status) {
        const s = (status || "").toLowerCase();
        if (s.includes("pending") || s.includes("unverified")) {
            return `<span class="badge badge-warning text-dark font-weight-bold">⏳ ${escapeHtml(status)}</span>`;
        } else if (s.includes("approved") || s.includes("verified") || s.includes("resolved") || s.includes("active")) {
            return `<span class="badge badge-success font-weight-bold">✅ ${escapeHtml(status)}</span>`;
        } else if (s.includes("rejected") || s.includes("revoked") || s.includes("inactive")) {
            return `<span class="badge badge-danger font-weight-bold">❌ ${escapeHtml(status)}</span>`;
        } else if (s.includes("open")) {
            return `<span class="badge badge-danger font-weight-bold">🚨 ${escapeHtml(status)}</span>`;
        } else if (s.includes("assigned")) {
            return `<span class="badge badge-info font-weight-bold">👷 ${escapeHtml(status)}</span>`;
        }
        return `<span class="badge badge-secondary font-weight-bold">${escapeHtml(status || 'None')}</span>`;
    }

    function isPending(item, module) {
        if (module === "tenants") return item.registration_status === "Pending" || item.registration_status === "Unverified";
        if (module === "vehicles") return item.approval_status === "Pending";
        if (module === "work_permits") return item.status === "Pending";
        if (module === "family") return item.registration_status === "Pending";
        if (module === "pets") return item.approval_status === "Pending";
        if (module === "tickets") return item.status === "Open" || item.status === "Assigned";
        if (module === "facility_bookings") return item.status === "Pending Approval";
        if (module === "classifieds") return item.approval_status === "Pending Approval";
        if (module === "resolutions") return item.user_status === "Pending" && (item.status === "Circulated" || item.status === "Draft");
        return false;
    }

    function updateBadgeCounts(counts) {
        $("#badge-tenants").text(counts.tenants_pending || 0);
        $("#badge-vehicles").text(counts.vehicles_pending || 0);
        $("#badge-permits").text(counts.permits_pending || 0);
        $("#badge-family").text(counts.family_pending || 0);
        $("#badge-pets").text(counts.pets_pending || 0);
        $("#badge-tickets").text(counts.tickets_open || 0);
        $("#badge-facility_bookings").text(counts.facility_bookings_pending || 0);
        $("#badge-classifieds").text(counts.classifieds_pending || 0);
        $("#badge-resolutions").text(counts.resolutions_pending || 0);
    }

    // --- Render Modules ---

    function renderTenants(items) {
        const $cont = $("#container-tenants").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No tenant records found.</div>`);
            return;
        }

        // 1. Desktop Table
        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Tenant Name</th>
                            <th>Contact</th>
                            <th>Lease Period</th>
                            <th>Documents</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // 2. Mobile Cards
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(t => {
            const isPend = t.registration_status === "Pending" || t.registration_status === "Unverified";
            const borderClass = isPend ? "border-pending" : (t.registration_status === "Rejected" ? "border-rejected" : "border-approved");

            const docs = [];
            if (t.rental_agreement) docs.push(`<a href="${t.rental_agreement}" target="_blank" class="badge badge-light border mr-1">📄 Lease</a>`);
            if (t.police_verification) docs.push(`<a href="${t.police_verification}" target="_blank" class="badge badge-light border mr-1">👮 Police</a>`);
            if (t.id_proof) docs.push(`<a href="${t.id_proof}" target="_blank" class="badge badge-light border mr-1">🪪 ID</a>`);
            const docsHtml = docs.length ? docs.join("") : `<span class="text-muted small">None</span>`;

            // Desktop Row
            tableHtml += `
                <tr>
                    <td><span class="comm-flat-badge">${escapeHtml(t.flat)}</span></td>
                    <td class="font-weight-bold text-dark">${escapeHtml(t.tenant_name)}</td>
                    <td class="small">
                        <div class="contact-box" data-doctype="Tenants" data-docname="${t.name}">
                            <div>📞 <span class="contact-phone">${escapeHtml(t.mobile_no || '-')}</span></div>
                            <div>✉️ <span class="contact-email">${escapeHtml(t.email || '-')}</span></div>
                            ${t.mobile_no && t.mobile_no.includes('*') ? `
                                <button type="button" class="btn btn-link btn-sm p-0 font-weight-bold text-primary btn-reveal-contact" style="font-size: 0.72rem;" data-doctype="Tenants" data-docname="${t.name}">
                                    👁️ Unmask Contact
                                </button>
                            ` : ''}
                        </div>
                    </td>
                    <td class="small text-muted">${formatDate(t.start_date)} to ${formatDate(t.end_date)}</td>
                    <td>${docsHtml}</td>
                    <td>${getStatusBadge(t.registration_status)}</td>
                    <td class="text-right">
                        ${isPend ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Tenants" data-docname="${t.name}" data-action="Verified Physically" data-title="Approve & Verify Tenant">
                                ✅ Verify
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Tenants" data-docname="${t.name}" data-action="Rejected" data-title="Reject Tenant Application">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">Processed</span>`}
                    </td>
                </tr>
            `;

            // Mobile Card
            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="comm-flat-badge">${escapeHtml(t.flat)}</span>
                        ${getStatusBadge(t.registration_status)}
                    </div>
                    <div class="h6 font-weight-bold text-dark mb-1">${escapeHtml(t.tenant_name)}</div>
                    <div class="small text-muted mb-2 contact-box" data-doctype="Tenants" data-docname="${t.name}">
                        <div>
                            📞 <span class="contact-phone">${escapeHtml(t.mobile_no || '-')}</span> &bull; 
                            ✉️ <span class="contact-email">${escapeHtml(t.email || '-')}</span>
                            ${t.mobile_no && t.mobile_no.includes('*') ? `
                                <button type="button" class="btn btn-link btn-sm p-0 ml-1 font-weight-bold text-primary btn-reveal-contact" style="font-size: 0.75rem;" data-doctype="Tenants" data-docname="${t.name}">
                                    👁️ Unmask
                                </button>
                            ` : ''}
                        </div>
                        <div>📅 Period: ${formatDate(t.start_date)} to ${formatDate(t.end_date)}</div>
                    </div>
                    <div class="mb-3">
                        <small class="text-muted font-weight-bold mr-1">Documents:</small> ${docsHtml}
                    </div>
                    ${isPend ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Tenants" data-docname="${t.name}" data-action="Verified Physically" data-title="Approve & Verify Tenant">
                                ✅ Verify Tenant
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm font-weight-bold btn-action" data-doctype="Tenants" data-docname="${t.name}" data-action="Rejected" data-title="Reject Tenant Application">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderVehicles(items) {
        const $cont = $("#container-vehicles").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No vehicle records found.</div>`);
            return;
        }

        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Vehicle No</th>
                            <th>Type & Model</th>
                            <th>Resident / Owner</th>
                            <th>Documents</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(v => {
            const isPend = v.approval_status === "Pending";
            const borderClass = isPend ? "border-pending" : (v.approval_status === "Rejected" ? "border-rejected" : "border-approved");

            const docs = [];
            if (v.rc_copy) docs.push(`<a href="${v.rc_copy}" target="_blank" class="badge badge-light border mr-1">📄 RC Copy</a>`);
            if (v.noc) docs.push(`<a href="${v.noc}" target="_blank" class="badge badge-light border mr-1">📄 NOC</a>`);
            const docsHtml = docs.length ? docs.join("") : `<span class="text-muted small">None</span>`;

            tableHtml += `
                <tr>
                    <td><span class="comm-flat-badge">${escapeHtml(v.flat)}</span></td>
                    <td class="font-weight-bold text-dark font-monospace">${escapeHtml(v.registration_number)}</td>
                    <td class="small">
                        <div><strong>${escapeHtml(v.vehicle_type)}</strong> (${escapeHtml(v.color || '-')})</div>
                        <div class="text-muted">${escapeHtml(v.make || '')} ${escapeHtml(v.model || '')}</div>
                    </td>
                    <td class="small">
                        <div>${escapeHtml(v.registered_owner_name || '-')}</div>
                        <span class="badge badge-light text-muted border">${escapeHtml(v.relationship_to_resident || v.belongs_to || 'Resident')}</span>
                    </td>
                    <td>${docsHtml}</td>
                    <td>${getStatusBadge(v.approval_status)}</td>
                    <td class="text-right">
                        ${isPend ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Resident Vehicle" data-docname="${v.name}" data-action="Approved" data-title="Approve Vehicle Sticker">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Resident Vehicle" data-docname="${v.name}" data-action="Rejected" data-title="Reject Vehicle Registration">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">Processed</span>`}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="comm-flat-badge">${escapeHtml(v.flat)}</span>
                        ${getStatusBadge(v.approval_status)}
                    </div>
                    <div class="h6 font-weight-bold text-dark mb-1 font-monospace">${escapeHtml(v.registration_number)}</div>
                    <div class="small text-muted mb-2">
                        <div>🚗 ${escapeHtml(v.vehicle_type)} &bull; ${escapeHtml(v.make || '')} ${escapeHtml(v.model || '')} (${escapeHtml(v.color || '-')})</div>
                        <div>👤 Reg Owner: ${escapeHtml(v.registered_owner_name || '-')} (${escapeHtml(v.relationship_to_resident || 'Self')})</div>
                    </div>
                    <div class="mb-3">
                        <small class="text-muted font-weight-bold mr-1">Documents:</small> ${docsHtml}
                    </div>
                    ${isPend ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Resident Vehicle" data-docname="${v.name}" data-action="Approved" data-title="Approve Vehicle Registration">
                                ✅ Approve Sticker
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm font-weight-bold btn-action" data-doctype="Resident Vehicle" data-docname="${v.name}" data-action="Rejected" data-title="Reject Vehicle Registration">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderWorkPermits(items) {
        const $cont = $("#container-work_permits").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No work permits found.</div>`);
            return;
        }

        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Permit ID</th>
                            <th>Work Type</th>
                            <th>Contractor</th>
                            <th>Validity</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(w => {
            const isPend = w.status === "Pending";
            const borderClass = isPend ? "border-pending" : (w.status === "Rejected" ? "border-rejected" : "border-approved");

            tableHtml += `
                <tr>
                    <td><span class="comm-flat-badge">${escapeHtml(w.flat_number)}</span></td>
                    <td class="font-weight-bold">${escapeHtml(w.name)}</td>
                    <td><span class="badge badge-light border text-dark">${escapeHtml(w.work_type || 'General')}</span></td>
                    <td class="small">${escapeHtml(w.contractor_name || '-')}</td>
                    <td class="small text-muted">${formatDate(w.start_date)} to ${formatDate(w.end_date)}</td>
                    <td>${getStatusBadge(w.status)}</td>
                    <td class="text-right">
                        ${isPend ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Work Permit" data-docname="${w.name}" data-action="Approved" data-title="Approve Work Permit">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Work Permit" data-docname="${w.name}" data-action="Rejected" data-title="Reject Work Permit">
                                ❌ Reject
                            </button>
                        ` : `
                            ${w.status === 'Approved' ? `
                                <button type="button" class="btn btn-sm btn-outline-secondary py-1 px-2 btn-action" data-doctype="Work Permit" data-docname="${w.name}" data-action="Completed" data-title="Mark Work Permit Completed">
                                    🏁 Complete
                                </button>
                            ` : `<span class="text-muted small">Closed</span>`}
                        `}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="comm-flat-badge">${escapeHtml(w.flat_number)}</span>
                        ${getStatusBadge(w.status)}
                    </div>
                    <div class="h6 font-weight-bold text-dark mb-1">Permit: ${escapeHtml(w.name)}</div>
                    <div class="small text-muted mb-2">
                        <div>🔨 Work: <strong>${escapeHtml(w.work_type || 'General')}</strong> &bull; Contractor: ${escapeHtml(w.contractor_name || '-')}</div>
                        <div>📅 Validity: ${formatDate(w.start_date)} to ${formatDate(w.end_date)}</div>
                        ${w.remarks ? `<div class="mt-1 text-dark"><em>Note:</em> ${escapeHtml(w.remarks)}</div>` : ''}
                    </div>
                    ${isPend ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Work Permit" data-docname="${w.name}" data-action="Approved" data-title="Approve Work Permit">
                                ✅ Approve Permit
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm font-weight-bold btn-action" data-doctype="Work Permit" data-docname="${w.name}" data-action="Rejected" data-title="Reject Work Permit">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderFamily(items) {
        const $cont = $("#container-family").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No family member records found.</div>`);
            return;
        }

        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Member Name</th>
                            <th>Relationship</th>
                            <th>Contact</th>
                            <th>ID Document</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(f => {
            const isPend = f.registration_status === "Pending";
            const borderClass = isPend ? "border-pending" : (f.registration_status === "Rejected" ? "border-rejected" : "border-approved");

            const docLink = f.id_proof_document
                ? `<a href="${f.id_proof_document}" target="_blank" class="badge badge-light border">🪪 ${escapeHtml(f.id_proof_type || 'View ID')}</a>`
                : `<span class="text-muted small">None</span>`;

            tableHtml += `
                <tr>
                    <td><span class="comm-flat-badge">${escapeHtml(f.parent_flat)}</span></td>
                    <td class="font-weight-bold text-dark">${escapeHtml(f.member_name)}</td>
                    <td><span class="badge badge-light border">${escapeHtml(f.relationship || 'Family')}</span></td>
                    <td class="small">
                        <div class="contact-box" data-doctype="Family Members" data-docname="${f.name}">
                            📞 <span class="contact-phone">${escapeHtml(f.mobile_no || '-')}</span>
                            ${f.mobile_no && f.mobile_no.includes('*') ? `
                                <div>
                                    <button type="button" class="btn btn-link btn-sm p-0 font-weight-bold text-primary btn-reveal-contact" style="font-size: 0.72rem;" data-doctype="Family Members" data-docname="${f.name}">
                                        👁️ Unmask
                                    </button>
                                </div>
                            ` : ''}
                        </div>
                    </td>
                    <td>${docLink}</td>
                    <td>${getStatusBadge(f.registration_status)}</td>
                    <td class="text-right">
                        ${isPend ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Family Members" data-docname="${f.name}" data-action="Verified" data-title="Approve Family Member">
                                ✅ Verify
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Family Members" data-docname="${f.name}" data-action="Rejected" data-title="Reject Family Member">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">Processed</span>`}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="comm-flat-badge">${escapeHtml(f.parent_flat)}</span>
                        ${getStatusBadge(f.registration_status)}
                    </div>
                    <div class="h6 font-weight-bold text-dark mb-1">${escapeHtml(f.member_name)}</div>
                    <div class="small text-muted mb-2 contact-box" data-doctype="Family Members" data-docname="${f.name}">
                        <div>
                            👥 Relationship: <strong>${escapeHtml(f.relationship || 'Family')}</strong> &bull; 
                            📞 <span class="contact-phone">${escapeHtml(f.mobile_no || '-')}</span>
                            ${f.mobile_no && f.mobile_no.includes('*') ? `
                                <button type="button" class="btn btn-link btn-sm p-0 ml-1 font-weight-bold text-primary btn-reveal-contact" style="font-size: 0.75rem;" data-doctype="Family Members" data-docname="${f.name}">
                                    👁️ Unmask
                                </button>
                            ` : ''}
                        </div>
                        <div class="mt-1">Document: ${docLink}</div>
                    </div>
                    ${isPend ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Family Members" data-docname="${f.name}" data-action="Verified" data-title="Approve Family Member">
                                ✅ Verify Member
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm font-weight-bold btn-action" data-doctype="Family Members" data-docname="${f.name}" data-action="Rejected" data-title="Reject Family Member">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderPets(items) {
        const $cont = $("#container-pets").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No resident pets registered.</div>`);
            return;
        }

        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Pet Name</th>
                            <th>License & Vaccination</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(p => {
            const isPend = p.approval_status === "Pending";
            const borderClass = isPend ? "border-pending" : (p.approval_status === "Rejected" ? "border-rejected" : "border-approved");

            tableHtml += `
                <tr>
                    <td><span class="comm-flat-badge">${escapeHtml(p.flat || p.parent)}</span></td>
                    <td class="font-weight-bold text-dark">🐾 ${escapeHtml(p.pet_name)}</td>
                    <td class="small">
                        <div>License: <code>${escapeHtml(p.license_no || '-')}</code> (Exp: ${formatDate(p.license_expiry_date)})</div>
                        <div class="text-muted">Vaccination Due: ${formatDate(p.vaccination_due_date)}</div>
                    </td>
                    <td>${getStatusBadge(p.approval_status)}</td>
                    <td class="text-right">
                        ${isPend ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Resident Pets" data-docname="${p.name}" data-action="Approved" data-title="Approve Pet Registration">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Resident Pets" data-docname="${p.name}" data-action="Rejected" data-title="Reject Pet Registration">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">Processed</span>`}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <span class="comm-flat-badge">${escapeHtml(p.flat || p.parent)}</span>
                        ${getStatusBadge(p.approval_status)}
                    </div>
                    <div class="h6 font-weight-bold text-dark mb-1">🐾 ${escapeHtml(p.pet_name)}</div>
                    <div class="small text-muted mb-2">
                        <div>License No: ${escapeHtml(p.license_no || '-')} (Exp: ${formatDate(p.license_expiry_date)})</div>
                        <div>Vaccination Due: ${formatDate(p.vaccination_due_date)}</div>
                    </div>
                    ${isPend ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Resident Pets" data-docname="${p.name}" data-action="Approved" data-title="Approve Pet Registration">
                                ✅ Approve Pet
                            </button>
                            <button type="button" class="btn btn-outline-danger btn-sm font-weight-bold btn-action" data-doctype="Resident Pets" data-docname="${p.name}" data-action="Rejected" data-title="Reject Pet Registration">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderTickets(items) {
        const $cont = $("#container-tickets").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No maintenance tickets found.</div>`);
            return;
        }

        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Ticket</th>
                            <th>Flat</th>
                            <th>Category & Priority</th>
                            <th>Description</th>
                            <th>Status</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        let cardsHtml = `<div class="d-block d-md-none">`;

        items.forEach(t => {
            const isOpen = t.status === "Open" || t.status === "Assigned";
            const borderClass = t.status === "Open" ? "border-rejected" : (t.status === "Assigned" ? "border-pending" : "border-approved");

            tableHtml += `
                <tr>
                    <td class="font-weight-bold font-monospace">${escapeHtml(t.name)}</td>
                    <td><span class="comm-flat-badge">${escapeHtml(t.resident)}</span></td>
                    <td class="small">
                        <div><strong>${escapeHtml(t.category)}</strong></div>
                        <span class="badge badge-light border">${escapeHtml(t.priority_level || 'Routine')}</span>
                    </td>
                    <td class="small" style="max-width: 280px;">
                        <div class="text-truncate">${escapeHtml(t.description)}</div>
                        ${t.resolution_remarks ? `<div class="text-success small mt-1"><em>Resolution:</em> ${escapeHtml(t.resolution_remarks.slice(0, 80))}…</div>` : ''}
                    </td>
                    <td>${getStatusBadge(t.status)}</td>
                    <td class="text-right">
                        ${t.status === "Open" ? `
                            <button type="button" class="btn btn-sm btn-info py-1 px-2 btn-action" data-doctype="Maintenance Ticket" data-docname="${t.name}" data-action="Assigned" data-title="Assign Ticket to Staff" data-show-remarks="1">
                                👷 Assign
                            </button>
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Maintenance Ticket" data-docname="${t.name}" data-action="Resolved" data-title="Resolve Ticket" data-show-remarks="1">
                                ✅ Resolve
                            </button>
                        ` : (t.status === "Assigned" ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Maintenance Ticket" data-docname="${t.name}" data-action="Resolved" data-title="Mark Resolved" data-show-remarks="1">
                                ✅ Resolve
                            </button>
                        ` : `<span class="text-muted small">Resolved</span>`)}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="font-weight-bold mr-1">${escapeHtml(t.name)}</span>
                            <span class="comm-flat-badge">${escapeHtml(t.resident)}</span>
                        </div>
                        ${getStatusBadge(t.status)}
                    </div>
                    <div class="small mb-2">
                        <span class="badge badge-light border text-dark font-weight-bold mr-1">${escapeHtml(t.category)}</span>
                        <span class="text-muted">${escapeHtml(t.priority_level || 'Routine')}</span>
                    </div>
                    <p class="small text-dark mb-2">${escapeHtml(t.description)}</p>
                    ${t.resolution_remarks ? `
                        <div class="p-2 mb-2 bg-light rounded small text-success border">
                            <strong>Resolution Note:</strong> ${escapeHtml(t.resolution_remarks)}
                        </div>
                    ` : ''}
                    ${isOpen ? `
                        <div class="d-flex pt-2 border-top">
                            ${t.status === 'Open' ? `
                                <button type="button" class="btn btn-info btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Maintenance Ticket" data-docname="${t.name}" data-action="Assigned" data-title="Assign Ticket" data-show-remarks="1">
                                    👷 Assign
                                </button>
                            ` : ''}
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 font-weight-bold btn-action" data-doctype="Maintenance Ticket" data-docname="${t.name}" data-action="Resolved" data-title="Resolve Ticket" data-show-remarks="1">
                                ✅ Mark Resolved
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderFacilityBookings(items) {
        const $cont = $("#container-facility_bookings").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No facility booking requests found.</div>`);
            return;
        }

        // 1. Desktop Table
        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Facility</th>
                            <th>Shift / Slot</th>
                            <th>Date of Booking</th>
                            <th>Status</th>
                            <th>Notes</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // 2. Mobile Cards
        let cardsHtml = `<div class="d-md-none">`;

        items.forEach(b => {
            const isPending = b.status === "Pending Approval";
            let borderClass = isPending ? "border-pending" : (b.status === "Confirmed" || b.status === "Approved" ? "border-approved" : "border-rejected");

            tableHtml += `
                <tr class="${isPending ? 'table-warning-row' : ''}">
                    <td><span class="comm-flat-badge">${escapeHtml(b.resident)}</span></td>
                    <td><strong>${escapeHtml(b.facility)}</strong></td>
                    <td><span class="badge badge-light border">${escapeHtml(b.shift || 'Full Day')}</span></td>
                    <td>${escapeHtml(b.formatted_booking_date || b.booking_date)}</td>
                    <td>${getStatusBadge(b.status)}</td>
                    <td class="small text-muted">${escapeHtml(b.remarks || '-')}</td>
                    <td class="text-right">
                        ${isPending ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Facility Booking" data-docname="${b.name}" data-action="Approved" data-title="Approve Booking for ${escapeHtml(b.resident)}" data-show-remarks="1">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-sm btn-danger py-1 px-2 btn-action" data-doctype="Facility Booking" data-docname="${b.name}" data-action="Rejected" data-title="Reject Booking for ${escapeHtml(b.resident)}" data-show-remarks="1">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">${escapeHtml(b.status)}</span>`}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="comm-flat-badge mr-2">${escapeHtml(b.resident)}</span>
                            <span class="font-weight-bold text-dark">${escapeHtml(b.facility)}</span>
                        </div>
                        ${getStatusBadge(b.status)}
                    </div>
                    <div class="small text-muted mb-1">
                        ⏰ <strong>Shift:</strong> ${escapeHtml(b.shift || 'Full Day')}
                    </div>
                    <div class="small text-muted mb-2">
                        📅 <strong>Date:</strong> ${escapeHtml(b.formatted_booking_date || b.booking_date)}
                    </div>
                    ${b.remarks ? `<div class="small text-secondary mb-2 bg-light p-2 rounded">${escapeHtml(b.remarks)}</div>` : ''}
                    ${isPending ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Facility Booking" data-docname="${b.name}" data-action="Approved" data-title="Approve Booking for ${escapeHtml(b.resident)}" data-show-remarks="1">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-danger btn-sm flex-grow-1 font-weight-bold btn-action" data-doctype="Facility Booking" data-docname="${b.name}" data-action="Rejected" data-title="Reject Booking for ${escapeHtml(b.resident)}" data-show-remarks="1">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderClassifieds(items) {
        const $cont = $("#container-classifieds").empty();
        if (!items || !items.length) {
            $cont.html(`<div class="text-center py-4 text-muted small">No resident classified ads found.</div>`);
            return;
        }

        // 1. Desktop Table
        let tableHtml = `
            <div class="d-none d-md-block table-responsive mb-4">
                <table class="table table-hover bg-white border rounded">
                    <thead class="thead-light">
                        <tr>
                            <th>Flat</th>
                            <th>Ad Title & Category</th>
                            <th>Price</th>
                            <th>Contact</th>
                            <th>Status</th>
                            <th>Remarks</th>
                            <th class="text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        // 2. Mobile Cards
        let cardsHtml = `<div class="d-md-none">`;

        items.forEach(c => {
            const isPending = c.approval_status === "Pending Approval";
            let borderClass = isPending ? "border-pending" : (c.approval_status === "Approved" ? "border-approved" : "border-rejected");

            tableHtml += `
                <tr class="${isPending ? 'table-warning-row' : ''}">
                    <td><span class="comm-flat-badge">${escapeHtml(c.resident)}</span></td>
                    <td>
                        <strong>${escapeHtml(c.title)}</strong>
                        <div><span class="badge badge-light border text-muted">${escapeHtml(c.category)}</span> <small class="text-muted">(${escapeHtml(c.listing_type)})</small></div>
                        <div class="small text-muted mt-1" style="max-width: 320px; white-space: normal;">${escapeHtml(c.description)}</div>
                    </td>
                    <td>${c.price ? `₹ ${c.price}` : '-'}</td>
                    <td class="small">
                        <div>${escapeHtml(c.contact_person || '-')}</div>
                        ${c.contact_phone ? `<div><a href="tel:${escapeHtml(c.contact_phone)}">${escapeHtml(c.contact_phone)}</a></div>` : ''}
                    </td>
                    <td>${getStatusBadge(c.approval_status)}</td>
                    <td class="small text-muted">${escapeHtml(c.committee_remarks || '-')}</td>
                    <td class="text-right">
                        ${isPending ? `
                            <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action" data-doctype="Resident Classified" data-docname="${c.name}" data-action="Approved" data-title="Approve Ad: ${escapeHtml(c.title)}" data-show-remarks="1">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-sm btn-danger py-1 px-2 btn-action" data-doctype="Resident Classified" data-docname="${c.name}" data-action="Rejected" data-title="Reject Ad: ${escapeHtml(c.title)}" data-show-remarks="1">
                                ❌ Reject
                            </button>
                        ` : `<span class="text-muted small">${escapeHtml(c.approval_status)}</span>`}
                    </td>
                </tr>
            `;

            cardsHtml += `
                <div class="card p-3 mb-3 comm-card-item ${borderClass}">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="comm-flat-badge mr-2">${escapeHtml(c.resident)}</span>
                            <strong class="text-dark">${escapeHtml(c.title)}</strong>
                        </div>
                        ${getStatusBadge(c.approval_status)}
                    </div>
                    <div class="small text-muted mb-2">
                        <span class="badge badge-light border">${escapeHtml(c.category)}</span>
                        ${c.price ? `<strong class="text-success ml-2">₹ ${c.price}</strong>` : ''}
                    </div>
                    <p class="small text-dark mb-2">${escapeHtml(c.description)}</p>
                    <div class="small text-muted mb-2">
                        📞 <strong>Contact:</strong> ${escapeHtml(c.contact_person || c.resident)} ${c.contact_phone ? `(${escapeHtml(c.contact_phone)})` : ''}
                    </div>
                    ${c.committee_remarks ? `<div class="small text-secondary mb-2 bg-light p-2 rounded">Committee Note: ${escapeHtml(c.committee_remarks)}</div>` : ''}
                    ${isPending ? `
                        <div class="d-flex pt-2 border-top">
                            <button type="button" class="btn btn-success btn-sm flex-grow-1 mr-2 font-weight-bold btn-action" data-doctype="Resident Classified" data-docname="${c.name}" data-action="Approved" data-title="Approve Ad: ${escapeHtml(c.title)}" data-show-remarks="1">
                                ✅ Approve
                            </button>
                            <button type="button" class="btn btn-danger btn-sm flex-grow-1 font-weight-bold btn-action" data-doctype="Resident Classified" data-docname="${c.name}" data-action="Rejected" data-title="Reject Ad: ${escapeHtml(c.title)}" data-show-remarks="1">
                                ❌ Reject
                            </button>
                        </div>
                    ` : ''}
                </div>
            `;
        });

        tableHtml += `</tbody></table></div>`;
        cardsHtml += `</div>`;
        $cont.html(tableHtml + cardsHtml);
    }

    function renderNotices(items) {
        const $cont = $("#container-notices").empty();
        if (!items || !items.length) {
            $cont.html(`
                <div class="text-center py-5 bg-white rounded border">
                    <div style="font-size: 2.2rem;">📢</div>
                    <h6 class="font-weight-bold mt-2">No Published Notices</h6>
                    <p class="text-muted small mb-3">Keep society members informed by posting announcements on the Resident Portal Notice Board.</p>
                    <button type="button" class="btn btn-primary btn-sm px-3" onclick="$('#btn-open-notice-modal').click()">
                        + Post First Notice
                    </button>
                </div>
            `);
            return;
        }

        let html = `<div class="row">`;
        items.forEach(n => {
            html += `
                <div class="col-md-6 mb-3">
                    <div class="card h-100 shadow-sm border ${n.is_active ? 'border-success' : 'border-secondary'}">
                        <div class="card-header bg-white d-flex justify-content-between align-items-center py-2">
                            <span class="badge ${n.is_active ? 'badge-success' : 'badge-secondary'}">
                                ${n.is_active ? 'Active' : 'Archived'}
                            </span>
                            <small class="text-muted">📅 ${formatDate(n.date)}</small>
                        </div>
                        <div class="card-body">
                            <h6 class="font-weight-bold text-dark mb-2">${escapeHtml(n.title)}</h6>
                            <p class="small text-muted mb-0" style="white-space: pre-line;">${escapeHtml(n.content)}</p>
                        </div>
                        <div class="card-footer bg-light d-flex justify-content-between align-items-center py-2">
                            <small class="text-muted">Posted: ${escapeHtml(n.posted_by || 'Committee')}</small>
                            <div>
                                <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-action" data-doctype="Society Notice" data-docname="${n.name}" data-action="toggle_active" data-title="${n.is_active ? 'Archive Notice' : 'Activate Notice'}">
                                    ${n.is_active ? 'Archive' : 'Activate'}
                                </button>
                                <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 ml-1 btn-action" data-doctype="Society Notice" data-docname="${n.name}" data-action="delete" data-title="Delete Notice">
                                    🗑️
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
        $cont.html(html);
    }

    // --- 8. Board Resolutions Module ---
    function renderResolutions(items) {
        const $cont = $("#container-resolutions").empty();
        if (!items || !items.length) {
            $cont.html(`
                <div class="text-center py-5 bg-white rounded border">
                    <div style="font-size: 2.2rem;">⚖️</div>
                    <h6 class="font-weight-bold mt-2">No Board Resolutions</h6>
                    <p class="text-muted small mb-3">No resolutions drafted or circulated for committee member signing yet.</p>
                    <button type="button" class="btn btn-primary btn-sm px-3" onclick="$('#btn-open-resolution-modal').click()">
                        + Draft New Resolution
                    </button>
                </div>
            `);
            return;
        }

        let html = `<div class="row">`;
        items.forEach(res => {
            const signatories = res.signatories || [];
            const total = signatories.length;
            const signedCount = signatories.filter(s => s.signature_status === "Signed").length;
            const declinedCount = signatories.filter(s => s.signature_status === "Declined").length;
            const pendingCount = signatories.filter(s => s.signature_status === "Pending").length;
            const percentSigned = total > 0 ? Math.round((signedCount / total) * 100) : 0;

            let statusBadge = `<span class="badge badge-warning text-dark font-weight-bold">⏳ Circulated</span>`;
            if (res.status === "Passed") {
                statusBadge = `<span class="badge badge-success font-weight-bold">✅ Passed</span>`;
            } else if (res.status === "Rejected") {
                statusBadge = `<span class="badge badge-danger font-weight-bold">❌ Rejected</span>`;
            } else if (res.status === "Draft") {
                statusBadge = `<span class="badge badge-secondary font-weight-bold">📝 Draft</span>`;
            }

            // User vote status in header
            let userActionHeaderHtml = "";
            if (res.user_status === "Signed") {
                userActionHeaderHtml = `<span class="badge badge-success px-2 py-1 mr-2"><i class="fa fa-check"></i> You Signed</span>`;
            } else if (res.user_status === "Declined") {
                userActionHeaderHtml = `<span class="badge badge-danger px-2 py-1 mr-2"><i class="fa fa-times"></i> You Declined</span>`;
            } else if (res.user_status === "Pending") {
                userActionHeaderHtml = `<span class="badge badge-warning text-dark px-2 py-1 mr-2">⏳ Your Vote Pending</span>`;
            } else {
                userActionHeaderHtml = `<span class="badge badge-light border text-muted mr-2">Observer</span>`;
            }

            // Publish to Notice Board Button (Enabled only for Passed resolutions, if user is the Author/Admin, and not yet published)
            let publishBtnHtml = "";
            if (res.status === "Passed") {
                if (res.is_published_to_notice_board) {
                    publishBtnHtml = `
                        <span class="badge badge-info px-2 py-1 ml-1" title="Published Notice ID: ${res.published_notice || ''}">
                            📢 Published to Notice Board
                        </span>
                    `;
                } else if (res.is_author) {
                    publishBtnHtml = `
                        <button type="button" class="btn btn-success btn-sm font-weight-bold btn-publish-resolution ml-1 shadow-sm" data-docname="${res.name}" data-title="${escapeHtml(res.resolution_title)}">
                            📢 Publish to Notice Board
                        </button>
                    `;
                } else {
                    publishBtnHtml = `
                        <span class="badge badge-light border text-muted ml-1" title="Awaiting publishing by the author">
                            Pending Author Publication
                        </span>
                    `;
                }
            }

            // Vote / Sign Button Below the Record
            let voteButtonBelowHtml = "";
            if (res.user_status === "Pending") {
                voteButtonBelowHtml = `
                    <div class="card-footer bg-white border-top d-flex justify-content-between align-items-center py-3 flex-wrap">
                        <div class="small text-muted mb-2 mb-md-0">
                            ℹ️ Review resolution text and signatories status before recording your response.
                        </div>
                        <button type="button" class="btn btn-primary font-weight-bold shadow-sm btn-vote-open px-4" data-docname="${res.name}">
                            🗳️ Vote / Sign Resolution Now
                        </button>
                    </div>
                `;
            } else if (res.user_status === "Signed") {
                voteButtonBelowHtml = `
                    <div class="card-footer bg-light border-top py-2 px-3 small text-success font-weight-bold d-flex align-items-center">
                        <span class="mr-2">✅</span> You have signed this resolution.
                    </div>
                `;
            } else if (res.user_status === "Declined") {
                voteButtonBelowHtml = `
                    <div class="card-footer bg-light border-top py-2 px-3 small text-danger font-weight-bold d-flex align-items-center">
                        <span class="mr-2">❌</span> You declined this resolution.
                    </div>
                `;
            }

            // Signatory breakdown tags
            let signatoriesListHtml = `<div class="d-flex flex-wrap gap-1 mt-2">`;
            signatories.forEach(s => {
                let badgeClass = "badge-light border text-muted";
                let icon = "⏳";
                if (s.signature_status === "Signed") {
                    badgeClass = "badge-success";
                    icon = "✅";
                } else if (s.signature_status === "Declined") {
                    badgeClass = "badge-danger";
                    icon = "❌";
                }
                const reasonTip = s.rejection_reason ? ` title="Declined: ${escapeHtml(s.rejection_reason)}"` : "";
                signatoriesListHtml += `
                    <span class="badge ${badgeClass} mr-1 mb-1 font-weight-normal px-2 py-1" ${reasonTip}>
                        ${icon} <strong>${escapeHtml(s.signatory_name || s.signatory)}</strong> (${escapeHtml(s.designation_name || s.role || 'Member')})
                    </span>
                `;
            });
            signatoriesListHtml += `</div>`;

            html += `
                <div class="col-12 mb-4">
                    <div class="card shadow-sm border ${res.status === 'Passed' ? 'border-success' : (res.status === 'Rejected' ? 'border-danger' : '')}">
                        <div class="card-header bg-white py-3 d-flex justify-content-between align-items-center flex-wrap">
                            <div>
                                <span class="badge badge-dark px-2 py-1 mr-2">${escapeHtml(res.name)}</span>
                                ${statusBadge}
                                <span class="text-muted small ml-2">📅 ${formatDate(res.creation)}</span>
                            </div>
                            <div class="mt-2 mt-md-0 d-flex align-items-center">
                                ${userActionHeaderHtml}
                                ${publishBtnHtml}
                            </div>
                        </div>
                        <div class="card-body">
                            <h5 class="font-weight-bold text-dark mb-2">${escapeHtml(res.resolution_title)}</h5>
                            <div class="bg-light p-3 rounded mb-3 text-dark small border" style="max-height: 250px; overflow-y: auto;">
                                ${res.resolution_text}
                            </div>

                            <!-- Progress & Tally -->
                            <div class="mb-3">
                                <div class="d-flex justify-content-between small font-weight-bold mb-1">
                                    <span>Committee Votes: ${signedCount} Signed &bull; ${declinedCount} Declined &bull; ${pendingCount} Pending</span>
                                    <span class="${percentSigned >= 51 ? 'text-success' : 'text-muted'}">${percentSigned}% Signed (51% needed to Pass)</span>
                                </div>
                                <div class="progress" style="height: 10px;">
                                    <div class="progress-bar bg-success" role="progressbar" style="width: ${percentSigned}%;" aria-valuenow="${percentSigned}" aria-valuemin="0" aria-valuemax="100"></div>
                                </div>
                            </div>

                            <!-- Signatories Breakdown -->
                            <div>
                                <label class="small font-weight-bold text-muted mb-1">Signatories Roster:</label>
                                ${signatoriesListHtml}
                            </div>
                        </div>
                        ${voteButtonBelowHtml}
                    </div>
                </div>
            `;
        });
        html += `</div>`;
        $cont.html(html);
    }

    // --- 9. Emergency SOS & Contacts Settings Module ---
    function renderEmergency(items) {
        const $cont = $("#container-emergency").empty();

        let html = `
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap">
                <div>
                    <h6 class="font-weight-bold text-dark mb-0">📞 Emergency & Duty Contact Directory (${(items || []).length} Contacts)</h6>
                    <small class="text-muted">Manage 24x7 gate security, facility staff, electricians, and public emergency numbers.</small>
                </div>
                <div class="mt-2 mt-md-0">
                    <button type="button" class="btn btn-primary btn-sm px-3 shadow-sm font-weight-bold" id="btn-add-emergency-contact">
                        ➕ Add Emergency Contact
                    </button>
                </div>
            </div>
        `;

        if (!items || !items.length) {
            html += `
                <div class="text-center py-5 bg-white rounded border">
                    <div style="font-size: 2.2rem;">📞</div>
                    <h6 class="font-weight-bold mt-2">No Contacts Configured</h6>
                    <p class="text-muted small mb-3">Add contacts like Main Gate Security, Estate Manager, Fire, or Police.</p>
                </div>
            `;
            $cont.html(html);
            return;
        }

        html += `<div class="row">`;
        items.forEach(c => {
            const isContactActive = c.enabled;
            html += `
                <div class="col-12 col-md-6 col-lg-4 mb-3">
                    <div class="card h-100 shadow-sm border p-3 d-flex flex-column justify-content-between" style="border-left: 4px solid ${isContactActive ? '#0d6efd' : '#adb5bd'} !important;">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span style="font-size: 1.8rem;">${escapeHtml(c.icon || '📞')}</span>
                                <div>
                                    <span class="badge ${isContactActive ? 'badge-success' : 'badge-secondary'} mr-1">${isContactActive ? 'Active' : 'Inactive'}</span>
                                    <span class="badge badge-light border text-muted">${escapeHtml(c.operating_hours || '24x7')}</span>
                                </div>
                            </div>
                            <h6 class="font-weight-bold text-dark mb-1">${escapeHtml(c.title)}</h6>
                            <span class="badge badge-info bg-info text-white mb-2" style="font-size: 0.72rem;">${escapeHtml(c.category)}</span>
                            <p class="small text-muted mb-2">${escapeHtml(c.description || 'No description provided')}</p>
                        </div>
                        <div class="pt-2 border-top d-flex justify-content-between align-items-center">
                            <span class="font-weight-bold text-dark small">📞 ${escapeHtml(c.phone)}</span>
                            <div>
                                <button type="button" class="btn btn-outline-secondary btn-sm px-2 btn-edit-emergency"
                                    data-name="${escapeHtml(c.name)}"
                                    data-title="${escapeHtml(c.title)}"
                                    data-category="${escapeHtml(c.category)}"
                                    data-phone="${escapeHtml(c.phone)}"
                                    data-hours="${escapeHtml(c.operating_hours || '')}"
                                    data-icon="${escapeHtml(c.icon || '')}"
                                    data-desc="${escapeHtml(c.description || '')}"
                                    data-enabled="${c.enabled ? 1 : 0}">
                                    ✏️ Edit
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        html += `</div>`;
        $cont.html(html);
    }

    // --- 10. Facility & Security Staff Deployment Module ---
    function renderFacilityStaff(items) {
        const $cont = $("#container-facility_staff");
        if (!items || !items.length) {
            $cont.html(`
                <div class="text-center py-5 bg-white rounded border">
                    <div style="font-size: 2.5rem;">🛡️</div>
                    <h6 class="font-weight-bold mt-2">No Facility Staff Records Found</h6>
                    <p class="text-muted small">No active security guards or housekeeping staff registered for today.</p>
                </div>
            `);
            return;
        }

        // Shift Muster Gallery Section (if any muster photos recorded today)
        const musters = committeeData.facility_musters || [];
        let musterGalleryHtml = '';
        if (musters.length > 0) {
            musterGalleryHtml = `
                <div class="card mb-3 border-0 bg-white shadow-sm p-3">
                    <h6 class="font-weight-bold text-dark mb-2">📸 Today's Shift Lineup & Muster Photos</h6>
                    <div class="row">
            `;
            musters.forEach(m => {
                musterGalleryHtml += `
                    <div class="col-12 col-md-4 col-lg-3 mb-2">
                        <div class="border rounded p-2 bg-light text-center">
                            <a href="${m.muster_photo}" target="_blank">
                                <img src="${m.muster_photo}" class="img-fluid rounded mb-2" style="max-height: 120px; object-fit: cover;" alt="Shift Lineup">
                            </a>
                            <div class="font-weight-bold small text-dark">${escapeHtml(m.shift)}</div>
                            <div class="small text-muted">${escapeHtml(m.category)} &bull; Count: <strong>${m.reported_count || 0}</strong></div>
                            ${m.briefing_notes ? `<div class="small text-muted font-italic mt-1 text-truncate">${escapeHtml(m.briefing_notes)}</div>` : ''}
                        </div>
                    </div>
                `;
            });
            musterGalleryHtml += `</div></div>`;
        }

        let html = `
            ${musterGalleryHtml}
            <div class="card mb-3 border-0 bg-light p-3">
                <div class="d-flex justify-content-between align-items-center flex-wrap">
                    <div>
                        <h6 class="font-weight-bold text-dark mb-1">🛡️ Today's Security & Facility Deployment</h6>
                        <small class="text-muted">Real-time gate check-ins and agency personnel compliance</small>
                    </div>
                    <div class="mt-2 mt-md-0 d-flex align-items-center">
                        ${items.filter(s => s.approval_status === "Pending").length > 0 ? `
                            <span class="badge badge-warning text-dark px-2 py-1 mr-2 font-weight-bold">
                                ⏳ ${items.filter(s => s.approval_status === "Pending").length} Pending Approval
                            </span>
                        ` : ''}
                        <span class="badge badge-success px-2 py-1 mr-1">
                            ${items.filter(s => s.is_on_duty).length} On Duty
                        </span>
                        <span class="badge badge-secondary px-2 py-1">
                            ${items.length} Total Registered
                        </span>
                    </div>
                </div>
            </div>
            <div class="row">
        `;

        items.forEach(st => {
            const isPendingApproval = st.approval_status === "Pending";
            const isOnDuty = st.is_on_duty;
            const borderCol = isPendingApproval ? '#ffc107' : (isOnDuty ? '#28a745' : '#6c757d');
            const badgeCol = isPendingApproval ? 'badge-warning text-dark' : (isOnDuty ? 'badge-success' : 'badge-secondary');
            const statusTxt = isPendingApproval ? '⏳ Awaiting Approval' : (isOnDuty ? '🟢 On Duty' : (st.in_time ? '🔴 Checked Out' : '⚪ Not Clocked In'));

            html += `
                <div class="col-12 col-md-6 col-lg-4 mb-3">
                    <div class="card h-100 shadow-sm border p-3 d-flex flex-column justify-content-between" style="border-left: 4px solid ${borderCol} !important;">
                        <div>
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <span class="badge ${badgeCol} font-weight-bold">${statusTxt}</span>
                                <span class="badge badge-light border text-muted">${escapeHtml(st.gate || st.gate_assigned || 'All Gates')}</span>
                            </div>
                            <h6 class="font-weight-bold text-dark mb-1">${escapeHtml(st.full_name)}</h6>
                            <div class="small text-muted mb-2">
                                <span class="badge badge-info bg-info text-white mr-1">${escapeHtml(st.role)}</span>
                                <span class="text-muted">(${escapeHtml(st.agency)})</span>
                            </div>
                            <div class="small text-muted mb-2">
                                📞 Contact: <strong>${escapeHtml(st.contact_number || 'N/A')}</strong><br>
                                🪪 Police Verification: <span class="badge ${st.police_status === 'Verified' ? 'badge-success' : 'badge-warning'}">${escapeHtml(st.police_status || 'Pending')}</span>
                            </div>
                            ${st.duty_post ? `
                                <div class="mb-2">
                                    <span class="badge badge-primary px-2 py-1">📍 Post: ${escapeHtml(st.duty_post)}</span>
                                    ${st.cost_center ? `<div class="small text-muted font-family-monospace mt-1">💼 CC: ${escapeHtml(st.cost_center)}</div>` : ''}
                                </div>
                            ` : ''}
                            ${st.in_time ? `
                                <div class="bg-light p-2 rounded small text-muted mb-2">
                                    ⏱️ Punch In: <strong>${escapeHtml(st.in_time.substring(11, 16))}</strong>
                                    ${st.out_time ? ` &bull; Out: <strong>${escapeHtml(st.out_time.substring(11, 16))}</strong>` : ' <em>(Active Shift)</em>'}
                                </div>
                            ` : ''}
                        </div>
                        <div class="pt-2 border-top d-flex justify-content-between align-items-center">
                            <span class="small text-muted">ID: <code>${escapeHtml(st.staff_id)}</code></span>
                            <div>
                                ${isPendingApproval ? `
                                    <button type="button" class="btn btn-sm btn-success py-1 px-2 btn-action mr-1" data-doctype="Facility Staff" data-docname="${st.staff_id}" data-action="Approved" data-title="Approve Staff Member ${escapeHtml(st.full_name)}">
                                        ✅ Approve
                                    </button>
                                    <button type="button" class="btn btn-sm btn-outline-danger py-1 px-2 btn-action" data-doctype="Facility Staff" data-docname="${st.staff_id}" data-action="Rejected" data-title="Reject Staff Member ${escapeHtml(st.full_name)}" data-show-remarks="1">
                                        ❌ Reject
                                    </button>
                                ` : `
                                    <span class="badge ${isOnDuty ? 'badge-success' : 'badge-light border'} py-1 px-2">
                                        ${isOnDuty ? '🟢 On Duty' : '⚪ Off Duty'}
                                    </span>
                                `}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += `</div>`;
        $cont.html(html);
    }

    // --- Search & Filter Logic ---
    function applyFilterAndRender() {
        const query = $searchInput.val().trim().toLowerCase();
        const pendingOnly = $switchPending.is(":checked");

        function filterList(list, module, searchFields) {
            return (list || []).filter(item => {
                if (pendingOnly && !isPending(item, module)) {
                    return false;
                }
                if (!query) return true;
                return searchFields.some(f => {
                    const val = (item[f] || "").toString().toLowerCase();
                    return val.includes(query);
                });
            });
        }

        renderTenants(filterList(committeeData.tenants, "tenants", ["flat", "tenant_name", "mobile_no", "email"]));
        renderVehicles(filterList(committeeData.vehicles, "vehicles", ["flat", "registration_number", "registered_owner_name", "make", "model"]));
        renderWorkPermits(filterList(committeeData.work_permits, "work_permits", ["flat_number", "contractor_name", "work_type", "name"]));
        renderFamily(filterList(committeeData.family, "family", ["parent_flat", "member_name", "mobile_no", "relationship"]));
        renderPets(filterList(committeeData.pets, "pets", ["flat", "parent", "pet_name", "license_no"]));
        renderTickets(filterList(committeeData.tickets, "tickets", ["name", "resident", "category", "description", "priority_level"]));
        renderFacilityBookings(filterList(committeeData.facility_bookings, "facility_bookings", ["facility", "resident", "name", "remarks"]));
        renderClassifieds(filterList(committeeData.classifieds, "classifieds", ["title", "category", "listing_type", "resident", "description"]));
        renderNotices(filterList(committeeData.notices, "notices", ["title", "content"]));
        
        // Filter resolutions with dedicated filter options (All, Pending My Vote, Signed by Me, Declined by Me, Passed, Rejected)
        const resFilterVal = $selectResolutionFilter.val() || "all";
        const filteredResolutions = (committeeData.resolutions || []).filter(item => {
            if (resFilterVal === "pending_vote" && !(item.user_status === "Pending" && (item.status === "Circulated" || item.status === "Draft"))) {
                return false;
            }
            if (resFilterVal === "my_signed" && item.user_status !== "Signed") {
                return false;
            }
            if (resFilterVal === "my_declined" && item.user_status !== "Declined") {
                return false;
            }
            if (resFilterVal === "passed" && item.status !== "Passed") {
                return false;
            }
            if (resFilterVal === "rejected" && item.status !== "Rejected") {
                return false;
            }
            if (!query) return true;
            return ["name", "resolution_title", "resolution_text", "status"].some(f => {
                const val = (item[f] || "").toString().toLowerCase();
                return val.includes(query);
            });
        });
        renderResolutions(filteredResolutions);
        renderEmergency(committeeData.emergency_contacts || []);
        renderFacilityStaff(filterList(committeeData.facility_staff, "facility_staff", ["full_name", "agency", "role", "gate_assigned", "contact_number"]));
    }

    // --- Data Fetching ---
    function loadCommitteeData() {
        $loading.removeClass("d-none");
        $panes.addClass("d-none");

        frappe.call({
            method: "society_erp.www.resident.committee.index.get_committee_data",
            args: { module_type: "all" },
            callback: function (r) {
                $loading.addClass("d-none");
                $panes.removeClass("d-none");

                if (r && r.message) {
                    committeeData = r.message;
                    if (committeeData.counts) {
                        updateBadgeCounts(committeeData.counts);
                    }
                    applyFilterAndRender();

                    // Support deep linking via URL hash (e.g. /resident/committee#tenants) or query param
                    const hashTab = (window.location.hash || "").replace("#pane-", "").replace("#tab-", "").replace("#", "").trim();
                    const urlParams = new URLSearchParams(window.location.search);
                    const paramTab = urlParams.get("tab") || hashTab;

                    if (paramTab) {
                        const $targetTab = $(`#tab-${paramTab}`);
                        if ($targetTab.length) {
                            $targetTab.tab("show");
                        }
                        // Also ensure the target pane is shown
                        $(`#pane-${paramTab}`).addClass("show active").siblings().removeClass("show active");
                        if (paramTab === "resolutions") {
                            $filterResGroup.removeClass("d-none");
                            $filterPendingSwitchGroup.addClass("d-none");
                        } else {
                            $filterResGroup.addClass("d-none");
                            $filterPendingSwitchGroup.removeClass("d-none");
                        }
                    } else if (!$("#committeeTabs .nav-link.active").is(":visible")) {
                        const $firstVisible = $("#committeeTabs .nav-link:visible").first();
                        if ($firstVisible.length) {
                            $firstVisible.tab("show");
                        }
                    }
                }
            },
            error: function () {
                $loading.html(`
                    <div class="text-danger small py-4">
                        Failed to load committee records. Please refresh the page or ensure you have committee authorization.
                    </div>
                `);
            }
        });
    }

    // Trigger initial load
    loadCommitteeData();

    // Event listeners for filters
    let searchTimer = null;
    $searchInput.on("input", function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(applyFilterAndRender, 200);
    });

    $switchPending.on("change", applyFilterAndRender);
    $selectResolutionFilter.on("change", applyFilterAndRender);
    $("#btn-refresh-data").on("click", loadCommitteeData);

    // Dynamic Filter switcher when switching tabs
    $('a[data-toggle="pill"]').on("shown.bs.tab", function (e) {
        const targetTab = $(e.target).data("module");
        if (targetTab === "resolutions") {
            $filterResGroup.removeClass("d-none");
            $filterPendingSwitchGroup.addClass("d-none");
        } else {
            $filterResGroup.addClass("d-none");
            $filterPendingSwitchGroup.removeClass("d-none");
        }
    });

    // --- Action Confirm Modal Handler ---
    $(document).on("click", ".btn-action", function (e) {
        e.preventDefault();
        const $btn = $(this);
        const doctype = $btn.data("doctype");
        const docname = $btn.data("docname");
        const action = $btn.data("action");
        const title = $btn.data("title") || `${action} ${doctype}`;
        const showRemarks = $btn.data("show-remarks") || (action === "Rejected" || doctype === "Maintenance Ticket");

        pendingActionData = { doctype, docname, action };

        $actionTitle.text(title);
        $actionSummary.html(`Are you sure you want to set <strong>${doctype} ${escapeHtml(docname)}</strong> to <strong>${action}</strong>?`);
        $actionRemarks.val("");

        if (showRemarks) {
            $("#modal-remarks-group").removeClass("d-none");
        } else {
            $("#modal-remarks-group").addClass("d-none");
        }

        $actionModal.modal("show");
    });

    $btnConfirmAction.on("click", function () {
        if (!pendingActionData) return;

        const remarks = $actionRemarks.val().trim();
        const { doctype, docname, action } = pendingActionData;
        const origBtnText = $btnConfirmAction.html();

        $btnConfirmAction.prop("disabled", true).html("Processing…");

        frappe.call({
            method: "society_erp.www.resident.committee.index.update_item_status",
            args: {
                doctype: doctype,
                docname: docname,
                action: action,
                remarks: remarks
            },
            callback: function (r) {
                $btnConfirmAction.prop("disabled", false).html(origBtnText);
                $actionModal.modal("hide");
                if (r && r.message && r.message.status === "success") {
                    showAlert(r.message.message || "Record updated successfully.", "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                $btnConfirmAction.prop("disabled", false).html(origBtnText);
                const errMsg = err && err.message ? err.message : "Failed to update record.";
                showAlert(errMsg, "danger");
            }
        });
    });

    // --- Notice Posting Handler ---
    $("#btn-open-notice-modal").on("click", function () {
        $("#notice-title").val("");
        $("#notice-content").val("");
        $("#notice-is-active").prop("checked", true);
        $noticeModal.modal("show");
    });

    $btnSubmitNotice.on("click", function () {
        const title = $("#notice-title").val().trim();
        const content = $("#notice-content").val().trim();
        const isActive = $("#notice-is-active").is(":checked") ? 1 : 0;

        if (!title || !content) {
            frappe.msgprint({
                title: __("Missing Information"),
                message: __("Please provide both title and announcement details for the notice."),
                indicator: "orange"
            });
            return;
        }

        const origBtnText = $btnSubmitNotice.html();
        $btnSubmitNotice.prop("disabled", true).html("Publishing…");

        frappe.call({
            method: "society_erp.www.resident.committee.index.post_society_notice",
            args: {
                title: title,
                content: content,
                is_active: isActive
            },
            callback: function (r) {
                $btnSubmitNotice.prop("disabled", false).html(origBtnText);
                $noticeModal.modal("hide");
                if (r && r.message && r.message.status === "success") {
                    showAlert(r.message.message || "Notice published successfully!", "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                $btnSubmitNotice.prop("disabled", false).html(origBtnText);
                const errMsg = err && err.message ? err.message : "Failed to publish notice.";
                frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
            }
        });
    });

    // --- Board Resolution Creation & Voting Handlers ---
    const $resModal = $("#modal-post-resolution");
    const $voteModal = $("#modal-resolution-vote");
    let activeVoteDocname = null;
    let selectedVoteAction = "Signed";

    $("#btn-open-resolution-modal").on("click", function () {
        $("#res-title").val("");
        $("#res-text").val("");
        $resModal.modal("show");
    });

    $("#btn-submit-resolution").on("click", function () {
        const title = $("#res-title").val().trim();
        const text = $("#res-text").val().trim();

        if (!title || !text) {
            frappe.msgprint({
                title: __("Missing Information"),
                message: __("Please provide both resolution title and motion text."),
                indicator: "orange"
            });
            return;
        }

        const $btn = $(this);
        const origText = $btn.html();
        $btn.prop("disabled", true).html("Circulating…");

        frappe.call({
            method: "society_erp.www.resident.committee.index.create_board_resolution",
            args: {
                title: title,
                text: text
            },
            callback: function (r) {
                $btn.prop("disabled", false).html(origText);
                $resModal.modal("hide");
                if (r && r.message && r.message.status === "success") {
                    showAlert(r.message.message || "Board Resolution created and circulated!", "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                $btn.prop("disabled", false).html(origText);
                const errMsg = err && err.message ? err.message : "Failed to create resolution.";
                frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
            }
        });
    });

    // Open Vote Modal
    $(document).on("click", ".btn-vote-open", function () {
        activeVoteDocname = $(this).data("docname");
        
        // Find the full resolution object from committeeData
        const res = (committeeData.resolutions || []).find(r => r.name === activeVoteDocname);
        if (!res) return;

        $("#vote-res-title").text(res.resolution_title || "Board Resolution");
        $("#vote-res-id").text(`Resolution ID: ${res.name}`);
        $("#vote-res-date").text(formatDate(res.creation));
        $("#vote-res-content").html(res.resolution_text || "<p class='text-muted'>No text provided.</p>");
        
        // Reset decline box state
        $("#vote-action-buttons-group").removeClass("d-none");
        $("#inline-decline-box").addClass("d-none");
        $("#inline-decline-reason").val("");

        // Populate Signatories Breakdown in the modal
        const signatories = res.signatories || [];
        const signedList = signatories.filter(s => s.signature_status === "Signed");
        const otherList = signatories.filter(s => s.signature_status !== "Signed");

        $("#vote-res-tally").text(`${signedList.length} of ${signatories.length} Members Signed`);

        const $signedContainer = $("#vote-res-signed-members").empty();
        if (signedList.length > 0) {
            signedList.forEach(s => {
                $signedContainer.append(`
                    <span class="badge badge-success mr-1 mb-1 px-2 py-1 font-weight-normal" title="Signed on: ${formatDate(s.signed_on)}">
                        ✅ <strong>${escapeHtml(s.signatory_name || s.signatory)}</strong> (${escapeHtml(s.designation_name || s.role || 'Member')})
                    </span>
                `);
            });
        } else {
            $signedContainer.html(`<span class="small text-muted font-italic">No committee members have signed yet.</span>`);
        }

        const $otherContainer = $("#vote-res-other-members").empty();
        if (otherList.length > 0) {
            otherList.forEach(s => {
                const isDeclined = s.signature_status === "Declined";
                const badgeClass = isDeclined ? "badge-danger" : "badge-light border text-muted";
                const icon = isDeclined ? "❌" : "⏳";
                const note = s.rejection_reason ? ` - "${escapeHtml(s.rejection_reason)}"` : "";
                $otherContainer.append(`
                    <span class="badge ${badgeClass} mr-1 mb-1 px-2 py-1 font-weight-normal" title="${s.signature_status}">
                        ${icon} ${escapeHtml(s.signatory_name || s.signatory)} (${escapeHtml(s.designation_name || s.role || 'Member')})${note}
                    </span>
                `);
            });
        } else {
            $otherContainer.html(`<span class="small text-muted font-italic">All signatories have responded!</span>`);
        }

        $voteModal.modal("show");
    });

    // Helper: Execute voting call
    function executeResolutionVote(action, reason, $triggerBtn) {
        if (!activeVoteDocname) return;

        const origBtnText = $triggerBtn ? $triggerBtn.html() : "";
        if ($triggerBtn) {
            $triggerBtn.prop("disabled", true).html("Recording…");
        }

        frappe.call({
            method: "society_erp.www.resident.committee.index.respond_board_resolution",
            args: {
                docname: activeVoteDocname,
                action: action,
                rejection_reason: reason || null
            },
            callback: function (r) {
                if ($triggerBtn) $triggerBtn.prop("disabled", false).html(origBtnText);
                $voteModal.modal("hide");
                if (r && r.message && r.message.status === "success") {
                    showAlert(r.message.message || "Your response has been recorded.", "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                if ($triggerBtn) $triggerBtn.prop("disabled", false).html(origBtnText);
                const errMsg = err && err.message ? err.message : "Failed to record response.";
                frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
            }
        });
    }

    // Direct Action 1: Sign with Confirmation Dialog
    $("#btn-modal-direct-sign").on("click", function () {
        if (!activeVoteDocname) return;
        const $btn = $(this);
        const resTitle = $("#vote-res-title").text();

        frappe.confirm(
            `Are you sure you want to sign and accept resolution <strong>${escapeHtml(resTitle)} (${escapeHtml(activeVoteDocname)})</strong>?`,
            function () {
                executeResolutionVote("Signed", null, $btn);
            }
        );
    });

    // Direct Action 2: Decline Toggle Inline Box
    $("#btn-modal-direct-decline").on("click", function () {
        $("#vote-action-buttons-group").addClass("d-none");
        $("#inline-decline-box").removeClass("d-none");
        $("#inline-decline-reason").val("").focus();
    });

    $("#btn-cancel-inline-decline").on("click", function () {
        $("#inline-decline-box").addClass("d-none");
        $("#vote-action-buttons-group").removeClass("d-none");
        $("#inline-decline-reason").val("");
    });

    $("#btn-confirm-inline-decline").on("click", function () {
        if (!activeVoteDocname) return;
        const reason = $("#inline-decline-reason").val().trim();
        if (!reason) {
            frappe.msgprint({
                title: __("Reason Required"),
                message: __("Please specify why you are declining this resolution."),
                indicator: "orange"
            });
            $("#inline-decline-reason").focus();
            return;
        }
        executeResolutionVote("Declined", reason, $(this));
    });

    // Publish Passed Resolution to Notice Board Handler
    $(document).on("click", ".btn-publish-resolution", function () {
        const docname = $(this).data("docname");
        const title = $(this).data("title");
        const $btn = $(this);

        frappe.confirm(
            `Are you sure you want to publish the Passed Board Resolution <strong>${escapeHtml(title)} (${escapeHtml(docname)})</strong> to the Society Notice Board for all residents to see?`,
            function () {
                const origText = $btn.html();
                $btn.prop("disabled", true).html("Publishing…");

                frappe.call({
                    method: "society_erp.www.resident.committee.index.publish_resolution_to_notice_board",
                    args: { docname: docname },
                    callback: function (r) {
                        $btn.prop("disabled", false).html(origText);
                        if (r && r.message && r.message.status === "success") {
                            showAlert(r.message.message, "success");
                            loadCommitteeData();
                        }
                    },
                    error: function (err) {
                        $btn.prop("disabled", false).html(origText);
                        const errMsg = err && err.message ? err.message : "Failed to publish resolution to Notice Board.";
                        frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
                    }
                });
            }
        );
    });

    // --- DPDP Act Unmasking & Audit Handler ---
    $(document).on("click", ".btn-reveal-contact", function () {
        const $btn = $(this);
        const doctype = $btn.data("doctype");
        const docname = $btn.data("docname");
        const $box = $btn.closest(".contact-box");

        frappe.confirm(
            `In accordance with DPDP Act & Society Privacy Policy, viewing unmasked contact details is audited.<br><br>Do you wish to log access and reveal contact details for <strong>${escapeHtml(docname)}</strong>?`,
            function () {
                const origText = $btn.text();
                $btn.prop("disabled", true).text("Unmasking…");

                frappe.call({
                    method: "society_erp.www.resident.committee.index.reveal_contact_details",
                    args: { doctype: doctype, docname: docname },
                    callback: function (r) {
                        $btn.prop("disabled", false);
                        if (r && r.message && r.message.status === "success") {
                            const res = r.message;
                            if (res.mobile_no) {
                                $box.find(".contact-phone").text(res.mobile_no);
                            }
                            if (res.email) {
                                $box.find(".contact-email").text(res.email);
                            }
                            $btn.replaceWith(`
                                <span class="badge badge-warning text-dark font-weight-normal py-0 px-1" title="Access logged in Committee Access Log" style="font-size: 0.68rem;">
                                    🔓 Unmasked (Logged)
                                </span>
                            `);
                            frappe.show_alert({ message: __("Contact details revealed & logged."), indicator: "green" }, 4);
                        }
                    },
                    error: function (err) {
                        $btn.prop("disabled", false).text(origText);
                        const errMsg = err && err.message ? err.message : "Failed to unmask contact.";
                        frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
                    }
                });
            }
        );
    });

    // --- Emergency SOS Management Handlers ---
    $(document).on("click", "#btn-add-emergency-contact", function () {
        $("#form-emergency-contact")[0].reset();
        $("#emergency-contact-name").val("");
        $("#modalEmergencyTitle").text("➕ Add Emergency / SOS Contact");
        $("#emergency-icon").val("📞");
        $("#emergency-hours").val("24x7");
        $("#emergency-enabled").prop("checked", true);
        $("#modal-emergency-contact").modal("show");
    });

    $(document).on("click", ".btn-edit-emergency", function () {
        const $b = $(this);
        $("#form-emergency-contact")[0].reset();
        $("#emergency-contact-name").val($b.data("name"));
        $("#emergency-title").val($b.data("title"));
        $("#emergency-category").val($b.data("category"));
        $("#emergency-phone").val($b.data("phone"));
        $("#emergency-hours").val($b.data("hours") || "24x7");
        $("#emergency-icon").val($b.data("icon") || "📞");
        $("#emergency-description").val($b.data("desc") || "");
        $("#emergency-enabled").prop("checked", $b.data("enabled") == 1);
        $("#modalEmergencyTitle").text("✏️ Edit Emergency Contact");
        $("#modal-emergency-contact").modal("show");
    });

    $(document).on("submit", "#form-emergency-contact", function (e) {
        e.preventDefault();
        const $btn = $("#btn-save-emergency");
        $btn.prop("disabled", true).text("Saving…");

        frappe.call({
            method: "society_erp.www.resident.committee.index.save_emergency_contact",
            args: {
                contact_name: $("#emergency-contact-name").val(),
                title: $("#emergency-title").val(),
                category: $("#emergency-category").val(),
                phone: $("#emergency-phone").val(),
                operating_hours: $("#emergency-hours").val(),
                icon: $("#emergency-icon").val(),
                description: $("#emergency-description").val(),
                enabled: $("#emergency-enabled").is(":checked") ? 1 : 0
            },
            callback: function (r) {
                $btn.prop("disabled", false).text("Save Contact");
                if (r && r.message && r.message.status === "success") {
                    $("#modal-emergency-contact").modal("hide");
                    showAlert(r.message.message, "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                $btn.prop("disabled", false).text("Save Contact");
                const errMsg = err && err.message ? err.message : "Failed to save contact.";
                frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
            }
        });
    });

    // --- Facility Staff Punch Button Handler ---
    $(document).on("click", ".btn-punch-staff", function () {
        const $b = $(this);
        const staffId = $b.data("staff-id");
        const action = $b.data("action");
        const origText = $b.text();

        $b.prop("disabled", true).text("Recording…");

        frappe.call({
            method: "society_erp.api.facility_staff.punch_attendance",
            args: {
                staff_id: staffId,
                punch_type: action,
                method: "Supervisor Punch"
            },
            callback: function (r) {
                $b.prop("disabled", false).text(origText);
                if (r && r.message && r.message.status === "success") {
                    showAlert(r.message.message, "success");
                    loadCommitteeData();
                }
            },
            error: function (err) {
                $b.prop("disabled", false).text(origText);
                const errMsg = err && err.message ? err.message : "Punch failed.";
                frappe.msgprint({ title: __("Error"), message: errMsg, indicator: "red" });
            }
        });
    });
});
