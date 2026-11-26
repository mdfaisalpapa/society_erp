// Copyright (c) 2026, Society ERP and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bye-Law Consultation", {
	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Import Clauses"), () => {
				const d = new frappe.ui.Dialog({
					title: __("Import Clauses"),
					fields: [
						{
							fieldname: "file_url",
							fieldtype: "Attach",
							label: __("Source File (.docx or .csv)"),
							reqd: 1,
						},
						{
							fieldname: "readonly_clauses",
							fieldtype: "Small Text",
							label: __("Read-Only Clauses / Chapters (optional)"),
							description: __("Comma-separated clause numbers or chapters, e.g. 1, 2, CHAPTER I"),
						},
						{
							fieldname: "readonly_reason",
							fieldtype: "Data",
							label: __("Read-Only Reason"),
							default: "Mandatory under TNAOA 2022",
						},
						{
							fieldname: "replace_existing",
							fieldtype: "Check",
							label: __("Replace existing clauses (blocked if comments exist)"),
						},
					],
					primary_action_label: __("Import"),
					primary_action(values) {
						frappe.call({
							method: "society_erp.byelaws_importer.import_clauses_from_file",
							args: {
								consultation: frm.doc.name,
								file_url: values.file_url,
								replace_existing: values.replace_existing ? 1 : 0,
								readonly_clauses: values.readonly_clauses || "",
								readonly_reason: values.readonly_reason || "",
							},
							freeze: true,
							freeze_message: __("Importing clauses..."),
							callback(r) {
								if (r.message) {
									d.hide();
									frappe.show_alert({
										message: __("Imported {0} clauses ({1} read-only)", [
											r.message.imported,
											r.message.readonly_count,
										]),
										indicator: "green",
									});
									frm.reload_doc();
								}
							},
						});
					},
				});
				d.show();
			});
		}
	},
});
