// Conditional requirements shared by creation and editing of listings.
(() => {
    const typeSelect = document.getElementById('listing-type-select');
    if (!typeSelect) return;
    const jobFields = document.getElementById('job-fields');
    const repertoireInput = document.getElementById('repertoire-input');
    const help = document.getElementById('job-required-help');
    const genericLabels = document.querySelectorAll('.label-generic');
    const jobLabels = document.querySelectorAll('.label-job');
    const availability = document.getElementById('availability-fields');
    const eventField = document.getElementById('event-date-field');
    const locationFields = document.getElementById('listing-location');
    function updateLocationRequired() {
        const optional = typeSelect.value === 'singer_available';
        locationFields.querySelectorAll('[data-required-marker]').forEach(marker => {
            marker.hidden = optional;
        });
        locationFields.querySelectorAll('[name="state"], [name="city"]').forEach(input => {
            input.required = !optional && !input.disabled;
        });
    }
    function updateJobFields() {
        const isJob = ['seeking_singer', 'seeking_conductor'].includes(typeSelect.value);
        const isAvailable = typeSelect.value === 'singer_available';
        availability.hidden = !isAvailable;
        availability.disabled = !isAvailable;
        eventField.hidden = isAvailable;
        const eventDate = eventField.querySelector('input');
        eventDate.disabled = isAvailable;
        eventDate.required = isJob;
        updateLocationRequired();
        jobFields.hidden = false;
        jobFields.disabled = false;
        repertoireInput.required = isJob;
        help.hidden = !isJob;
        genericLabels.forEach(label => { label.hidden = isJob; });
        jobLabels.forEach(label => { label.hidden = !isJob; });
    }
    typeSelect.addEventListener('change', updateJobFields);

    // P3.E: top-level fee "a negociar" checkbox — disables the amount
    // field/currency select and clears any typed amount, so the two
    // never get submitted set together (mirrors app.fees.fee_valid's
    // "exactly one of the two" rule client-side, before the server
    // ever sees it).
    const feeNegotiableCheckbox = document.getElementById('fee-negotiable-checkbox');
    const feeAmountInput = document.getElementById('fee-amount-input');
    const feeCurrencySelect = document.getElementById('fee-currency-select');
    if (feeNegotiableCheckbox && feeAmountInput && feeCurrencySelect) {
        feeNegotiableCheckbox.addEventListener('change', () => {
            feeAmountInput.disabled = feeNegotiableCheckbox.checked;
            feeCurrencySelect.disabled = feeNegotiableCheckbox.checked;
            if (feeNegotiableCheckbox.checked) feeAmountInput.value = '';
        });
    }
    locationFields.addEventListener('change', updateLocationRequired);
    locationFields.addEventListener('input', updateLocationRequired);
    locationFields.addEventListener('click', updateLocationRequired);
    const firstDate = availability.querySelector('[name="available_from"]');
    const lastDate = availability.querySelector('[name="available_until"]');
    function updateDateBounds() {
        lastDate.min = firstDate.value;
        if (!firstDate.value) { lastDate.removeAttribute('max'); return; }
        const end = new Date(firstDate.value + 'T00:00:00Z');
        end.setUTCDate(end.getUTCDate() + 29);
        lastDate.max = end.toISOString().slice(0, 10);
    }
    firstDate.addEventListener('change', updateDateBounds);
    updateDateBounds();

    // P3.A / FIX (19/09/2026, Daniel: "duas formas de adicionar vagas,
    // fica confuso, inclusive para o código e db") — the vacancy list
    // is now the ONLY place voice type/fee are entered for BOTH
    // seeking_singer and seeking_conductor (previously seeking_singer
    // only, and only as one of two redundant entry points). The
    // standalone top-level voice type field/fee section are the
    // mirror image: visible only when NOT is_job.
    const vacanciesSection = document.getElementById('vacancies-section');
    const voiceTypeStandaloneSection = document.getElementById('voice-type-standalone-section');
    const topLevelFeeSection = document.getElementById('top-level-fee-section');
    const addVacancyButton = document.getElementById('add-vacancy-row');
    const vacanciesRemoveHelp = document.getElementById('vacancies-remove-help');
    // A conductor vaga has no naipe — only row 0 applies, with its
    // voice select hidden (see listing_form.html's vacancy-row-
    // conductor-hide class on every row past the first, and
    // vacancy-voice-type-select on each row's own select).
    function updateVacanciesVisible() {
        const isJob = ['seeking_singer', 'seeking_conductor'].includes(typeSelect.value);
        const isConductor = typeSelect.value === 'seeking_conductor';
        if (vacanciesSection) vacanciesSection.hidden = !isJob;
        if (voiceTypeStandaloneSection) voiceTypeStandaloneSection.hidden = isJob;
        if (topLevelFeeSection) topLevelFeeSection.hidden = isJob;
        if (addVacancyButton) addVacancyButton.hidden = isConductor;
        if (vacanciesRemoveHelp) vacanciesRemoveHelp.hidden = isConductor;
        document.querySelectorAll('.vacancy-row-conductor-hide').forEach(row => {
            // Remembers each row's hidden state from BEFORE it was
            // forced hidden for conductor, so switching back to
            // seeking_singer restores whatever it was (an untouched
            // extra row stays hidden; a row that already had data —
            // editing an existing multi-voice listing — reappears).
            if (isConductor) {
                if (row.dataset.prevHidden === undefined) row.dataset.prevHidden = row.hidden ? '1' : '0';
                row.hidden = true;
            } else if (row.dataset.prevHidden !== undefined) {
                row.hidden = row.dataset.prevHidden === '1';
                delete row.dataset.prevHidden;
            }
        });
        document.querySelectorAll('.vacancy-voice-type-select').forEach(select => {
            const row = select.closest('.vacancy-row');
            const isFirstRow = row && !row.classList.contains('vacancy-row-conductor-hide');
            // Hide the whole labelled field (label text included), not just the select.
            (select.closest('.vacancy-field') || select).hidden = isConductor && isFirstRow;
        });
        // A conductor listing always has exactly one implicit vaga —
        // there's nothing to remove (mirrors add-vacancy-button/
        // vacanciesRemoveHelp being hidden for the same reason above).
        document.querySelectorAll('.vacancy-remove-btn').forEach(btn => { btn.hidden = isConductor; });
    }
    typeSelect.addEventListener('change', updateVacanciesVisible);
    updateVacanciesVisible();

    // "Add another voice" reveals the next hidden vacancy row instead of
    // building new DOM — same progressive-reveal idea as the spoken
    // languages fields on /profile, just per-listing instead of per-person.
    // Hidden entirely for seeking_conductor (see updateVacanciesVisible).
    if (addVacancyButton) {
        addVacancyButton.addEventListener('click', () => {
            const nextHidden = document.querySelector('.vacancy-row-extra[hidden]');
            if (nextHidden) {
                nextHidden.hidden = false;
            } else {
                addVacancyButton.disabled = true;
            }
        });
    }

    // Remove-vacancy button (19/09/2026, task #54, Daniel: "permitir
    // remover vaga/naipe já adicionado, não só adicionar") — replaces
    // the old "leave the field empty and save again" workaround.
    // Clears the row's own fields and hides it again (exactly the
    // "unused extra row" state "Add another voice" reveals), reusing
    // the backend's existing "rows with no voice type chosen are
    // skipped" logic (see parse_vacancies_form in app/vacancies.py) —
    // no new backend code needed, this button just does client-side
    // what the person used to have to do by hand. Always keeps at
    // least one visible row (a listing needs at least one vaga to
    // save at all — see _job_fields_valid in listings_routes.py), and
    // a row already locked (disabled — see listing_form.html: it has
    // a confirmed Match) never reaches this handler.
    document.addEventListener('click', (e) => {
        const removeBtn = e.target.closest('.vacancy-remove-btn');
        if (!removeBtn || removeBtn.disabled) return;
        const row = removeBtn.closest('.vacancy-row');
        if (!row) return;
        const visibleRows = Array.from(document.querySelectorAll('.vacancy-row')).filter(r => !r.hidden);
        if (visibleRows.length <= 1) return;
        row.querySelectorAll('select').forEach(select => { select.selectedIndex = 0; select.disabled = false; });
        row.querySelectorAll('input[type="text"], input[type="number"]').forEach(input => { input.value = ''; input.disabled = false; });
        row.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = false; });
        row.hidden = true;
        row.classList.add('vacancy-row-extra');
        if (addVacancyButton) addVacancyButton.disabled = false;
    });

    // P3.E: each vacancy row has its own "a negociar" checkbox — same
    // disable-the-amount-field behavior as the top-level fee, just
    // delegated (rows can be revealed later by "Add another voice",
    // see below, so a plain querySelectorAll at load time would miss them).
    document.addEventListener('change', (e) => {
        if (!e.target.classList || !e.target.classList.contains('vacancy-fee-negotiable')) return;
        const row = e.target.closest('.vacancy-row');
        if (!row) return;
        const amount = row.querySelector('.vacancy-fee-amount');
        const currency = row.querySelector('.vacancy-fee-currency');
        if (amount) { amount.disabled = e.target.checked; if (e.target.checked) amount.value = ''; }
        if (currency) currency.disabled = e.target.checked;
    });

    // Zero-Storage sheet music link: the URL field only makes sense
    // once "Partitur vorhanden" is checked.
    const sheetMusicToggle = document.getElementById('sheet-music-toggle');
    const sheetMusicUrlField = document.getElementById('sheet-music-url-field');
    if (sheetMusicToggle && sheetMusicUrlField) {
        sheetMusicToggle.addEventListener('change', () => {
            sheetMusicUrlField.hidden = !sheetMusicToggle.checked;
        });
    }

    updateJobFields();

    // Task #52 (Daniel: "aviso ao publicar anúncio sem Cachê/A
    // negociar") — a soft nudge, not a hard requirement: fee stays
    // fully optional server-side (parse_vacancies_form/fee_valid, see
    // app/fees.py and app/vacancies.py — it can always be added later),
    // but a listing published with no fee info anywhere gets fewer
    // applications, so we confirm() once before letting it through.
    // Checks the top-level fee fields for a self-ad listing
    // (singer_available/conductor_available) or every VISIBLE vacancy
    // row for a job listing (seeking_singer/seeking_conductor) — "any
    // one row has fee info" is enough to skip the warning, since a
    // multi-naipe listing only needs one clear vaga to look worth
    // opening.
    const listingForm = document.getElementById('listing-form');
    if (listingForm) {
        let feeWarningAcknowledged = false;
        listingForm.addEventListener('submit', (e) => {
            if (feeWarningAcknowledged) return;
            const isJob = ['seeking_singer', 'seeking_conductor'].includes(typeSelect.value);
            let hasFeeInfo;
            if (isJob) {
                const visibleRows = Array.from(document.querySelectorAll('.vacancy-row')).filter(row => !row.hidden);
                hasFeeInfo = visibleRows.some(row => {
                    const amount = row.querySelector('.vacancy-fee-amount');
                    const negotiable = row.querySelector('.vacancy-fee-negotiable');
                    return (amount && amount.value.trim() !== '') || (negotiable && negotiable.checked);
                });
            } else {
                hasFeeInfo = (feeAmountInput && feeAmountInput.value.trim() !== '')
                    || (feeNegotiableCheckbox && feeNegotiableCheckbox.checked);
            }
            if (hasFeeInfo) return;
            e.preventDefault();
            const message = listingForm.getAttribute('data-fee-warning');
            if (window.confirm(message)) {
                feeWarningAcknowledged = true;
                // Deferred: browsers ignore requestSubmit() while this submit
                // event is still being dispatched, so "OK" did nothing (26/09/2026).
                setTimeout(() => {
                    listingForm.requestSubmit ? listingForm.requestSubmit() : listingForm.submit();
                }, 0);
            }
        });
    }
})();
