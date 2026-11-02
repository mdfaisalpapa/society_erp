frappe.ui.form.on("Voting Poll", {
    refresh(frm) {
        if (frm.is_new()) return;

        if (frm.doc.status === "Open") {
            frm.add_custom_button(__("Extend Poll"), () => {
                frappe.prompt([
                    {fieldname: "new_end_datetime", label: __("New Closing Date & Time"), fieldtype: "Datetime", reqd: 1, default: frm.doc.end_datetime},
                    {fieldname: "reason", label: __("Reason for Extension"), fieldtype: "Small Text", reqd: 1}
                ], values => {
                    frappe.call({
                        method: "society_erp.society_erp.doctype.voting_poll.voting_api.extend_poll",
                        args: {poll_name: frm.doc.name, new_end_datetime: values.new_end_datetime, reason: values.reason},
                        freeze: true, freeze_message: __("Extending poll…"),
                        callback: r => { if (!r.exc) { frappe.show_alert({message: __("Poll closing time extended."), indicator: "green"}); frm.reload_doc(); } }
                    });
                }, __("Extend Voting Period"), __("Extend Poll"));
            }, __("Poll Actions"));

            frm.add_custom_button(__("End Poll"), () => {
                frappe.prompt([
                    {fieldname: "reason", label: __("Reason for Early Closure"), fieldtype: "Small Text", reqd: 1}
                ], values => {
                    frappe.confirm(__("End this poll immediately? This cannot be reversed and voting will stop."), () => {
                        frappe.call({
                            method: "society_erp.society_erp.doctype.voting_poll.voting_api.end_poll",
                            args: {poll_name: frm.doc.name, reason: values.reason},
                            freeze: true, freeze_message: __("Closing poll…"),
                            callback: r => { if (!r.exc) { frappe.show_alert({message: __("Poll closed."), indicator: "green"}); frm.reload_doc(); } }
                        });
                    });
                }, __("End Poll"), __("Continue"));
            }, __("Poll Actions"));
        }

        if (frm.doc.status === "Closed" && frm.doc.publish_ballot_register && !frm.doc.ballot_register_published) {
            frm.add_custom_button(__("Publish Ballot Register"), () => {
                frappe.confirm(__("Publish the anonymous ballot register? This action is final."), () => {
                    frappe.call({
                        method: "society_erp.society_erp.doctype.voting_poll.voting_api.publish_ballot_register",
                        args: {poll_name: frm.doc.name}, freeze: true,
                        callback: r => { if (!r.exc) { frappe.show_alert({message: __("Ballot register published."), indicator: "green"}); frm.reload_doc(); } }
                    });
                });
            }, __("Poll Actions"));
        }


        if (frm.doc.status === "Closed") {
            frm.add_custom_button(__("View Election Audit Summary"), () => {
                frappe.call({
                    method: "society_erp.society_erp.doctype.voting_poll.voting_api.get_poll_audit_summary",
                    args: {poll_name: frm.doc.name}, freeze: true,
                    callback: r => {
                        if (r.exc || !r.message) return;
                        const d = r.message;
                        const rows = (d.option_totals || []).map(x => `<tr><td>${frappe.utils.escape_html(x.option)}</td><td>${x.votes}</td><td>${Number(x.weighted_total || 0).toFixed(3)}</td></tr>`).join("");
                        const html = `<p><b>Ballots:</b> ${d.ballot_count} &nbsp; <b>Participation:</b> ${d.participation_count}</p><p><b>Participation / ballot match:</b> ${d.participation_ballot_match ? "Yes" : "NO - INVESTIGATE"}</p><table class="table table-bordered"><thead><tr><th>Option</th><th>Votes</th><th>Weighted Total</th></tr></thead><tbody>${rows}</tbody></table><p><b>Register published:</b> ${d.published ? "Yes" : "No"}</p><p><b>Register hash:</b> <code>${d.register_hash || "Not published"}</code></p>`;
                        frappe.msgprint({title: __("Election Audit Summary"), message: html, wide: true});
                    }
                });
            }, __("Poll Actions"));
        }

        if (frm.doc.status === "Closed" && frm.doc.ballot_register_published) {
            frm.add_custom_button(__("Download Ballot Register (CSV)"), () => {
                const url = `/api/method/society_erp.society_erp.doctype.voting_poll.voting_api.download_published_ballot_register?poll_name=${encodeURIComponent(frm.doc.name)}`;
                window.open(url);
            }, __("Poll Actions"));
        }
    }
});


frappe.ui.form.on("Voting Poll", {
    refresh(frm) {
        // Show only for Draft/Scheduled polls without an existing snapshot.
        if (
            !frm.is_new() &&
            ["Draft", "Scheduled"].includes(frm.doc.status) &&
            !frm.doc.eligibility_snapshot_created
        ) {
            frm.add_custom_button(
                __("Generate Eligibility Snapshot"),
                () => generate_eligibility_snapshot(frm),
                __("Eligibility")
            );
        }
    }
});

function generate_eligibility_snapshot(frm) {
    frappe.call({
        method: "society_erp.society_erp.doctype.voting_poll.voting_poll.generate_eligibility",
        args: {
            poll_name: frm.doc.name,
            preview_only: 1
        },
        freeze: true,
        freeze_message: __("Preparing eligibility preview..."),

        callback(r) {
            if (!r.message) return;

            const d = r.message;

            // Data-integrity issues must be resolved before snapshot creation.
            if (d.data_issue_flats > 0) {
                frappe.msgprint({
                    title: __("Cannot Generate Snapshot"),
                    indicator: "red",
                    message: `
                        <p>There are <b>${d.data_issue_flats}</b>
                        data issues that must be resolved first.</p>
                        <p>Please review the eligibility details before proceeding.</p>
                    `
                });
                return;
            }

            let summary = `
                <table class="table table-bordered">
                    <tr>
                        <td>Eligible voters/flats</td>
                        <th>${d.eligible_flats}</th>
                    </tr>
                    <tr>
                        <td>Pending account setup</td>
                        <th>${d.pending_account_setup_flats}</th>
                    </tr>
                    <tr>
                        <td>Excluded flats</td>
                        <th>${d.excluded_flats}</th>
                    </tr>
                    <tr>
                        <td>Data issues</td>
                        <th>${d.data_issue_flats}</th>
                    </tr>
                    ${
                        d.poll_type === "Association Voting"
                            ? `<tr>
                                <td>Total eligible UDS</td>
                                <th>${flt(d.total_eligible_uds, 3)}</th>
                               </tr>`
                            : ""
                    }
                </table>
            `;

            if (d.pending_account_setup_flats > 0) {
                summary += `
                    <p class="text-warning">
                        Pending account setup flats will not be included
                        in the eligible voter snapshot.
                    </p>
                `;
            }

            summary += `
                <p><b>Once generated, the eligibility snapshot is frozen.</b>
                This action cannot be repeated for this poll.</p>
            `;

            frappe.confirm(
                summary + "<p>Do you want to generate the snapshot?</p>",

                () => {
                    frappe.call({
                        method: "society_erp.society_erp.doctype.voting_poll.voting_poll.generate_eligibility",
                        args: {
                            poll_name: frm.doc.name,
                            preview_only: 0
                        },
                        freeze: true,
                        freeze_message: __("Generating eligibility snapshot..."),

                        callback(result) {
                            if (!result.message) return;

                            frappe.msgprint({
                                title: __("Snapshot Generated"),
                                indicator: "green",
                                message: `
                                    Eligibility snapshot successfully created
                                    for <b>${result.message.created}</b> voters/flats.
                                `
                            });

                            frm.reload_doc();
                        }
                    });
                }
            );
        }
    });
}
