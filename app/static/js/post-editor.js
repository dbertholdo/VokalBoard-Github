/*
 * Editor de posts estilo WordPress ("o que você vê é o que sai") —
 * ver app/templates/admin_posts.html e app/richtext.py.
 *
 * É uma <div contenteditable> comum, formatada com document.execCommand
 * (suficiente pros comandos simples que o post precisa: negrito,
 * itálico, listas, link, título) — nada de biblioteca externa, pra não
 * depender de CDN nenhum (o CSP do site só libera script-src 'self').
 *
 * Antes do <form> ser enviado, o HTML atual da div é copiado pro
 * <textarea name="body"> escondido — o servidor SEMPRE sanitiza esse
 * HTML de novo antes de salvar (ver app/richtext.py:sanitize_post_body),
 * então mesmo que alguém adultere o HTML no navegador antes de mandar,
 * nada além da lista permitida sobrevive.
 */
(function () {
    "use strict";

    function initPostEditor(root) {
        var editable = root.querySelector("[data-post-editor-area]");
        var hiddenField = root.querySelector("[data-post-editor-hidden]");
        var toolbar = root.querySelector("[data-post-editor-toolbar]");
        var imageInput = root.querySelector("[data-post-editor-image-input]");
        var uploadUrl = root.getAttribute("data-upload-url");
        var csrfToken = root.getAttribute("data-csrf-token");
        var form = root.closest("form");
        if (!editable || !hiddenField || !toolbar || !form) return;

        // Conteúdo já existente (ex: reabrir um rascunho) — nunca usado
        // aqui hoje (o form sempre começa vazio), mas deixa o editor
        // pronto pra edição no futuro sem precisar mexer nisso de novo.
        if (hiddenField.value) {
            editable.innerHTML = hiddenField.value;
        }

        function syncHiddenField() {
            hiddenField.value = editable.innerHTML;
        }

        editable.addEventListener("input", syncHiddenField);
        form.addEventListener("submit", syncHiddenField);

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

        if (imageInput) {
            imageInput.addEventListener("change", function () {
                var file = imageInput.files && imageInput.files[0];
                imageInput.value = ""; // permite escolher o mesmo arquivo de novo depois
                if (!file || !uploadUrl) return;

                var statusEl = root.querySelector("[data-post-editor-status]");
                if (statusEl) statusEl.textContent = "Enviando imagem…";

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
                            window.alert("Não deu pra enviar essa imagem (formato não aceito ou arquivo grande demais).");
                            return;
                        }
                        editable.focus();
                        document.execCommand("insertImage", false, result.body.url);
                        syncHiddenField();
                    })
                    .catch(function () {
                        if (statusEl) statusEl.textContent = "";
                        window.alert("Falha ao enviar a imagem. Tente de novo.");
                    });
            });
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        var editors = document.querySelectorAll("[data-post-editor]");
        for (var i = 0; i < editors.length; i++) initPostEditor(editors[i]);
    });
})();
