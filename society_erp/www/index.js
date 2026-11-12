/**
 * Public AoA Owner Contact Verification Status script
 * Loads dynamically on public home page via frappe.call without requiring login.
 */
frappe.ready(function () {
    const $loading = $("#owner-status-loading");
    const $panes = $("#owner-status-panes");
    const $searchInput = $("#owner-contact-search");
    const $totalBadge = $("#status-total-badge");
    const $matchCount = $("#search-match-count");

    let statusData = {
        fully_updated: [],
        duplicate_contact: [],
        missing_email: [],
        missing_mobile: [],
        missing_both: []
    };

    function escapeHtml(str) {
        if (!str) return "";
        return $("<div>").text(str).html();
    }

    function renderStatusLists(filterText) {
        const query = (filterText || "").trim().toLowerCase();
        let totalMatched = 0;

        const categories = [
            { key: "fully_updated", container: "#table-container-fully-updated", badge: "#count-fully-updated" },
            { key: "duplicate_contact", container: "#table-container-duplicate-contact", badge: "#count-duplicate-contact", isDuplicate: true },
            { key: "missing_email", container: "#table-container-missing-email", badge: "#count-missing-email" },
            { key: "missing_mobile", container: "#table-container-missing-mobile", badge: "#count-missing-mobile" },
            { key: "missing_both", container: "#table-container-missing-both", badge: "#count-missing-both" }
        ];

        categories.forEach(cat => {
            const list = statusData[cat.key] || [];
            const filtered = query
                ? list.filter(item => {
                    const flat = (item.flat_no || "").toLowerCase();
                    const name = (item.owner_name || "").toLowerCase();
                    const shared = (item.shared_flats ? item.shared_flats.join(" ") : "").toLowerCase();
                    return flat.includes(query) || name.includes(query) || shared.includes(query);
                })
                : list;

            totalMatched += filtered.length;
            $(cat.badge).text(list.length);

            const $container = $(cat.container).empty();

            if (filtered.length === 0) {
                $container.html(`
                    <div class="text-center py-4 text-muted small">
                        ${query ? 'No matching records found for current search.' : 'No records in this category.'}
                    </div>
                `);
                return;
            }

            // Desktop Table Layout (hidden on mobile)
            let tableHtml = `
                <div class="d-none d-md-block table-responsive">
                    <table class="table table-hover status-table mb-0">
                        <thead>
                            <tr>
                                <th style="width: 15%;">Flat No</th>
                                <th style="width: ${cat.isDuplicate ? '25%' : '35%'};">Owner Name</th>
                                <th style="width: 25%;">Registered Email</th>
                                <th style="width: 20%;">Registered Mobile</th>
                                ${cat.isDuplicate ? '<th style="width: 15%;">Shared With Flats</th>' : ''}
                            </tr>
                        </thead>
                        <tbody>
            `;

            filtered.forEach(item => {
                const emailHtml = item.masked_email
                    ? `<code>${escapeHtml(item.masked_email)}</code>`
                    : `<span class="missing-tag">⚠️ Missing Email</span>`;

                const mobileHtml = item.masked_mobile
                    ? `<code>${escapeHtml(item.masked_mobile)}</code>`
                    : `<span class="missing-tag">⚠️ Missing Mobile</span>`;

                let sharedHtml = "";
                if (cat.isDuplicate) {
                    const flats = (item.shared_flats || []).map(f => `<span class="badge badge-light border mr-1 font-weight-normal">${escapeHtml(f)}</span>`).join("");
                    const dupBadge = item.duplicate_type ? `<div class="text-info font-weight-bold" style="font-size: 0.72rem;">${escapeHtml(item.duplicate_type)}</div>` : "";
                    sharedHtml = `<td>${dupBadge}<div>${flats}</div></td>`;
                }

                tableHtml += `
                    <tr>
                        <td><span class="flat-badge">${escapeHtml(item.flat_no)}</span></td>
                        <td class="font-weight-500">${escapeHtml(item.owner_name)}</td>
                        <td>${emailHtml}</td>
                        <td>${mobileHtml}</td>
                        ${sharedHtml}
                    </tr>
                `;
            });

            tableHtml += `
                        </tbody>
                    </table>
                </div>
            `;

            // Mobile Cards Stack Layout (hidden on desktop)
            let cardsHtml = `<div class="d-block d-md-none p-2">`;
            filtered.forEach(item => {
                const emailHtml = item.masked_email
                    ? `<span class="text-dark small"><code>${escapeHtml(item.masked_email)}</code></span>`
                    : `<span class="missing-tag">⚠️ Missing</span>`;

                const mobileHtml = item.masked_mobile
                    ? `<span class="text-dark small"><code>${escapeHtml(item.masked_mobile)}</code></span>`
                    : `<span class="missing-tag">⚠️ Missing</span>`;

                let sharedMobileHtml = "";
                if (cat.isDuplicate && item.shared_flats && item.shared_flats.length) {
                    const flats = item.shared_flats.map(f => `<span class="badge badge-light border mr-1 font-weight-normal">${escapeHtml(f)}</span>`).join("");
                    sharedMobileHtml = `
                        <div class="mt-2 pt-1 border-top" style="font-size: 0.78rem;">
                            <span class="text-info font-weight-bold d-block" style="font-size: 0.72rem;">${escapeHtml(item.duplicate_type || 'SHARED CONTACT')}</span>
                            <span class="text-muted">Same contact also used for:</span> ${flats}
                        </div>
                    `;
                }

                cardsHtml += `
                    <div class="owner-card-item bg-white p-2 mb-2 rounded border">
                        <div class="d-flex justify-content-between align-items-center mb-1">
                            <span class="flat-badge">${escapeHtml(item.flat_no)}</span>
                            <span class="font-weight-bold text-dark" style="font-size: 0.88rem;">${escapeHtml(item.owner_name)}</span>
                        </div>
                        <div class="d-flex justify-content-between align-items-center mt-2 pt-1 border-top" style="font-size: 0.82rem;">
                            <div class="pr-2">
                                <span class="text-muted d-block" style="font-size: 0.72rem;">EMAIL</span>
                                ${emailHtml}
                            </div>
                            <div class="text-right pl-2">
                                <span class="text-muted d-block" style="font-size: 0.72rem;">MOBILE</span>
                                ${mobileHtml}
                            </div>
                        </div>
                        ${sharedMobileHtml}
                    </div>
                `;
            });
            cardsHtml += `</div>`;

            $container.html(tableHtml + cardsHtml);
        });

        if (query) {
            $matchCount.text(`Showing ${totalMatched} matches across categories`);
        } else {
            $matchCount.text("");
        }
    }

    // Fetch contact status from whitelisted endpoint (allow_guest=True)
    frappe.call({
        method: "society_erp.www.index.get_owner_contact_status",
        callback: function (r) {
            $loading.addClass("d-none");
            $panes.removeClass("d-none");

            if (r && r.message) {
                statusData = r.message;
                const counts = statusData.counts || {};
                const verifiedCount = counts.already_logged_in || 0;
                $totalBadge.html(`Pending: <strong>${counts.total_pending || 0}</strong> &bull; Verified: <strong>${verifiedCount}</strong> / ${counts.total || 0}`);
                renderStatusLists("");
            } else {
                $totalBadge.text("Unable to load records");
            }
        },
        error: function () {
            $loading.html(`
                <div class="text-danger small py-3">
                    Failed to fetch owner contact status. Please refresh the page or try again later.
                </div>
            `);
        }
    });

    // Debounced search input handler
    let searchTimer = null;
    $searchInput.on("input", function () {
        const val = $(this).val();
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
            renderStatusLists(val);
        }, 200);
    });
});
