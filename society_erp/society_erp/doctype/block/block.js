frappe.ui.form.on('Block', {
    // Trigger calculation when 'uds' or 'number_of_flats' is changed
    uds: function(frm) {
        calculate_total_uds(frm);
    },
    number_of_flats: function(frm) {
        calculate_total_uds(frm);
    },
    // Also trigger before saving just to be safe
    validate: function(frm) {
        calculate_total_uds(frm);
    }
});

function calculate_total_uds(frm) {
    if (frm.doc.uds && frm.doc.number_of_flats) {
        let total = frm.doc.uds * frm.doc.number_of_flats;
        frm.set_value('total_block_uds', total);
    }
}
