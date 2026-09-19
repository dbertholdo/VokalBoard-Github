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
            select.hidden = isConductor && isFirstRow;
        });
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
