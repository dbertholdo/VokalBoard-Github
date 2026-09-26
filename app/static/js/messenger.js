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
