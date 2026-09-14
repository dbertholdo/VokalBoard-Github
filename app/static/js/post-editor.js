/*
 * WordPress-style post editor ("what you see is what you get") —
 * see app/templates/admin_posts.html and app/richtext.py.
 *
 * It's a plain <div contenteditable>, formatted with document.execCommand
 * (enough for the commands a post needs: bold, italic, lists, link,
 * heading, text color/font, image placement) — no external library, so
 * there's no dependency on any CDN (the site's CSP only allows
 * script-src 'self').
 *
 * Before the <form> is submitted, the div's current HTML is copied into
 * the hidden <textarea name="body"> — the server ALWAYS sanitizes that
 * HTML again before saving (see app/richtext.py:sanitize_post_body), so
 * even if someone tampers with the HTML in the browser before submitting,
 * nothing beyond the allow-listed tags/attributes/style-properties survives.
 */
(function () {
    "use strict";

    function initPostEditor(root) {
        var editable = root.querySelector("[data-post-editor-area]");
        var hiddenField = root.querySelector("[data-post-editor-hidden]");
        var toolbar = root.querySelector("[data-post-editor-toolbar]");
        var imageInput = root.querySelector("[data-post-editor-image-input]");
        var colorField = root.querySelector("[data-post-editor-color]");
        var fontField = root.querySelector("[data-post-editor-font]");
        var uploadUrl = root.getAttribute("data-upload-url");
        var csrfToken = root.getAttribute("data-csrf-token");
        var form = root.closest("form");
        if (!editable || !hiddenField || !toolbar || !form) return;

        // Using <span style="..."> for color/font instead of the legacy
        // <font> tag — matches what app/richtext.py's sanitizer allows
        // (a "span" with a filtered "style" attribute).
        document.execCommand("styleWithCSS", false, true);

        // Pre-existing content (e.g. reopening a draft) — never used
        // here today (the form always starts empty), but leaves the
        // editor ready for future editing without touching this again.
        if (hiddenField.value) {
            editable.innerHTML = hiddenField.value;
        }

        function syncHiddenField() {
            hiddenField.value = editable.innerHTML;
        }

        editable.addEventListener("input", syncHiddenField);
        form.addEventListener("submit", syncHiddenField);

        // --- selection tracking, so a click on the color/font pickers
        // (which steals focus away from the editor) still applies to
        // whatever text was selected right before that click. ---
        var savedRange = null;
        function saveSelection() {
            var sel = window.getSelection();
            if (sel && sel.rangeCount > 0 && editable.contains(sel.anchorNode)) {
                savedRange = sel.getRangeAt(0);
            }
        }
        function restoreSelection() {
            if (!savedRange) return;
            var sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(savedRange);
        }
        editable.addEventListener("mouseup", saveSelection);
        editable.addEventListener("keyup", saveSelection);

        toolbar.addEventListener("click", function (event) {
            var button = event.target.closest("[data-cmd]");
            if (!button) return;
            event.preventDefault();
            editable.focus();

            var cmd = button.getAttribute("data-cmd");
            if (cmd === "insertImage") {
                imageInput.click();
                return;
            }
            if (cmd === "createLink") {
                var url = window.prompt("Link (https://…):", "https://");
                if (!url) return;
                document.execCommand("createLink", false, url);
                syncHiddenField();
                return;
            }
            if (cmd === "formatBlock") {
                document.execCommand("formatBlock", false, button.getAttribute("data-value"));
                syncHiddenField();
                return;
            }
            document.execCommand(cmd, false, null);
            syncHiddenField();
        });

        if (colorField) {
            colorField.addEventListener("input", function () {
                restoreSelection();
                editable.focus();
                document.execCommand("foreColor", false, colorField.value);
                syncHiddenField();
            });
        }

        if (fontField) {
            fontField.addEventListener("change", function () {
                restoreSelection();
                editable.focus();
                if (fontField.value) {
                    document.execCommand("fontName", false, fontField.value);
                } else {
                    document.execCommand("removeFormat", false, null);
                }
                syncHiddenField();
                fontField.selectedIndex = 0;
            });
        }

        // --- image upload (shared by the toolbar button, the file
        // input it triggers, and dropping a file onto the editor) ---
        function uploadAndInsert(file, atRange) {
            if (!file || !uploadUrl) return;
            var statusEl = root.querySelector("[data-post-editor-status]");
            if (statusEl) statusEl.textContent = "Uploading image…";

            var data = new FormData();
            data.append("image", file);

            fetch(uploadUrl, {
                method: "POST",
                body: data,
                headers: { "X-CSRF-Token": csrfToken },
            })
                .then(function (r) { return r.json().then(function (body) { return { ok: r.ok, body: body }; }); })
                .then(function (result) {
                    if (statusEl) statusEl.textContent = "";
                    if (!result.ok || !result.body.url) {
                        window.alert("Couldn't upload that image (unsupported format or file too large).");
                        return;
                    }
                    editable.focus();
                    if (atRange) {
                        var sel = window.getSelection();
                        sel.removeAllRanges();
                        sel.addRange(atRange);
                    }
                    document.execCommand("insertImage", false, result.body.url);
                    syncHiddenField();
                })
                .catch(function () {
                    if (statusEl) statusEl.textContent = "";
                    window.alert("Failed to upload the image. Please try again.");
                });
        }

        if (imageInput) {
            imageInput.addEventListener("change", function () {
                var file = imageInput.files && imageInput.files[0];
                imageInput.value = ""; // allows picking the same file again later
                uploadAndInsert(file, null);
            });
        }

        // --- drag-and-drop upload: dropping a file from the computer
        // lands and uploads it right where it's dropped. Dragging an
        // image that's ALREADY inside the post (to reposition it) is a
        // different kind of drag (no "Files" in dataTransfer.types) —
        // that one is left alone so the browser's own contenteditable
        // drag-and-drop moves it natively, instead of being hijacked here. ---
        function isFileDrag(event) {
            return event.dataTransfer && Array.prototype.indexOf.call(event.dataTransfer.types || [], "Files") !== -1;
        }
        function caretRangeAt(x, y) {
            if (document.caretRangeFromPoint) return document.caretRangeFromPoint(x, y);
            if (document.caretPositionFromPoint) {
                var pos = document.caretPositionFromPoint(x, y);
                if (!pos) return null;
                var range = document.createRange();
                range.setStart(pos.offsetNode, pos.offset);
                range.collapse(true);
                return range;
            }
            return null;
        }

        editable.addEventListener("dragover", function (event) {
            if (!isFileDrag(event)) return; // let native image-move drags pass through untouched
            event.preventDefault();
            editable.classList.add("is-drag-over");
        });
        editable.addEventListener("dragleave", function (event) {
            if (event.target === editable) editable.classList.remove("is-drag-over");
        });
        editable.addEventListener("drop", function (event) {
            if (!isFileDrag(event)) return;
            event.preventDefault();
            editable.classList.remove("is-drag-over");
            var file = event.dataTransfer.files && event.dataTransfer.files[0];
            if (!file || file.type.indexOf("image/") !== 0) return;
            var range = caretRangeAt(event.clientX, event.clientY);
            uploadAndInsert(file, range);
        });

        // --- click an inserted image to align it (left/center/right)
        // via a small floating toolbar; dragging it (native browser
        // behavior for <img> inside contenteditable) moves it to a
        // different spot in the text. ---
        var imageToolbar = document.createElement("div");
        imageToolbar.className = "post-editor-image-toolbar";
        imageToolbar.hidden = true;
        imageToolbar.innerHTML =
            '<button type="button" data-align="align-left" title="Align left">⟸</button>' +
            '<button type="button" data-align="align-center" title="Center">⟺</button>' +
            '<button type="button" data-align="align-right" title="Align right">⟹</button>' +
            '<button type="button" data-align="" title="Reset">✕</button>';
        document.body.appendChild(imageToolbar);

        var activeImage = null;
        function positionImageToolbar(img) {
            var rect = img.getBoundingClientRect();
            imageToolbar.style.left = Math.max(4, rect.left) + "px";
            imageToolbar.style.top = Math.max(4, rect.top - 36) + "px";
            imageToolbar.hidden = false;
        }
        function refreshImageToolbarState() {
            var buttons = imageToolbar.querySelectorAll("[data-align]");
            for (var i = 0; i < buttons.length; i++) {
                var align = buttons[i].getAttribute("data-align");
                var isActive = align && activeImage && activeImage.classList.contains(align);
                buttons[i].classList.toggle("is-active", !!isActive);
            }
        }
        function hideImageToolbar() {
            imageToolbar.hidden = true;
            activeImage = null;
        }

        editable.addEventListener("click", function (event) {
            var img = event.target.closest && event.target.closest("img");
            if (img && editable.contains(img)) {
                activeImage = img;
                positionImageToolbar(img);
                refreshImageToolbarState();
            } else {
                hideImageToolbar();
            }
        });

        imageToolbar.addEventListener("click", function (event) {
            var button = event.target.closest("[data-align]");
            if (!button || !activeImage) return;
            event.preventDefault();
            activeImage.classList.remove("align-left", "align-center", "align-right");
            var align = button.getAttribute("data-align");
            if (align) activeImage.classList.add(align);
            positionImageToolbar(activeImage);
            refreshImageToolbarState();
            syncHiddenField();
        });

        // Keep the floating toolbar glued to the image while the page
        // scrolls, and dismiss it once the user clicks/types elsewhere.
        window.addEventListener("scroll", function () {
            if (activeImage && !imageToolbar.hidden) positionImageToolbar(activeImage);
        }, true);
        document.addEventListener("click", function (event) {
            if (event.target === imageToolbar || imageToolbar.contains(event.target)) return;
            if (event.target.closest && event.target.closest("img") && editable.contains(event.target)) return;
            hideImageToolbar();
        });
        editable.addEventListener("dragend", function () {
            // Native drag of an image within the editor just ended —
            // its position (and our hidden field) needs to catch up.
            syncHiddenField();
            hideImageToolbar();
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        var editors = document.querySelectorAll("[data-post-editor]");
        for (var i = 0; i < editors.length; i++) initPostEditor(editors[i]);
    });
})();
