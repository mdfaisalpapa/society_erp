frappe.ready(function () {
    const API = 'society_erp.society_erp.doctype.voting_poll.voting_api';

    const state = {
        polls: [],
        poll: null,
        selectedOption: null,
        pendingKey: null,
        submitting: false
    };

    const $ = (selector) => document.querySelector(selector);

    const el = {
        alert: $('#voting-alert'),
        loading: $('#voting-loading'),
        empty: $('#voting-empty'),
        list: $('#voting-poll-list'),
        panel: $('#voting-detail-panel'),
        title: $('#voting-detail-title'),
        meta: $('#voting-detail-meta'),
        description: $('#voting-detail-description'),
        flat: $('#voting-flat-select'),
        already: $('#voting-already-voted'),
        choiceArea: $('#voting-choice-area'),
        options: $('#voting-options'),
        submit: $('#voting-submit'),
        receipt: $('#voting-receipt'),
        confirmArea: $('#voting-confirm-area'),
        confirmText: $('#voting-confirm-text'),
        confirmSubmit: $('#voting-confirm-submit'),
        cancelSubmit: $('#voting-cancel-submit'),
        registerList: $('#published-register-list'),
        registerDetail: $('#published-register-detail'),
        registerTitle: $('#published-register-title'),
        registerMeta: $('#published-register-meta'),
        registerHash: $('#published-register-hash'),
        registerRows: $('#published-register-rows'),
        registerDownload: $('#published-register-download')
    };

    function showAlert(message, type = 'danger') {
        el.alert.className = `alert alert-${type}`;
        el.alert.textContent = message;
    }

    function clearAlert() {
        el.alert.classList.add('d-none');
        el.alert.textContent = '';
    }

    function call(method, args = {}) {
        return new Promise((resolve, reject) => {
            frappe.call({
                method: `${API}.${method}`,
                args,
                callback: (r) => {
                    if (r && !r.exc) {
                        resolve(r.message);
                    } else {
                        reject(new Error(
                            (r && r.message) || 'The request could not be completed.'
                        ));
                    }
                },
                error: (r) => {
                    reject(new Error(
                        (r && r.message) || 'Unable to contact the server.'
                    ));
                }
            });
        });
    }

    function formatDate(value) {
        if (!value) return 'Not specified';

        const date = new Date(String(value).replace(' ', 'T'));

        return Number.isNaN(date.getTime())
            ? value
            : date.toLocaleString();
    }

    function make(tag, className, text) {
        const node = document.createElement(tag);

        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;

        return node;
    }

    function renderSafeDescription(source) {
        const allowed = new Set([
            'P', 'DIV', 'BR', 'STRONG', 'B', 'EM', 'I',
            'U', 'UL', 'OL', 'LI', 'H1', 'H2', 'H3',
            'H4', 'BLOCKQUOTE'
        ]);

        const parsed = new DOMParser().parseFromString(
            String(source || ''),
            'text/html'
        );

        function copyNode(node) {
            if (node.nodeType === Node.TEXT_NODE) {
                return document.createTextNode(node.nodeValue || '');
            }

            if (node.nodeType !== Node.ELEMENT_NODE) {
                return document.createDocumentFragment();
            }

            if (!allowed.has(node.tagName)) {
                const fragment = document.createDocumentFragment();

                Array.from(node.childNodes).forEach(child => {
                    fragment.append(copyNode(child));
                });

                return fragment;
            }

            const clean = document.createElement(
                node.tagName.toLowerCase()
            );

            Array.from(node.childNodes).forEach(child => {
                clean.append(copyNode(child));
            });

            return clean;
        }

        el.description.replaceChildren();

        Array.from(parsed.body.childNodes).forEach(node => {
            el.description.append(copyNode(node));
        });
    }

    // --------------------------------------------------
    // Idempotency key
    // --------------------------------------------------

    function idempotencyStorageKey() {
        return `resident-vote:${state.poll.name}:${el.flat.value}:${state.selectedOption}`;
    }

    function getIdempotencyKey() {
        const storageKey = idempotencyStorageKey();

        let key = sessionStorage.getItem(storageKey);

        if (!key) {
            if (window.crypto && crypto.randomUUID) {
                key = crypto.randomUUID().replace(/-/g, '');
            } else {
                const bytes = new Uint8Array(32);

                crypto.getRandomValues(bytes);

                key = Array.from(bytes, b =>
                    b.toString(16).padStart(2, '0')
                ).join('');
            }

            sessionStorage.setItem(storageKey, key);
        }

        return key;
    }

    // --------------------------------------------------
    // Poll list
    // --------------------------------------------------

    function renderPolls() {
        el.list.replaceChildren();

        el.empty.classList.toggle(
            'd-none',
            state.polls.length !== 0
        );

        state.polls.forEach(poll => {
            const col = make('div', 'col-md-6 col-lg-4 mb-3');
            const card = make('div', 'card shadow-sm voting-poll-card');
            const body = make('div', 'card-body d-flex flex-column');

            body.append(
                make('h5', 'card-title', poll.title || poll.name)
            );

            body.append(
                make(
                    'span',
                    'badge badge-primary align-self-start mb-2',
                    poll.poll_type || 'Poll'
                )
            );

            body.append(
                make(
                    'p',
                    'small text-muted mb-2',
                    `Closes: ${formatDate(poll.end_datetime)}`
                )
            );

            body.append(
                make(
                    'p',
                    'small mb-3',
                    `${poll.voted_flat_count || 0} of ${poll.eligible_flat_count || 0} eligible flat(s) have voted`
                )
            );

            const button = make(
                'button',
                'btn btn-outline-primary btn-sm mt-auto',
                'View Poll'
            );

            button.type = 'button';

            button.addEventListener('click', () => {
                openPoll(poll.name);
            });

            body.append(button);
            card.append(body);
            col.append(card);
            el.list.append(col);
        });
    }

    // --------------------------------------------------
    // Published ballot registers
    // --------------------------------------------------

    async function loadPublishedRegisters() {
        try {
            const registers =
                await call('get_published_ballot_registers') || [];

            el.registerList.replaceChildren();

            if (!registers.length) {
                el.registerList.append(
                    make(
                        'p',
                        'text-muted small',
                        'No ballot registers have been published yet.'
                    )
                );

                return;
            }

            registers.forEach(item => {
                const col = make('div', 'col-md-6 col-lg-4 mb-2');
                const card = make('div', 'card h-100');
                const body = make('div', 'card-body');

                body.append(
                    make(
                        'h6',
                        'mb-1',
                        item.poll_title || item.name
                    )
                );

                body.append(
                    make(
                        'div',
                        'small text-muted mb-2',
                        `${item.name} · Published ${formatDate(item.published_on)} · ${item.ballot_count} ballot(s)`
                    )
                );

                const button = make(
                    'button',
                    'btn btn-outline-primary btn-sm',
                    'View Published Register'
                );

                button.type = 'button';

                button.addEventListener('click', () => {
                    openPublishedRegister(item.name);
                });

                body.append(button);
                card.append(body);
                col.append(card);
                el.registerList.append(col);
            });

        } catch (error) {
            el.registerList.replaceChildren(
                make(
                    'p',
                    'text-muted small',
                    'Published registers could not be loaded.'
                )
            );
        }
    }

    async function openPublishedRegister(name) {
        clearAlert();

        try {
            const data = await call(
                'get_published_ballot_register',
                { poll_name: name }
            );

            el.registerTitle.textContent =
                data.poll_title || data.poll;

            el.registerMeta.textContent =
                `${data.poll} · Published ${formatDate(data.published_on)} · ${data.ballot_count} ballot(s)`;

            el.registerHash.textContent =
                data.register_hash || '';

            el.registerRows.replaceChildren();

            (data.ballots || []).forEach(ballot => {
                const tr = document.createElement('tr');

                [
                    ballot.receipt_code,
                    ballot.selected_option_label,
                    Number(ballot.voting_weight || 0).toFixed(3),
                    ballot.ballot_hash
                ].forEach(value => {
                    const td = document.createElement('td');

                    td.textContent =
                        value == null ? '' : String(value);

                    if (String(value || '').length > 30) {
                        td.classList.add('voting-receipt-code');
                    }

                    tr.append(td);
                });

                el.registerRows.append(tr);
            });

            el.registerDownload.href =
                `/api/method/${API}.download_published_ballot_register?poll_name=${encodeURIComponent(name)}`;

            el.registerDownload.textContent = 'Download CSV';

            const oldPdfLink =
                el.registerDownload.nextElementSibling;

            if (
                oldPdfLink &&
                oldPdfLink.dataset.registerPdf === '1'
            ) {
                oldPdfLink.remove();
            }

            const pdfLink = document.createElement('a');

            pdfLink.dataset.registerPdf = '1';

            pdfLink.href =
                `/api/method/${API}.download_published_ballot_register_pdf?poll_name=${encodeURIComponent(name)}`;

            pdfLink.className =
                'btn btn-outline-secondary btn-sm ml-2';

            pdfLink.textContent = 'Download PDF';

            el.registerDownload.after(pdfLink);

            el.registerDetail.classList.remove('d-none');
            el.registerList.classList.add('d-none');

        } catch (error) {
            showAlert(error.message);
        }
    }

    // --------------------------------------------------
    // Load polls
    // --------------------------------------------------

    async function loadPolls() {
        clearAlert();

        el.loading.classList.remove('d-none');
        el.empty.classList.add('d-none');

        try {
            state.polls =
                await call('get_resident_polls') || [];

            renderPolls();

            await loadPublishedRegisters();

        } catch (error) {
            showAlert(error.message);

        } finally {
            el.loading.classList.add('d-none');
        }
    }

    // --------------------------------------------------
    // Open poll
    // --------------------------------------------------

    async function openPoll(name) {
        clearAlert();

        el.panel.classList.add('d-none');
        el.list.classList.add('d-none');

        try {
            state.poll = await call(
                'get_resident_poll_details',
                { poll_name: name }
            );

            state.selectedOption = null;
            state.pendingKey = null;

            renderDetails();

            el.panel.classList.remove('d-none');

            window.scrollTo({
                top:
                    el.panel.getBoundingClientRect().top +
                    window.scrollY - 20,
                behavior: 'smooth'
            });

        } catch (error) {
            el.list.classList.remove('d-none');
            showAlert(error.message);
        }
    }

    function renderDetails() {
        const poll = state.poll;

        el.title.textContent =
            poll.title || poll.name;

        el.meta.textContent =
            `${poll.poll_type} · Closes ${formatDate(poll.end_datetime)}`;

        renderSafeDescription(poll.description || '');

        el.flat.replaceChildren();

        (poll.eligible_flats || []).forEach(row => {
            const option = make('option', '', row.flat);

            option.value = row.flat;

            el.flat.append(option);
        });

        el.options.replaceChildren();

        (poll.options || []).forEach(option => {
            const label = make(
                'label',
                'list-group-item voting-option'
            );

            const radio = document.createElement('input');

            radio.type = 'radio';
            radio.name = 'voting-choice';
            radio.value = option.name;

            radio.addEventListener('change', () => {
                state.selectedOption = option.name;

                el.submit.disabled = false;
                el.confirmArea.classList.add('d-none');
            });

            label.append(
                radio,
                document.createTextNode(
                    option.label || option.name
                )
            );

            if (option.description) {
                label.append(
                    make(
                        'small',
                        'text-muted voting-option-description',
                        option.description
                    )
                );
            }

            el.options.append(label);
        });

        el.receipt.classList.add('d-none');
        el.confirmArea.classList.add('d-none');

        el.confirmSubmit.classList.remove('d-none');

        const oldOtp =
            el.confirmText.nextElementSibling;

        if (oldOtp && oldOtp.dataset.otpEntry === '1') {
            oldOtp.remove();
        }

        updateFlatState();
    }

    // --------------------------------------------------
    // Flat selection
    // --------------------------------------------------

    function updateFlatState() {
        const row = (state.poll.eligible_flats || []).find(
            item => item.flat === el.flat.value
        );

        const voted = !!(row && row.has_voted);

        el.already.classList.toggle('d-none', !voted);

        el.already.textContent = voted
            ? `A vote has already been recorded for ${row.flat}.`
            : '';

        el.choiceArea.classList.toggle('d-none', voted);

        el.submit.disabled =
            voted || !state.selectedOption;

        el.confirmArea.classList.add('d-none');
        el.receipt.classList.add('d-none');

        state.selectedOption = null;

        document.querySelectorAll(
            'input[name="voting-choice"]'
        ).forEach(radio => {
            radio.checked = false;
        });
    }

    el.flat.addEventListener('change', updateFlatState);

    el.submit.addEventListener('click', () => {
        if (!state.selectedOption || !el.flat.value) {
            return;
        }

        const selected = (state.poll.options || []).find(
            option => option.name === state.selectedOption
        );

        el.confirmText.textContent =
            `You are voting for flat ${el.flat.value}. Your selection is “${selected ? selected.label : ''}”.`;

        el.confirmArea.classList.remove('d-none');
    });

    el.cancelSubmit.addEventListener('click', () => {
        el.confirmArea.classList.add('d-none');
    });

    // --------------------------------------------------
    // Cast vote
    // --------------------------------------------------

    async function castSelectedVote() {
        const result = await call('cast_vote', {
            poll_name: state.poll.name,
            flat: el.flat.value,
            selected_option: state.selectedOption,
            idempotency_key: getIdempotencyKey()
        });

        if (!result || !result.success) {
            throw new Error(
                'The server did not confirm the vote.'
            );
        }

        sessionStorage.removeItem(idempotencyStorageKey());

        el.confirmArea.classList.add('d-none');
        el.choiceArea.classList.add('d-none');
        el.already.classList.add('d-none');
        el.receipt.classList.remove('d-none');

        const receiptHeading = make(
            'strong',
            '',
            result.recovered
                ? 'Your previously recorded vote was recovered.'
                : 'Your vote has been recorded.'
        );

        const receiptDetails = make('div', 'mt-2');

        [
            ['Poll', result.poll_title || result.poll_name],
            ['Flat', result.flat],
            ['Selected option', result.selected_option_label],
            ['Voting weight', Number(result.voting_weight || 0).toFixed(3)],
            ['Receipt code', result.receipt_code],
            ['SHA-256 ballot hash', result.ballot_hash],
            ['Date and time', formatDate(result.cast_on)]
        ].forEach(([label, value]) => {
            const line = make('div', 'mt-1');

            line.append(
                make('strong', '', `${label}: `),
                document.createTextNode(
                    value == null ? '' : String(value)
                )
            );

            if (
                label === 'Receipt code' ||
                label === 'SHA-256 ballot hash'
            ) {
                line.classList.add('voting-receipt-code');
            }

            receiptDetails.append(line);
        });

        const note = make(
            'small',
            'd-block text-muted mt-3',
            'Your vote has been recorded. Retain this receipt code. After the Association publishes the anonymous ballot register, you can use the code to locate your ballot.'
        );

        el.receipt.replaceChildren(
            receiptHeading,
            receiptDetails,
            note
        );

        const row = (state.poll.eligible_flats || []).find(
            item => item.flat === result.flat
        );

        if (row) {
            row.has_voted = true;
        }

        await loadPolls();
    }

    // --------------------------------------------------
    // Email OTP entry
    // --------------------------------------------------

    function showOtpEntry() {
        const wrap = make('div', 'mt-3');

        wrap.dataset.otpEntry = '1';

        wrap.append(
            make(
                'p',
                'small mb-2',
                'Enter the six-digit OTP sent to your registered email address.'
            )
        );

        const input = make('input', 'form-control mb-2');

        input.type = 'text';
        input.inputMode = 'numeric';
        input.autocomplete = 'one-time-code';
        input.maxLength = 6;
        input.placeholder = 'Six-digit OTP';

        input.setAttribute(
            'aria-label',
            'Six-digit email OTP'
        );

        const verify = make(
            'button',
            'btn btn-primary btn-sm',
            'Verify OTP and Cast Vote'
        );

        verify.type = 'button';

        verify.addEventListener('click', async () => {
            const otp = input.value.trim();

            if (!/^\d{6}$/.test(otp)) {
                showAlert(
                    'Enter the six-digit OTP.',
                    'warning'
                );

                return;
            }

            verify.disabled = true;
            verify.textContent = 'Verifying…';

            clearAlert();

            try {
                await call('verify_voting_otp', {
                    poll_name: state.poll.name,
                    flat: el.flat.value,
                    otp: otp
                });

                verify.textContent = 'Casting vote…';

                await castSelectedVote();

            } catch (error) {
                showAlert(error.message);

                verify.disabled = false;
                verify.textContent = 'Verify OTP and Cast Vote';

                input.focus();
            }
        });

        wrap.append(input, verify);

        el.confirmText.after(wrap);

        input.focus();
    }

    // --------------------------------------------------
    // Confirm vote / send OTP
    // --------------------------------------------------

    el.confirmSubmit.addEventListener('click', async () => {
        if (
            state.submitting ||
            !state.selectedOption ||
            !el.flat.value
        ) {
            return;
        }

        state.submitting = true;

        el.confirmSubmit.disabled = true;
        el.confirmSubmit.textContent = 'Please wait…';

        clearAlert();

        try {
            if (state.poll.require_email_otp) {
                await call('send_voting_otp', {
                    poll_name: state.poll.name,
                    flat: el.flat.value
                });

                showOtpEntry();

                el.confirmSubmit.classList.add('d-none');

            } else {
                el.confirmSubmit.textContent = 'Submitting…';

                await castSelectedVote();
            }

        } catch (error) {
            showAlert(error.message);

        } finally {
            state.submitting = false;

            el.confirmSubmit.disabled = false;

            if (
                !el.confirmSubmit.classList.contains('d-none')
            ) {
                el.confirmSubmit.textContent = 'Confirm Vote';
            }
        }
    });

    // --------------------------------------------------
    // Back buttons
    // --------------------------------------------------

    $('#voting-back-button').addEventListener('click', () => {
        el.panel.classList.add('d-none');
        el.list.classList.remove('d-none');

        clearAlert();

        loadPolls();
    });

    $('#published-register-back').addEventListener('click', () => {
        el.registerDetail.classList.add('d-none');
        el.registerList.classList.remove('d-none');
    });

    // --------------------------------------------------
    // Initialise
    // --------------------------------------------------

    loadPolls();
});
