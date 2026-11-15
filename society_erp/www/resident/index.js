frappe.ready(function() {
    // Resident Portal Dashboard Controller
    class ResidentDashboard {
        constructor() {
            this.setup_defaults();
            this.bind_events();
        }

        setup_defaults() {
            // Add any initialization logic here (e.g., setting up tooltips or UI states)
            console.log("Resident Portal Initialized");
        }

        bind_events() {
            // 1. Handle Logout explicitly if you add a .btn-logout class to your UI
            $('.btn-logout').on('click', (e) => {
                e.preventDefault();
                this.logout_user();
            });

            // 2. Example: Interactive button to acknowledge/dismiss a notice
            $('.acknowledge-notice-btn').on('click', (e) => {
                e.preventDefault();
                let $btn = $(e.currentTarget);
                let notice_id = $btn.data('notice-id');
                
                // Disable button to prevent double-clicks
                $btn.prop('disabled', true).text('Processing...');
                
                this.acknowledge_notice(notice_id, $btn);
            });
        }

        logout_user() {
            frappe.call({
                method: 'logout',
                callback: function(r) {
                    if (!r.exc) {
                        // Redirect to login page after successful logout
                        window.location.href = '/login';
                    } else {
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: __('Failed to log out. Please try again.')
                        });
                    }
                }
            });
        }

        acknowledge_notice(notice_id, $btn) {
            // Example custom API call (you would need to create this python method)
            frappe.call({
                method: 'society_erp.api.resident_portal.acknowledge_notice',
                args: {
                    notice_id: notice_id
                },
                callback: function(r) {
                    if (!r.exc && r.message) {
                        // Remove the notice from the UI dynamically with a fade effect
                        $btn.closest('.list-group-item').fadeOut(300, function() {
                            $(this).remove();
                        });
                        frappe.show_alert({message: __('Notice Acknowledged'), indicator: 'green'});
                    } else {
                        $btn.prop('disabled', false).text('Acknowledge');
                        frappe.msgprint(__('Something went wrong.'));
                    }
                }
            });
        }
    }

    // Global verification handlers
    window.sendEmailOTP = function() {
        const $btn = $('#btn-send-email-otp');
        $btn.prop('disabled', true).text('Sending...');
        frappe.call({
            method: 'society_erp.api.verification.send_email_verification_otp',
            callback: function(r) {
                $btn.prop('disabled', false).text('📩 Resend Code');
                if (!r.exc) {
                    $('#email-otp-box').slideDown();
                    $('#email-otp-status').text('Code sent! Check your inbox.');
                    frappe.show_alert({message: r.message.message || 'Verification code sent!', indicator: 'green'});
                }
            }
        });
    };

    window.submitEmailOTP = function() {
        const otp = $('#email-otp-input').val().trim();
        if (!otp || otp.length < 6) {
            frappe.msgprint(__('Please enter the complete 6-digit code.'));
            return;
        }
        frappe.call({
            method: 'society_erp.api.verification.verify_email_otp',
            args: { otp: otp },
            callback: function(r) {
                if (!r.exc && r.message && r.message.success) {
                    frappe.msgprint({
                        title: __('Verified'),
                        indicator: 'green',
                        message: __('Email verified successfully! Reloading portal...')
                    });
                    setTimeout(function() { window.location.reload(); }, 1200);
                }
            }
        });
    };

    // Initialize the dashboard scripts
    new ResidentDashboard();

    // Mobile Number Change Modal Handlers
    const $mobileModal = $('#modal-update-mobile');
    const $mobileAlert = $('#modal-otp-alert');
    const $stateRequest = $('#otp-state-request');
    const $stateVerify = $('#otp-state-verify');
    const $inputNewMobile = $('#input-new-mobile');
    const $btnSendMobileOtp = $('#btn-send-mobile-otp');
    const $btnResendMobileOtp = $('#btn-resend-mobile-otp');
    const $btnVerifyMobileOtp = $('#btn-verify-mobile-otp');
    const $btnBackToRequest = $('#btn-back-to-request');
    const $inputMobileOtp = $('#input-mobile-otp-code');
    const $btnWaVerify = $('#btn-wa-verify');
    const $btnTgVerify = $('#btn-tg-verify');

    let currentPendingMobile = '';

    function showMobileAlert(msg, type) {
        $mobileAlert
            .removeClass('d-none alert-success alert-danger alert-warning alert-info')
            .addClass('alert-' + (type || 'danger'))
            .text(msg);
    }

    function hideMobileAlert() {
        $mobileAlert.addClass('d-none').text('');
    }

    function resetMobileModal() {
        hideMobileAlert();
        $stateRequest.removeClass('d-none');
        $stateVerify.addClass('d-none');
        $inputNewMobile.val('');
        $inputMobileOtp.val('');
        currentPendingMobile = '';
    }

    $('#btn-open-change-mobile').on('click', function(e) {
        e.preventDefault();
        resetMobileModal();
        $mobileModal.modal('show');
        setTimeout(function() { $inputNewMobile.focus(); }, 350);
    });

    $btnBackToRequest.on('click', function(e) {
        e.preventDefault();
        hideMobileAlert();
        $stateVerify.addClass('d-none');
        $stateRequest.removeClass('d-none');
        $inputNewMobile.focus();
    });

    function sendMobileOtp(isResend) {
        const mobileVal = isResend ? currentPendingMobile : $inputNewMobile.val().trim();
        const cleaned = mobileVal.replace(/[\s\-\(\)\+]/g, '');

        if (!cleaned || (cleaned.length !== 10 && !(cleaned.length === 12 && cleaned.startsWith('91')))) {
            showMobileAlert('Please enter a valid 10-digit mobile number.', 'warning');
            $inputNewMobile.focus();
            return;
        }

        const $targetBtn = isResend ? $btnResendMobileOtp : $btnSendMobileOtp;
        const origBtnText = $targetBtn.html();
        $targetBtn.prop('disabled', true).html('Sending OTP…');
        hideMobileAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.send_mobile_update_otp',
            args: { new_mobile: mobileVal },
            callback: function(r) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    currentPendingMobile = r.message.new_mobile || mobileVal;
                    if (r.message.wa_link) $btnWaVerify.attr('href', r.message.wa_link);
                    if (r.message.tg_link) $btnTgVerify.attr('href', r.message.tg_link);

                    $stateRequest.addClass('d-none');
                    $stateVerify.removeClass('d-none');
                    showMobileAlert(r.message.message || 'OTP sent successfully to your registered email.', 'info');
                    setTimeout(function() { $inputMobileOtp.focus(); }, 300);
                }
            },
            error: function(err) {
                $targetBtn.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Failed to send OTP. Please try again.';
                showMobileAlert(errMsg, 'danger');
            }
        });
    }

    $btnSendMobileOtp.on('click', function(e) {
        e.preventDefault();
        sendMobileOtp(false);
    });

    $btnResendMobileOtp.on('click', function(e) {
        e.preventDefault();
        sendMobileOtp(true);
    });

    $inputNewMobile.on('keypress', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            sendMobileOtp(false);
        }
    });

    $btnVerifyMobileOtp.on('click', function(e) {
        e.preventDefault();
        const otpVal = $inputMobileOtp.val().trim();
        if (!otpVal || otpVal.length !== 6) {
            showMobileAlert('Please enter the 6-digit OTP code received in your email.', 'warning');
            $inputMobileOtp.focus();
            return;
        }

        const origBtnText = $btnVerifyMobileOtp.html();
        $btnVerifyMobileOtp.prop('disabled', true).html('Verifying…');
        hideMobileAlert();

        frappe.call({
            method: 'society_erp.www.resident.profile.index.verify_and_update_mobile',
            args: {
                new_mobile: currentPendingMobile,
                otp: otpVal
            },
            callback: function(r) {
                $btnVerifyMobileOtp.prop('disabled', false).html(origBtnText);
                if (r && r.message && r.message.status === 'success') {
                    const updatedMobile = r.message.mobile_no || currentPendingMobile;
                    $('#current-resident-mobile').text(updatedMobile);

                    // Update bot links on the page if present
                    if (r.message.whatsapp_verification_link) {
                        $('#link-verify-wa').attr('href', r.message.whatsapp_verification_link);
                    }
                    if (r.message.telegram_verification_link) {
                        $('#link-verify-tg').attr('href', r.message.telegram_verification_link);
                    }

                    $mobileModal.modal('hide');

                    frappe.msgprint({
                        title: __('Mobile Number Changed'),
                        indicator: 'blue',
                        message: __('Your registered mobile number has been changed to <b>{0}</b>.<br><br>As per security policy, please tap <b>Verify via WhatsApp</b> or <b>Telegram</b> to complete 1-click bot verification and unlock access.', [frappe.utils.escape_html(updatedMobile)])
                    });

                    setTimeout(function() { window.location.reload(); }, 2000);
                }
            },
            error: function(err) {
                $btnVerifyMobileOtp.prop('disabled', false).html(origBtnText);
                const errMsg = err && err.message ? err.message : 'Invalid or expired OTP. Please check and try again.';
                showMobileAlert(errMsg, 'danger');
            }
        });
    });

    $inputMobileOtp.on('keypress', function(e) {
        if (e.which === 13) {
            e.preventDefault();
            $btnVerifyMobileOtp.click();
        }
    });
});
