/**
 * Committee Member Portal Client Script
 * Handles real-time search, responsive card & table rendering, approval/rejection actions, and notice posting.
 */
frappe.ready(function () {
    const $loading = $("#committee-loading");
    const $panes = $("#committeeTabPanes");
    const $searchInput = $("#committee-search-input");
    const $switchPending = $("#switch-pending-only");
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
        return val.split(" ")[0];
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
        return false;
    }

    function updateBadgeCounts(counts) {
        $("#badge-tenants").text(counts.tenants_pending || 0);
        $("#badge-vehicles").text(counts.vehicles_pending || 0);
        $("#badge-permits").text(counts.permits_pending || 0);
        $("#badge-family").text(counts.family_pending || 0);
        $("#badge-pets").text(counts.pets_pending || 0);
        $("#badge-tickets").text(counts.tickets_open || 0);
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
                        <div>📞 ${escapeHtml(t.mobile_no || '-')}</div>
                        <div>✉️ ${escapeHtml(t.email || '-')}</div>
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
                    <div class="small text-muted mb-2">
                        <div>📞 ${escapeHtml(t.mobile_no || '-')} &bull; ✉️ ${escapeHtml(t.email || '-')}</div>
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
                    <td class="small">📞 ${escapeHtml(f.mobile_no || '-')}</td>
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
                    <div class="small text-muted mb-2">
                        <div>👥 Relationship: <strong>${escapeHtml(f.relationship || 'Family')}</strong> &bull; 📞 ${escapeHtml(f.mobile_no || '-')}</div>
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
        renderNotices(filterList(committeeData.notices, "notices", ["title", "content"]));
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
    $("#btn-refresh-data").on("click", loadCommitteeData);

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
});
