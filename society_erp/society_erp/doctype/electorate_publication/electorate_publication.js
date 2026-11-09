frappe.ui.form.on("Electorate Publication", {
    refresh(frm) {
        if (frm.is_new()) return;

        const roles = frappe.user_roles || [];
        const can_manage = roles.includes("System Manager") || roles.includes("Society Committee Member");
        if (!can_manage) return;

        // View Members button
        frm.add_custom_button(__("View Members"), () => {
            frappe.route_options = { publication: frm.doc.name };
            frappe.set_route("List", "Provisional Electorate Member", "List");
        }, __("Actions"));

        // View Objections button
        frm.add_custom_button(__("View Objections"), () => {
            frappe.route_options = { publication: frm.doc.name };
            frappe.set_route("List", "Electorate Objection", "List");
        }, __("Actions"));

        // Status-based workflow actions
        if (frm.doc.status === "Draft") {
            frm.add_custom_button(__("Generate Electorate"), async () => {
                const response = await frappe.call({
                    method: "society_erp.society_erp.doctype.electorate_publication.electorate_publication.generate_draft",
                    args: { publication_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Evaluating residential flats and calculating UDS weights…"),
                });
                if (!response.exc) {
                    frappe.show_alert({ message: __("Draft electorate generated successfully"), indicator: "green" });
                    await frm.reload_doc();
                }
            }).addClass("btn-primary");

            if (frm.doc.total_flats_evaluated > 0) {
                frm.add_custom_button(__("Publish Electorate"), async () => {
                    if (!window.confirm(__("Publish this electorate for resident inspection and objections?"))) return;
                    const response = await frappe.call({
                        method: "society_erp.society_erp.doctype.electorate_publication.electorate_publication.publish",
                        args: { publication_name: frm.doc.name },
                        freeze: true,
                        freeze_message: __("Publishing electorate…"),
                    });
                    if (!response.exc) {
                        frappe.show_alert({ message: __("Electorate published"), indicator: "green" });
                        await frm.reload_doc();
                    }
                }, __("Workflow"));
            }
        }

        if (frm.doc.status === "Published") {
            frm.add_custom_button(__("Close Objections Window"), async () => {
                if (!window.confirm(__("Close objection submission window? Incoming submissions will be blocked."))) return;
                const response = await frappe.call({
                    method: "society_erp.society_erp.doctype.electorate_publication.electorate_publication.close_objections",
                    args: { publication_name: frm.doc.name },
                    freeze: true,
                    freeze_message: __("Closing objections window…"),
                });
                if (!response.exc) {
                    frappe.show_alert({ message: __("Objections window closed"), indicator: "orange" });
                    await frm.reload_doc();
                }
            }, __("Workflow")).addClass("btn-warning");
        }

        if (frm.doc.status === "Objections Closed" || frm.doc.status === "Published") {
            frm.add_custom_button(__("Approve & Certify Roll"), () => {
                frappe.prompt([
                    {
                        fieldname: "notes",
                        fieldtype: "Small Text",
                        label: __("Certification Notes"),
                        reqd: 0,
                    },
                ], async (values) => {
                    const response = await frappe.call({
                        method: "society_erp.society_erp.doctype.electorate_publication.electorate_publication.approve",
                        args: {
                            publication_name: frm.doc.name,
                            certified_by: frappe.session.user,
                            notes: values.notes || "",
                        },
                        freeze: true,
                        freeze_message: __("Computing canonical manifest hash and certifying roll…"),
                    });
                    if (!response.exc) {
                        frappe.show_alert({ message: __("Electorate roll approved and certified"), indicator: "green" });
                        await frm.reload_doc();
                    }
                }, __("Approve Electorate Roll"), __("Certify & Approve"));
            }, __("Workflow")).addClass("btn-primary");
        }
    },
});
