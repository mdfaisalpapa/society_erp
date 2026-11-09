frappe.ready(function () {
    const API = 'society_erp.voting.portal_api';

    const state = {
        publications: [],
        currentPub: null,
        selfRecords: [],
        myObjections: [],
        directory: [],
        filteredDirectory: [],
    };

    const $ = (selector) => document.querySelector(selector);

    const el = {
        alert: $('#pe-alert'),
        pubSelect: $('#pe-publication-select'),
        statusBadge: $('#pe-pub-status-badge'),
        pubMeta: $('#pe-pub-meta'),
        selfLoading: $('#pe-self-loading'),
        selfEmpty: $('#pe-self-empty'),
        selfContainer: $('#pe-self-table-container'),
        selfRows: $('#pe-self-rows'),
        objectionsEmpty: $('#pe-objections-empty'),
        objectionsContainer: $('#pe-objections-table-container'),
        objectionsRows: $('#pe-objections-rows'),
        directorySearch: $('#pe-directory-search'),
        directoryRows: $('#pe-directory-rows'),
        claimBtn: $('#pe-claim-omitted-btn'),
        modal: $('#pe-objection-modal'),
        modalTitle: $('#pe-modal-title'),
        objFlat: $('#pe-obj-flat'),
        objType: $('#pe-obj-type'),
        objDetails: $('#pe-obj-details'),
        submitObjBtn: $('#pe-submit-objection-btn'),
    };

    function showAlert(msg, type = 'danger') {
        el.alert.className = `alert alert-${type}`;
        el.alert.classList.remove('d-none');
        el.alert.textContent = msg;
    }

    function clearAlert() {
        el.alert.className = 'alert d-none';
        el.alert.textContent = '';
    }

    function call(method, args = {}) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: `${API}.${method}`,
                args,
                callback: (r) => {
                    if (r && !r.exc) resolve(r.message);
                    else reject(new Error((r && r.message) || 'Request failed.'));
                },
                error: (r) => reject(new Error((r && r.message) || 'Network error.')),
            });
        });
    }

    async function loadPublications() {
        try {
            const pubs = await call('get_provisional_electorates');
            state.publications = pubs || [];
            el.pubSelect.innerHTML = '';
            if (state.publications.length === 0) {
                el.pubSelect.innerHTML = '<option value="">No publications available</option>';
                el.statusBadge.textContent = 'None Available';
                el.selfLoading.classList.add('d-none');
                el.selfEmpty.classList.remove('d-none');
                return;
            }
            state.publications.forEach((p) => {
                const opt = document.createElement('option');
                opt.value = p.name;
                opt.textContent = `${p.title} (v${p.version}) - ${p.status}`;
                el.pubSelect.appendChild(opt);
            });
            const urlParams = new URLSearchParams(window.location.search);
            const targetPub = urlParams.get('publication');
            const initialPub = (targetPub && state.publications.find(p => p.name === targetPub)) ? targetPub : state.publications[0].name;
            el.pubSelect.value = initialPub;
            await selectPublication(initialPub);
        } catch (err) {
            showAlert(err.message);
        }
    }

    async function selectPublication(name) {
        clearAlert();
        el.selfLoading.classList.remove('d-none');
        el.selfContainer.classList.add('d-none');
        el.selfEmpty.classList.add('d-none');

        try {
            const data = await call('get_electorate_details', { publication_name: name });
            state.currentPub = data.publication;
            state.selfRecords = data.self_records || [];
            state.myObjections = data.my_objections || [];
            state.directory = data.directory || [];
            state.filteredDirectory = state.directory;

            renderPubHeader();
            renderSelfRecords();
            renderMyObjections();
            renderDirectory();
        } catch (err) {
            showAlert(err.message);
        } finally {
            el.selfLoading.classList.add('d-none');
        }
    }

    function renderPubHeader() {
        const pub = state.currentPub;
        if (!pub) return;

        let badgeClass = 'badge-secondary';
        if (pub.status === 'Published') badgeClass = 'badge-primary';
        else if (pub.status === 'Approved') badgeClass = 'badge-success';
        else if (pub.status === 'Objections Closed') badgeClass = 'badge-warning';

        el.statusBadge.className = `badge ${badgeClass} p-2`;
        el.statusBadge.textContent = pub.status;

        let metaHtml = `
            <div class="col-sm-6 col-md-3"><strong>Flats Evaluated:</strong> ${pub.total_flats_evaluated}</div>
            <div class="col-sm-6 col-md-3"><strong>Eligible Voters:</strong> <span class="text-success font-weight-bold">${pub.eligible_count}</span></div>
            <div class="col-sm-6 col-md-3"><strong>Excluded:</strong> <span class="text-danger font-weight-bold">${pub.excluded_count}</span></div>
            <div class="col-sm-6 col-md-3"><strong>Objections Close:</strong> ${pub.objection_submission_deadline ? pub.objection_submission_deadline : 'Not set'}</div>
        `;
        if (pub.dues_enforcement_enabled) {
            metaHtml += `
                <div class="col-12 mt-2">
                    <span class="badge badge-info p-1 mr-2">Dues Enforcement Active</span>
                    Cutoff Date: <strong>${pub.dues_cutoff_date}</strong> | Dues Threshold: <strong>₹${Number(pub.dues_threshold).toFixed(2)}</strong>
                </div>
            `;
        }
        if (pub.electorate_content_hash) {
            metaHtml += `
                <div class="col-12 mt-2 small font-monospace">
                    <strong>Certified Content Hash:</strong> <code>${pub.electorate_content_hash}</code>
                </div>
            `;
        }
        el.pubMeta.innerHTML = metaHtml;

        if (pub.can_submit_objection) {
            el.claimBtn.classList.remove('d-none');
        } else {
            el.claimBtn.classList.add('d-none');
        }
    }

    function renderSelfRecords() {
        el.selfRows.innerHTML = '';
        if (state.selfRecords.length === 0) {
            el.selfEmpty.classList.remove('d-none');
            el.selfContainer.classList.add('d-none');
            return;
        }

        el.selfEmpty.classList.add('d-none');
        el.selfContainer.classList.remove('d-none');

        state.selfRecords.forEach((m) => {
            const tr = document.createElement('tr');
            const isEligible = m.eligibility_status === 'Eligible';
            const badgeClass = isEligible ? 'badge-success' : 'badge-danger';
            const duesText = state.currentPub.dues_enforcement_enabled
                ? `₹${Number(m.outstanding_dues || 0).toFixed(2)}`
                : 'Not enforced';

            let actionHtml = '';
            if (state.currentPub.can_submit_objection) {
                actionHtml = `<button class="btn btn-sm btn-outline-danger btn-object" data-flat="${m.flat_no}" data-reason="${m.exclusion_reason || ''}">Object / Correct</button>`;
            } else {
                actionHtml = `<span class="text-muted small">Submissions Closed</span>`;
            }

            tr.innerHTML = `
                <td><strong>${m.flat_no}</strong></td>
                <td>${m.block || '-'}</td>
                <td>${m.owner_name}</td>
                <td>${Number(m.voting_weight || 1).toFixed(3)}</td>
                <td>${duesText}</td>
                <td>
                    <span class="badge ${badgeClass}">${m.eligibility_status}</span>
                    ${!isEligible && m.exclusion_reason ? `<div class="small text-danger">${m.exclusion_reason}</div>` : ''}
                </td>
                <td>${actionHtml}</td>
            `;
            el.selfRows.appendChild(tr);
        });

        document.querySelectorAll('.btn-object').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                const flat = e.target.getAttribute('data-flat');
                const reason = e.target.getAttribute('data-reason');
                openObjectionModal(flat, reason.includes('Dues') ? 'Incorrect Dues / Payment Omission' : 'Incorrect Exclusion');
            });
        });
    }

    function renderMyObjections() {
        el.objectionsRows.innerHTML = '';
        if (state.myObjections.length === 0) {
            el.objectionsEmpty.classList.remove('d-none');
            el.objectionsContainer.classList.add('d-none');
            return;
        }

        el.objectionsEmpty.classList.add('d-none');
        el.objectionsContainer.classList.remove('d-none');

        state.myObjections.forEach((obj) => {
            const tr = document.createElement('tr');
            let statusBadge = 'badge-secondary';
            if (obj.status === 'Accepted') statusBadge = 'badge-success';
            else if (obj.status === 'Rejected') statusBadge = 'badge-danger';
            else if (obj.status === 'Evidence Requested') statusBadge = 'badge-warning';

            tr.innerHTML = `
                <td>${String(obj.creation || '').slice(0, 10)}</td>
                <td><strong>${obj.flat_no}</strong></td>
                <td>${obj.objection_type}</td>
                <td><span class="badge ${statusBadge}">${obj.status}</span></td>
                <td>
                    <div>${obj.details}</div>
                    ${obj.officer_comments ? `<div class="text-info small mt-1"><strong>Officer:</strong> ${obj.officer_comments}</div>` : ''}
                    ${obj.evidence_request_details ? `<div class="text-warning small mt-1"><strong>Action Required:</strong> ${obj.evidence_request_details}</div>` : ''}
                </td>
            `;
            el.objectionsRows.appendChild(tr);
        });
    }

    function renderDirectory() {
        el.directoryRows.innerHTML = '';
        const list = state.filteredDirectory.slice(0, 200); // paginate first 200 for fast dom rendering
        list.forEach((m) => {
            const tr = document.createElement('tr');
            const isEligible = m.eligibility_status === 'Eligible';
            tr.innerHTML = `
                <td><strong>${m.flat_no}</strong></td>
                <td>${m.block || '-'}</td>
                <td>${m.masked_voter_name || '***'}</td>
                <td><span class="badge ${isEligible ? 'badge-success' : 'badge-danger'}">${m.eligibility_status}</span></td>
            `;
            el.directoryRows.appendChild(tr);
        });
    }

    function openObjectionModal(flat = '', type = 'Missing Voter / Omitted Flat') {
        el.objFlat.value = flat;
        el.objFlat.readOnly = !!flat;
        el.objType.value = type;
        el.objDetails.value = '';
        el.modalTitle.textContent = flat ? `Objection for Flat ${flat}` : 'Claim Omitted Flat';
        window.$(el.modal).modal('show');
    }

    el.pubSelect.addEventListener('change', (e) => selectPublication(e.target.value));

    el.claimBtn.addEventListener('click', () => openObjectionModal('', 'Missing Voter / Omitted Flat'));

    el.directorySearch.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) {
            state.filteredDirectory = state.directory;
        } else {
            state.filteredDirectory = state.directory.filter(
                (m) => m.flat_no.toLowerCase().includes(query) || (m.block && m.block.toLowerCase().includes(query))
            );
        }
        renderDirectory();
    });

    el.submitObjBtn.addEventListener('click', async () => {
        const flat = el.objFlat.value.trim();
        const type = el.objType.value;
        const details = el.objDetails.value.trim();

        if (!flat || !details) {
            alert('Flat number and details are required.');
            return;
        }

        try {
            el.submitObjBtn.disabled = true;
            await call('submit_objection', {
                publication_name: state.currentPub.name,
                flat_no: flat,
                objection_type: type,
                details: details,
            });
            window.$(el.modal).modal('hide');
            await selectPublication(state.currentPub.name);
            showAlert('Your objection has been submitted and queued for officer review.', 'success');
        } catch (err) {
            alert(err.message);
        } finally {
            el.submitObjBtn.disabled = false;
        }
    });

    const urlParams = new URLSearchParams(window.location.search);
    const pollParam = urlParams.get('poll');
    const backBtn = $('#pe-back-btn');
    if (pollParam && backBtn) {
        backBtn.textContent = `← Back to Voting Poll (${pollParam})`;
        backBtn.href = `/consensus-vote?poll=${encodeURIComponent(pollParam)}`;
    }

    loadPublications();
});
