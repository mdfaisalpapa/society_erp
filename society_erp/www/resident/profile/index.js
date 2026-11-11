frappe.ready(function() {
    // 1. Discrepancy update request handler
    $('.btn-update-req').on('click', function(e) {
        e.preventDefault();
        
        frappe.msgprint({
            title: __('Update Request'),
            message: __('To maintain secure records, direct edits to Flat or Ownership details are disabled. <br><br>Please go to the <b>Maintenance</b> module and raise a ticket under the "Other" category to request an update to your flat details.'),
            indicator: 'blue',
            primary_action: {
                label: 'Go to Maintenance',
                action: function() {
                    window.location.href = '/resident/maintenance';
                }
            }
        });
    });

    // 2. Mobile Update Modal Elements & State Management
    const $modal = $('#modal-update-mobile');
    const $alert = $('#modal-otp-alert');
    const $stateRequest = $('#otp-state-request');
    const $stateVerify = $('#otp-state-verify');
    const $inputMobile = $('#input-new-mobile');
    const $inputOtp = $('#input-otp-code');
    const $btnSendOtp = $('#btn-send-otp');
    const $btnVerifyOtp = $('#btn-verify-otp');
    const $btnResendOtp = $('#btn-resend-otp');
    const $btnBack = $('#btn-back-to-request');
    const $displayMobile = $('#display-user-mobile');

    let currentPendingMobile = '';

    function showAlert(msg, type) {
        $alert.removeClass('d-none alert-success alert-danger alert-info alert-warning')
              .addClass('alert-' + (type || 'info'))
              .html(msg);
    }

    function hideAlert() {
        $alert.addClass('d-none').empty();
    }

    function showStateRequest() {
        hideAlert();
        $stateRequest.removeClass('d-none');
        $stateVerify.addClass('d-none');
        $inputOtp.val('');
    }

    function showStateVerify(msg) {
        $stateRequest.addClass('d-none');
        $stateVerify.removeClass('d-none');
        $inputOtp.val('').focus();
        if (msg) {
            showAlert(msg, 'success');
        } else {
            hideAlert();
        }
    }

    // Open Modal button
    $('#btn-open-edit-mobile').on('click', function(e) {
        e.preventDefault();
        showStateRequest();
        $inputMobile.val('');
        $modal.modal('show');
        setTimeout(() => $inputMobile.focus(), 300);
    });

    // Back to request state
    $btnBack.on('click', function(e) {
        e.preventDefault();
        showStateRequest();
        $inputMobile.focus();
    });

    // Send OTP Request
    function sendOtp(isResend) {
        const rawMobile = $inputMobile.val().trim();
        const cleanedMobile = rawMobile.replace(/\D/g, '');

        if (!cleanedMobile || cleanedMobile.length < 10) {
            showAlert('Please enter a valid 10-digit mobile number.', 'warning');
            $inputMobile.focus();
            return;
        }

        currentPendingMobile = cleanedMobile;
        const $targetBtn = isResend ? $btnResendOtp : $btnSendOtp;
        const origBtnText = $targetBtn.html();

        $targetBtn.prop('disabled', true).html('Sending OTP…');
        hideAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.send_mobile_update_otp',
            args: {
                new_mobile: currentPendingMobile
            },
            callback: function(r) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    showStateVerify(r.message.message || 'OTP sent successfully to your registered email.');
                }
            },
            error: function(err) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Failed to send OTP. Please try again.';
                showAlert(errMsg, 'danger');
            }
        });
    }

    $btnSendOtp.on('click', function(e) {
        e.preventDefault();
        sendOtp(false);
    });

    $btnResendOtp.on('click', function(e) {
        e.preventDefault();
        sendOtp(true);
    });

    // Allow Enter key to trigger send OTP in request state
    $inputMobile.on('keypress', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            sendOtp(false);
        }
    });

    // Verify OTP & Update Mobile
    function verifyAndUpdate() {
        const otpVal = $inputOtp.val().trim();

        if (!otpVal || otpVal.length !== 6) {
            showAlert('Please enter the 6-digit OTP code received in your email.', 'warning');
            $inputOtp.focus();
            return;
        }

        const origBtnText = $btnVerifyOtp.html();
        $btnVerifyOtp.prop('disabled', true).html('Verifying…');
        hideAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.verify_and_update_mobile',
            args: {
                new_mobile: currentPendingMobile,
                otp: otpVal
            },
            callback: function(r) {
                $btnVerifyOtp.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    const updatedMobile = r.message.mobile_no || currentPendingMobile;

                    // Update UI in profile card without full reload
                    $displayMobile.text(updatedMobile);

                    // Close modal and show success alert
                    $modal.modal('hide');

                    frappe.show_alert({
                        message: __('Mobile number updated successfully!'),
                        indicator: 'green'
                    }, 5);

                    frappe.msgprint({
                        title: __('Mobile Updated'),
                        indicator: 'green',
                        message: __('Your registered mobile number has been successfully updated to <b>{0}</b>.', [frappe.utils.escape_html(updatedMobile)])
                    });
                }
            },
            error: function(err) {
                $btnVerifyOtp.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Invalid OTP. Please check the code and try again.';
                showAlert(errMsg, 'danger');
            }
        });
    }

    $btnVerifyOtp.on('click', function(e) {
        e.preventDefault();
        verifyAndUpdate();
    });

    // Allow Enter key to trigger verify in verify state
    $inputOtp.on('keypress', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            verifyAndUpdate();
        }
    });
});
