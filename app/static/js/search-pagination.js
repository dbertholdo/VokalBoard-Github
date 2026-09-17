/* Shared progressive enhancement for board and people. No scripts from fetched HTML run. */
(() => {
    const form = document.querySelector('form[data-search-results]');
    if (!form) return;
    const results = document.getElementById(form.dataset.searchResults);
    const error = document.getElementById('search-error');
    let controller;
    let committedUrl = location.href;

    function restoreFilters(url) {
        const params = new URL(url).searchParams;
        form.dispatchEvent(new CustomEvent('search:restore', {detail: params}));
        for (const input of form.elements) {
            if (!input.name || input.disabled) continue;
            if (input.type === 'checkbox') input.checked = params.getAll(input.name).includes(input.value);
            else input.value = params.get(input.name) || '';
        }
    }

    async function load(url, fromHistory = false) {
        controller?.abort();
        const current = new AbortController();
        controller = current;
        const timeout = setTimeout(() => current.abort(), 15000);
        results.setAttribute('aria-busy', 'true');
        error.hidden = true;
        try {
            const response = await fetch(url, {signal: current.signal, credentials: 'same-origin'});
            if (!response.ok || response.redirected) throw new Error('Unexpected search response');
            const page = new DOMParser().parseFromString(await response.text(), 'text/html');
            const replacement = page.getElementById(results.id);
            if (!replacement) throw new Error('Missing results');
            if (controller !== current) return;
            results.replaceChildren(...replacement.childNodes);
            restoreFilters(url);
            if (!fromHistory && url !== location.href) history.pushState(null, '', url);
            committedUrl = url;
            results.focus({preventScroll: true});
            results.scrollIntoView({block: 'start', behavior: 'instant'});
        } catch (failure) {
            if (controller !== current) return;
            // Keep the existing results and their URL coherent, even if Back failed.
            if (fromHistory) history.replaceState(null, '', committedUrl);
            error.hidden = false;
            error.querySelector('a').href = url;
        } finally {
            clearTimeout(timeout);
            if (controller === current) results.removeAttribute('aria-busy');
        }
    }

    form.addEventListener('submit', event => {
        event.preventDefault();
        const url = new URL(form.action);
        url.search = new URLSearchParams(new FormData(form)).toString();
        url.searchParams.delete('page');
        load(url.href);
    });
    document.addEventListener('click', event => {
        const link = event.target.closest('a');
        if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey ||
            event.metaKey || event.shiftKey || event.altKey || link.target === '_blank') return;
        if (!(results.contains(link) && link.closest('.pagination')) &&
            !(form.contains(link) && link.classList.contains('clear-link'))) return;
        if (link.origin !== location.origin) return;
        event.preventDefault();
        load(link.href);
    });
    window.addEventListener('popstate', () => load(location.href, true));
})();
