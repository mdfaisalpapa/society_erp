frappe.ready(function() {
    // Client-side filtering logic
    $('#status-filter').on('change', function() {
        let selectedStatus = $(this).val();
        if (selectedStatus === 'All') {
            $('.ticket-row').show();
        } else {
            $('.ticket-row').hide();
            $(`.ticket-row[data-status="${selectedStatus}"]`).show();
        }
    });

    // File upload helper
function uploadFile(file, docname) {
    return new Promise((resolve, reject) => {
        if (!file) return resolve();
        let reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = function() {
            frappe.call({
                // FIX: Changed from 'uploadfile' to 'upload_file'
                method: 'upload_file', 
                args: {
                    doctype: 'Maintenance Ticket',
                    docname: docname,
                    filename: file.name,
                    filedata: reader.result.split(',')[1],
                    is_private: 1,
                    fieldname: 'photo',
                    from_form: 1
                },
                callback: resolve
            });
        };
        reader.onerror = reject;
    });
}

    // Form submission logic
    $('#create-ticket-form').on('submit', function(e) {
        e.preventDefault();
        $('#ticket-submit-btn').prop('disabled', true).text('Submitting...');
        
        let payload = {
            doctype: 'Maintenance Ticket',
            resident: $('#resident_flat').val(),
            category: $('#ticket_category').val(),
            description: $('#ticket_description').val(),
            status: 'Open'
        };

        frappe.call({
            method: 'frappe.client.insert',
            args: { doc: payload },
            callback: async function(r) {
                if (!r.exc && r.message) {
                    let docname = r.message.name;
                    let photoFile = $('#ticket_photo')[0].files[0];
                    
                    try {
                        if (photoFile) await uploadFile(photoFile, docname);
                        
                        frappe.msgprint({
                            title: 'Success',
                            indicator: 'green',
                            message: 'Maintenance ticket created successfully.'
                        });
                        $('#createTicketModal').modal('hide');
                        setTimeout(() => location.reload(), 1500);
                    } catch (err) {
                        frappe.msgprint('Ticket created, but photo upload failed.');
                        $('#ticket-submit-btn').prop('disabled', false).text('Submit Ticket');
                    }
                } else {
                    $('#ticket-submit-btn').prop('disabled', false).text('Submit Ticket');
                }
            }
        });
    });
});
