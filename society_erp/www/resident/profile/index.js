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
                    if (r.message.wa_link) {
                        $('#btn-wa-verify').attr('href', r.message.wa_link);
                    }
                    if (r.message.tg_link) {
                        $('#btn-tg-verify').attr('href', r.message.tg_link);
                    }
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
                        title: __('Mobile Number Changed'),
                        indicator: 'blue',
                        message: __('Your registered mobile number has been updated to <b>{0}</b>.<br><br>Please complete 1-click verification via WhatsApp or Telegram bot to verify and activate it.', [frappe.utils.escape_html(updatedMobile)])
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

    // Auto-open modal if requested via URL param (e.g. from Telegram bot WebApp)
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('modal') === 'update_mobile' || urlParams.get('open_modal') === 'update_mobile') {
        setTimeout(function() {
            showStateRequest();
            $inputMobile.val('');
            $modal.modal('show');
            setTimeout(() => $inputMobile.focus(), 300);
        }, 350);
    }

    // 3. Email Update Modal Elements & State Management
    const $emailModal = $('#modal-update-email');
    const $emailAlert = $('#modal-email-otp-alert');
    const $emailStateRequest = $('#email-otp-state-request');
    const $emailStateVerify = $('#email-otp-state-verify');
    const $inputEmail = $('#input-new-email');
    const $inputEmailOtp = $('#input-email-otp-code');
    const $btnSendEmailOtp = $('#btn-send-email-otp');
    const $btnVerifyEmailOtp = $('#btn-verify-email-otp');
    const $btnResendEmailOtp = $('#btn-resend-email-otp');
    const $btnBackEmail = $('#btn-back-to-email-request');
    const $displayEmail = $('#display-user-email');
    const $spanTargetNewEmail = $('#span-target-new-email');

    let currentPendingEmail = '';

    function showEmailAlert(msg, type) {
        $emailAlert.removeClass('d-none alert-success alert-danger alert-info alert-warning')
                   .addClass('alert-' + (type || 'info'))
                   .html(msg);
    }

    function hideEmailAlert() {
        $emailAlert.addClass('d-none').empty();
    }

    function showEmailStateRequest() {
        hideEmailAlert();
        $emailStateRequest.removeClass('d-none');
        $emailStateVerify.addClass('d-none');
        $inputEmailOtp.val('');
    }

    function showEmailStateVerify(msg) {
        $emailStateRequest.addClass('d-none');
        $emailStateVerify.removeClass('d-none');
        $spanTargetNewEmail.text(currentPendingEmail);
        $inputEmailOtp.val('').focus();
        if (msg) {
            showEmailAlert(msg, 'success');
        } else {
            hideEmailAlert();
        }
    }

    $('#btn-open-edit-email').on('click', function(e) {
        e.preventDefault();
        showEmailStateRequest();
        $inputEmail.val('');
        $emailModal.modal('show');
        setTimeout(() => $inputEmail.focus(), 300);
    });

    $btnBackEmail.on('click', function(e) {
        e.preventDefault();
        showEmailStateRequest();
        $inputEmail.focus();
    });

    function sendEmailOtp(isResend) {
        const rawEmail = $inputEmail.val().trim().toLowerCase();
        if (!rawEmail || !rawEmail.includes('@') || !rawEmail.includes('.')) {
            showEmailAlert('Please enter a valid email address.', 'warning');
            $inputEmail.focus();
            return;
        }

        currentPendingEmail = rawEmail;
        const $targetBtn = isResend ? $btnResendEmailOtp : $btnSendEmailOtp;
        const origBtnText = $targetBtn.html();

        $targetBtn.prop('disabled', true).html('Sending Code…');
        hideEmailAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.send_email_update_otp',
            args: {
                new_email: currentPendingEmail
            },
            callback: function(r) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    showEmailStateVerify(r.message.message);
                }
            },
            error: function(err) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Failed to send verification code. Please try again.';
                showEmailAlert(errMsg, 'danger');
            }
        });
    }

    $btnSendEmailOtp.on('click', function(e) {
        e.preventDefault();
        sendEmailOtp(false);
    });

    $btnResendEmailOtp.on('click', function(e) {
        e.preventDefault();
        sendEmailOtp(true);
    });

    function verifyAndUpdateEmail() {
        const otpVal = $inputEmailOtp.val().trim();
        if (!otpVal || otpVal.length < 6) {
            showEmailAlert('Please enter the full 6-digit verification code.', 'warning');
            $inputEmailOtp.focus();
            return;
        }

        const origBtnText = $btnVerifyEmailOtp.html();
        $btnVerifyEmailOtp.prop('disabled', true).html('Verifying…');
        hideEmailAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.verify_and_update_email',
            args: {
                new_email: currentPendingEmail,
                otp: otpVal
            },
            callback: function(r) {
                $btnVerifyEmailOtp.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    const updatedEmail = r.message.new_email || currentPendingEmail;
                    $displayEmail.text(updatedEmail);
                    $emailModal.modal('hide');

                    frappe.show_alert({
                        message: __('Email updated successfully!'),
                        indicator: 'green'
                    }, 5);

                    frappe.msgprint({
                        title: __('Email Updated'),
                        indicator: 'green',
                        message: __('Your registered email address has been successfully updated to <b>{0}</b>.', [frappe.utils.escape_html(updatedEmail)])
                    });
                }
            },
            error: function(err) {
                $btnVerifyEmailOtp.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Invalid code. Please check and try again.';
                showEmailAlert(errMsg, 'danger');
            }
        });
    }

    $btnVerifyEmailOtp.on('click', function(e) {
        e.preventDefault();
        verifyAndUpdateEmail();
    });

    $inputEmailOtp.on('keypress', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            verifyAndUpdateEmail();
        }
    });

    if (urlParams.get('modal') === 'update_email' || urlParams.get('open_modal') === 'update_email') {
        setTimeout(function() {
            showEmailStateRequest();
            $inputEmail.val('');
            $emailModal.modal('show');
            setTimeout(() => $inputEmail.focus(), 300);
        }, 350);
    }
});
