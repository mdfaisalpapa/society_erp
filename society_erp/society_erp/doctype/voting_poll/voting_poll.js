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
