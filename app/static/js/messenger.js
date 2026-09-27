/*
 * Messenger live updates (docs/specs/MESSENGER.md, M4) — polling, never
 * WebSockets (Daniel, 2026-09-26: cheapest option).
 * - Unread badge: every 60 s, only while the tab is visible.
 * - Open thread (/messages/c/{id}): every 5 s, 30 s after 2 idle minutes,
 *   paused in background tabs.
 * Message text is always inserted with textContent (never as HTML).
 * Other scripts can listen for "vb:messages-summary" (the desktop bubble, M5).
 */
(function () {
    'use strict';
    var BADGE_EVERY = 60000, FAST = 5000, SLOW = 30000, IDLE_AFTER = 120000;

    function visible() { return document.visibilityState === 'visible'; }

    function updateBadges(total) {
        document.querySelectorAll('[data-messages-badge]').forEach(function (badge) {
            badge.textContent = total;
            badge.hidden = !total;
        });
    }

    function pollBadge() {
        if (!visible()) return;
        fetch('/messages/unread-count', { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (!data) return;
                updateBadges(data.total);
                document.dispatchEvent(new CustomEvent('vb:messages-summary', { detail: data }));
            })
            .catch(function () {});
    }
    setInterval(pollBadge, BADGE_EVERY);
    document.addEventListener('visibilitychange', function () { if (visible()) pollBadge(); });
    window.vbPollMessages = pollBadge;
    pollBadge();  // once on load, so the desktop bubble can appear right away

    // ---- Open conversation page ---------------------------------------
    var list = document.querySelector('.messenger-messages[data-conversation-id]');
    if (!list) return;
    var conversationId = list.dataset.conversationId;
    var aboutLabel = list.dataset.aboutLabel || '';
    var delay = FAST, lastNew = Date.now(), timer = null;
    list.scrollTop = list.scrollHeight;

    function renderMessage(msg) {
        var li = document.createElement('li');
        li.className = 'messenger-message ' + (msg.mine ? 'mine' : 'theirs');
        li.dataset.messageId = msg.id;
        if (msg.listing_title) {
            var context = document.createElement('span');
            context.className = 'messenger-context';
            context.textContent = aboutLabel + ': ' + msg.listing_title;
            li.appendChild(context);
        }
        var bubble = document.createElement('p');
        bubble.className = 'messenger-bubble';
        bubble.textContent = msg.body;
        li.appendChild(bubble);
        var time = document.createElement('span');
        time.className = 'messenger-time';
        time.textContent = msg.time;
        li.appendChild(time);
        list.appendChild(li);
    }

    function schedule() {
        if (!timer && visible()) timer = setTimeout(pollThread, delay);
    }

    function pollThread() {
        timer = null;
        fetch('/messages/c/' + conversationId + '/since?after=' + (list.dataset.lastId || 0), { credentials: 'same-origin' })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
                if (data && data.messages.length) {
                    data.messages.forEach(renderMessage);
                    list.dataset.lastId = data.messages[data.messages.length - 1].id;
                    list.scrollTop = list.scrollHeight;
                    lastNew = Date.now();
                    delay = FAST;
                } else if (Date.now() - lastNew > IDLE_AFTER) {
                    delay = SLOW;
                }
            })
            .catch(function () {})
            .then(schedule);
    }

    document.addEventListener('visibilitychange', function () {
        if (visible()) { delay = FAST; lastNew = Date.now(); schedule(); }
        else if (timer) { clearTimeout(timer); timer = null; }
    });
    schedule();
})();

/*
 * Desktop chat dock (M5, Daniel 2026-09-26): a small popup bubble appears on
 * a new message; clicking it opens a small chat window (bottom right) with
 * minimize and close buttons in its header — like Facebook. Up to 3 windows,
 * kept open across page loads (sessionStorage). Hidden below 1024 px (CSS);
 * phones use the Messages menu badge instead. Minimized windows only peek
 * (count new messages) and never mark anything as read.
 */
(function () {
    'use strict';
    var dock = document.getElementById('vb-chat-dock');
    if (!dock) return;
    var L = dock.dataset;
    var desktop = window.matchMedia('(min-width: 1024px)');
    var STORE = 'vbChatWindows', SEEN = 'vbChatBubbleSeen', FAST = 5000, SLOW = 30000, IDLE_AFTER = 120000;
    var windows = {};

    function load(key, fallback) {
        try { return JSON.parse(sessionStorage.getItem(key)) || fallback; } catch (e) { return fallback; }
    }
    function store(key, value) { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (e) {} }
    function save() {
        store(STORE, Object.keys(windows).map(function (id) { return { id: id, min: windows[id].minimized }; }));
    }
    function el(tag, cls, text) {
        var node = document.createElement(tag);
        if (cls) node.className = cls;
        if (text != null) node.textContent = text;
        return node;
    }
    function button(cls, text, label) {
        var b = el('button', cls, text);
        b.type = 'button';
        if (label) b.setAttribute('aria-label', label);
        return b;
    }

    function showBubble(latest) {
        if (!desktop.matches || windows[latest.conversation_id] || latest.id <= load(SEEN, 0)) return;
        store(SEEN, latest.id);
        var old = dock.querySelector('.chat-bubble');
        if (old) old.remove();
        var bubble = el('div', 'chat-bubble');
        bubble.setAttribute('role', 'status');
        var open = button('chat-bubble-open');
        open.appendChild(el('strong', null, (L.labelNew || '').replace('{name}', latest.sender_name)));
        open.appendChild(el('span', 'chat-bubble-snippet', latest.snippet));
        open.addEventListener('click', function () { bubble.remove(); openWindow(String(latest.conversation_id), false); });
        var close = button('chat-bubble-close', '×', L.labelClose);
        close.addEventListener('click', function () { bubble.remove(); });
        bubble.appendChild(open);
        bubble.appendChild(close);
        dock.appendChild(bubble);
    }

    function openWindow(id, minimized) {
        if (windows[id]) { setMinimized(id, false); return; }
        var ids = Object.keys(windows);
        if (ids.length >= 3) closeWindow(ids[0]);

        var win = el('section', 'chat-window');
        var header = el('header', 'chat-window-header');
        var title = el('a', 'chat-window-title', '…');
        title.href = '/messages/c/' + id;
        title.title = L.labelOpen;
        var badge = el('span', 'badge-count badge-alert');
        badge.hidden = true;
        var minimize = button('chat-window-btn', '–', L.labelMinimize);
        var close = button('chat-window-btn', '×', L.labelClose);
        header.appendChild(title);
        header.appendChild(badge);
        header.appendChild(minimize);
        header.appendChild(close);
        var list = el('ol', 'chat-window-messages');
        // Screen readers announce messages as they arrive.
        list.setAttribute('aria-live', 'polite');
        var form = el('form', 'chat-window-composer');
        var input = el('textarea');
        input.name = 'body';
        input.rows = 2;
        input.maxLength = 2000;
        input.placeholder = L.placeholder || '';
        input.setAttribute('aria-label', L.placeholder || '');
        var send = el('button', null, L.labelSend);
        send.type = 'submit';
        form.appendChild(input);
        form.appendChild(send);
        win.appendChild(header);
        win.appendChild(list);
        win.appendChild(form);
        dock.appendChild(win);

        var state = { el: win, list: list, title: title, badge: badge, minimize: minimize, lastId: 0, minimized: false,
                      timer: null, delay: FAST, lastNew: Date.now() };
        windows[id] = state;

        minimize.addEventListener('click', function (e) { e.stopPropagation(); setMinimized(id, !state.minimized); });
        close.addEventListener('click', function (e) { e.stopPropagation(); closeWindow(id); });
        header.addEventListener('click', function (e) { if (state.minimized && e.target !== title) setMinimized(id, false); });
        input.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
        });
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var body = input.value.trim();
            if (!body) return;
            send.disabled = true;
            fetch('/messages/c/' + id + '/post', {
                method: 'POST', credentials: 'same-origin',
                body: new URLSearchParams({ csrf_token: L.csrf, body: body })
            })
                .then(function (r) { return r.json(); })
                .then(function (res) {
                    if (res.status === 'sent' || res.status === 'request_sent') { input.value = ''; poll(id); }
                    else { showError(state); }
                })
                .catch(function () { showError(state); })
                .then(function () { send.disabled = false; });
        });

        setMinimized(id, !!minimized);
        save();
    }

    function showError(state) {
        state.list.appendChild(el('li', 'chat-window-error', L.labelError));
        state.list.scrollTop = state.list.scrollHeight;
    }

    function setMinimized(id, value) {
        var state = windows[id];
        state.minimized = value;
        state.el.classList.toggle('minimized', value);
        state.minimize.setAttribute('aria-expanded', String(!value));
        if (!value) {
            state.badge.hidden = true;
            state.delay = FAST;
            state.lastNew = Date.now();
        }
        schedule(id, 0);
        save();
    }

    function closeWindow(id) {
        var state = windows[id];
        if (!state) return;
        clearTimeout(state.timer);
        state.el.remove();
        delete windows[id];
        save();
    }

    function renderMessage(state, msg) {
        var li = el('li', 'chat-window-message ' + (msg.mine ? 'mine' : 'theirs'));
        li.appendChild(el('p', 'messenger-bubble', msg.body));
        li.appendChild(el('span', 'messenger-time', msg.time));
        state.list.appendChild(li);
    }

    function schedule(id, wait) {
        var state = windows[id];
        if (!state) return;
        clearTimeout(state.timer);
        state.timer = setTimeout(function () { poll(id); }, wait);
    }

    function poll(id) {
        var state = windows[id];
        if (!state) return;
        if (document.visibilityState !== 'visible') { schedule(id, state.delay); return; }
        var url = '/messages/c/' + id + '/since?after=' + state.lastId + (state.minimized ? '&peek=1' : '');
        fetch(url, { credentials: 'same-origin' })
            .then(function (r) {
                if (r.status === 404) { closeWindow(id); return null; }
                return r.ok ? r.json() : null;
            })
            .then(function (data) {
                if (!data || !windows[id]) return;
                state.title.textContent = data.other_name;
                state.el.setAttribute('aria-label', data.other_name);
                if (state.minimized) {
                    var fresh = data.messages.filter(function (m) { return !m.mine; }).length;
                    state.badge.textContent = fresh;
                    state.badge.hidden = !fresh;
                    state.delay = SLOW;
                } else if (data.messages.length) {
                    data.messages.forEach(function (m) { renderMessage(state, m); });
                    state.lastId = data.messages[data.messages.length - 1].id;
                    state.list.scrollTop = state.list.scrollHeight;
                    state.lastNew = Date.now();
                    state.delay = FAST;
                    if (window.vbPollMessages) window.vbPollMessages();
                } else if (Date.now() - state.lastNew > IDLE_AFTER) {
                    state.delay = SLOW;
                }
            })
            .catch(function () {})
            .then(function () { if (windows[id]) schedule(id, state.delay); });
    }

    document.addEventListener('vb:messages-summary', function (e) {
        if (e.detail && e.detail.latest) showBubble(e.detail.latest);
    });
    function restore() {
        load(STORE, []).forEach(function (w) { if (!windows[w.id]) openWindow(String(w.id), w.min); });
    }
    if (desktop.matches) restore();
    // A window that was narrow (or not yet laid out) at load restores its chats once it's wide.
    desktop.addEventListener('change', function (e) { if (e.matches) restore(); });
})();
