// Copyright (c) 2026, Mohammed Faisal and contributors
// Owners form behaviour.

frappe.ui.form.on("Owners", {
    refresh(frm) {
        // linked_user is maintained by the server-side account provisioner.
        frm.set_df_property("linked_user", "read_only", 1);

        if (frm.doc.linked_user) {
            frm.set_intro(
                __("Login account linked: {0}", [
                    `<a href="/app/user/${encodeURIComponent(frm.doc.linked_user)}">${frappe.utils.escape_html(frm.doc.linked_user)}</a>`
                ]),
                "green"
            );
        }
    },

    email(frm) {
        if (frm.doc.email) {
            frm.set_value("email", frm.doc.email.trim().toLowerCase());
        }
    }
});
