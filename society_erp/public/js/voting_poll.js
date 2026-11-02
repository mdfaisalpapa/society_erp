frappe.ui.form.on("Voting Poll", {
    refresh(frm) {
        if (frm.is_new() || frm.doc.eligibility_snapshot_created) return;
        if (!["Draft", "Scheduled"].includes(frm.doc.status)) return;

        frm.add_custom_button(__("Preview Eligibility"), () => {
            frappe.call({
                method: "society_erp.society_erp.doctype.voting_poll.voting_poll.generate_eligibility",
                args: {
                    poll_name: frm.doc.name,
                    preview_only: 1
                },
                freeze: true,
                freeze_message: __("Checking voting eligibility..."),
                callback(r) {
                    if (r.message) show_eligibility_preview(r.message);
                }
            });
        }, __("Eligibility"));
    }
});


function show_eligibility_preview(data) {
    const tabs = {
        eligible: {
            label: __("Eligible"),
            rows: data.eligible_details || [],
            headers: ["Flat", "Voter Type", "Block", "Voting Weight"],
            fields: ["flat", "voter_type", "block", "voting_weight"]
        },
        pending: {
            label: __("Pending"),
            rows: data.pending_account_setup_details || [],
            headers: ["Flat", "Voter Type", "Block", "Reason"],
            fields: ["flat", "voter_type", "block", "reason"]
        },
        issues: {
            label: __("Data Issues"),
            rows: data.data_issue_details || [],
            headers: ["Flat", "Reason"],
            fields: ["flat", "reason"]
        },
        excluded: {
            label: __("Excluded"),
            rows: data.excluded_details || [],
            headers: ["Flat", "Reason"],
            fields: ["flat", "reason"]
        }
    };

    let activeTab = "eligible";
    let searchText = "";
    let selectedBlock = "";

    const blocks = [...new Set(
        Object.values(tabs).flatMap(tab =>
            tab.rows.map(row => row.block).filter(Boolean)
        )
    )].sort();

    const dialog = new frappe.ui.Dialog({
        title: __("Voting Eligibility Preview"),
        size: "extra-large",
        fields: [{
            fieldtype: "HTML",
            fieldname: "preview_html"
        }],
        primary_action_label: __("Close"),
        primary_action() {
            dialog.hide();
        }
    });

    const wrapper = dialog.fields_dict.preview_html.$wrapper;

    function esc(value) {
        return frappe.utils.escape_html(String(value ?? "-"));
    }

    function render() {
        const tab = tabs[activeTab];

        const filtered = tab.rows.filter(row => {
            const matchesBlock =
                !selectedBlock || row.block === selectedBlock;

            const searchable = tab.fields
                .map(field => row[field] ?? "")
                .join(" ")
                .toLowerCase();

            return matchesBlock &&
                searchable.includes(searchText.toLowerCase());
        });

        const headers = tab.headers.map(h =>
            `<th>${esc(h)}</th>`
        ).join("");

        const body = filtered.length
            ? filtered.map(row => `
                <tr>
                    ${tab.fields.map(field =>
                        `<td>${esc(row[field])}</td>`
                    ).join("")}
                </tr>
            `).join("")
            : `<tr><td colspan="${tab.fields.length}"
                class="text-center text-muted">
                ${__("No matching records")}
            </td></tr>`;

        const tabButtons = Object.entries(tabs).map(([key, item]) => `
            <button type="button"
                class="btn btn-sm ${activeTab === key ? "btn-primary" : "btn-default"}"
                data-tab="${key}">
                ${esc(item.label)} (${item.rows.length})
            </button>
        `).join(" ");

        const blockOptions = [
            `<option value="">${__("All Blocks")}</option>`,
            ...blocks.map(block =>
                `<option value="${esc(block)}"
                    ${selectedBlock === block ? "selected" : ""}>
                    ${esc(block)}
                </option>`
            )
        ].join("");

        wrapper.html(`
            <div class="row text-center mb-4">
                ${summary_card(__("Eligible"), data.eligible_flats)}
                ${summary_card(__("Pending Accounts"), data.pending_account_setup_flats)}
                ${summary_card(__("Data Issues"), data.data_issue_flats)}
                ${summary_card(__("Excluded"), data.excluded_flats)}
            </div>

            <div class="alert alert-info">
                ${__("Preview only. No eligibility records have been created and the snapshot has not been frozen.")}
            </div>

            <div class="mb-3" style="display:flex;gap:8px;flex-wrap:wrap">
                ${tabButtons}
            </div>

            <div class="row mb-3">
                <div class="col-sm-7">
                    <input type="text"
                        class="form-control"
                        id="eligibility-search"
                        placeholder="${__("Search flat, voter or reason...")}"
                        value="${esc(searchText)}">
                </div>
                <div class="col-sm-5">
                    <select class="form-control" id="eligibility-block">
                        ${blockOptions}
                    </select>
                </div>
            </div>

            <div class="mb-2 text-muted">
                ${__("Showing")} ${filtered.length} ${__("of")} ${tab.rows.length}
            </div>

            <div style="max-height:400px;overflow:auto">
                <table class="table table-bordered table-hover">
                    <thead style="position:sticky;top:0;background:var(--card-bg);z-index:1">
                        <tr>${headers}</tr>
                    </thead>
                    <tbody>${body}</tbody>
                </table>
            </div>

            ${["eligible", "pending"].includes(activeTab) ? `
                <div class="mt-3">
                    <button type="button"
                        class="btn btn-default"
                        id="eligibility-export">
                        <i class="fa fa-download"></i>
                        ${__("Export CSV")}
                    </button>
                </div>
            ` : ""}
        `);

        wrapper.find("[data-tab]").on("click", function() {
            activeTab = $(this).attr("data-tab");
            render();
        });

        wrapper.find("#eligibility-search").on("input", function() {
            searchText = $(this).val();
            const cursor = this.selectionStart;
            render();
            const input = wrapper.find("#eligibility-search")[0];
            input.focus();
            input.setSelectionRange(cursor, cursor);
        });

        wrapper.find("#eligibility-block").on("change", function() {
            selectedBlock = $(this).val();
            render();
        });

        wrapper.find("#eligibility-export").on("click", function() {
            export_csv(tabs[activeTab]);
        });
    }

    function export_csv(tab) {
        const rows = [
            tab.headers,
            ...tab.rows.map(row =>
                tab.fields.map(field => row[field] ?? "")
            )
        ];

        const csv = rows.map(row =>
            row.map(value => {
                let text = String(value ?? "");

                // Protect spreadsheet users from formula injection.
                if (/^[\s]*[=+\-@]/.test(text)) {
                    text = "'" + text;
                }

                return '"' + text.replace(/"/g, '""') + '"';
            }).join(",")
        ).join("\r\n");

        const blob = new Blob(["\uFEFF" + csv], {
            type: "text/csv;charset=utf-8;"
        });

        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `voting-${tab.label.toLowerCase().replace(/\s+/g, "-")}.csv`;
        link.click();
        URL.revokeObjectURL(url);
    }

    render();
    dialog.show();
}


function summary_card(label, value) {
    return `
        <div class="col-sm-3">
            <div class="border rounded p-3 text-center">
                <div class="text-muted">
                    ${frappe.utils.escape_html(String(label))}
                </div>
                <h3>${frappe.utils.escape_html(String(value ?? 0))}</h3>
            </div>
        </div>
    `;
}
