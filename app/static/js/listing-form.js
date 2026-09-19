// Conditional requirements shared by creation and editing of listings.
(() => {
    const typeSelect = document.getElementById('listing-type-select');
    if (!typeSelect) return;
    const jobFields = document.getElementById('job-fields');
    const feeRequiredHelp = document.getElementById('fee-required-help');
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
        // P3.E: fee is "exactly one of amount/negotiable", not a plain
        // required text field anymore — the server validates that
        // combination (see app.fees.fee_valid); here we just show/hide
        // the hint, matching the same isJob condition as before.
        if (feeRequiredHelp) feeRequiredHelp.hidden = !isJob;
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

    // P3.A: the vacancy list (multiple naipes/quotas/fee) only makes
    // sense for "seeking_singer" listings.
    const vacanciesSection = document.getElementById('vacancies-section');
    function updateVacanciesVisible() {
        if (!vacanciesSection) return;
        vacanciesSection.hidden = typeSelect.value !== 'seeking_singer';
    }
    typeSelect.addEventListener('change', updateVacanciesVisible);
    updateVacanciesVisible();

    // "Add another voice" reveals the next hidden vacancy row instead of
    // building new DOM — same progressive-reveal idea as the spoken
    // languages fields on /profile, just per-listing instead of per-person.
    const addVacancyButton = document.getElementById('add-vacancy-row');
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
})();
