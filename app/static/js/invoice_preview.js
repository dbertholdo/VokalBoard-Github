/* Rechnungmaker — form behaviour + live WYSIWYG preview.
 *
 * v2 (2026-09-28, docs/specs/RECHNUNGMAKER_V2.md): everything country- or
 * language-specific comes from the JSON the server embeds (#inv-data, built
 * from app/invoice_countries.py), so this file never duplicates tax rules.
 * Entirely client-side: nothing typed here is ever sent anywhere until the
 * person submits the form (Zero-Storage, CLAUDE.md §2).
 *
 *  - country change: rebuilds the tax options, sets the country's currency
 *    and invoice language, swaps the country-specific "?" texts;
 *  - tax option change: shows client VAT ID (reverse charge) / own tax fields;
 *  - "?" buttons: click/tap/Enter toggles, Esc or a click elsewhere closes;
 *  - "Invoice the person who posted the job" (Match form) fills/clears the client;
 *  - "+ Add service" / "Remove" for extra service lines (7b);
 *  - the preview mirrors app/invoice_pdf.py (labels, number/date formats, totals).
 */
(function () {
    "use strict";

    var MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

    function num(value) {
        var n = parseFloat(String(value || "0").replace(/\s/g, "").replace(",", "."));
        return isNaN(n) ? 0 : n;
    }

    function money(n, format) {
        // format = [thousands, decimal] like ".," / "'." / ",."
        var parts = Math.abs(n).toFixed(2).split(".");
        var intPart = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, format.charAt(0));
        return (n < 0 ? "-" : "") + intPart + format.charAt(1) + parts[1];
    }

    function formatDate(iso, lang) {
        var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || "");
        if (!m) return iso || "";
        if (lang === "en") return parseInt(m[3], 10) + " " + MONTHS_EN[parseInt(m[2], 10) - 1] + " " + m[1];
        if (lang === "de") return m[3] + "." + m[2] + "." + m[1];
        return m[3] + "/" + m[2] + "/" + m[1];
    }

    function escapeHtml(value) {
        var div = document.createElement("div");
        div.textContent = value;
        return div.innerHTML;
    }

    // ---- "?" help popovers -------------------------------------------------
    function closeAllHelp(except) {
        document.querySelectorAll(".inv-help.open").forEach(function (h) {
            if (h === except) return;
            h.classList.remove("open", "pinned");
            var b = h.querySelector(".inv-help-btn");
            if (b) b.setAttribute("aria-expanded", "false");
        });
    }

    function initHelp() {
        document.addEventListener("click", function (e) {
            var btn = e.target.closest && e.target.closest(".inv-help-btn");
            if (!btn) { closeAllHelp(null); return; }
            e.preventDefault();
            var box = btn.parentNode;
            // Click/tap pins it open (a hover may already have opened it); a second click closes.
            var open = !box.classList.contains("pinned");
            closeAllHelp(box);
            box.classList.toggle("open", open);
            box.classList.toggle("pinned", open);
            btn.setAttribute("aria-expanded", open ? "true" : "false");
        });
        document.addEventListener("keydown", function (e) {
            if (e.key === "Escape") closeAllHelp(null);
        });
        // Mouse users also get it on hover; Esc / moving away closes it.
        if (window.matchMedia && window.matchMedia("(hover: hover)").matches) {
            document.querySelectorAll(".inv-help").forEach(function (box) {
                var btn = box.querySelector(".inv-help-btn");
                box.addEventListener("mouseenter", function () {
                    closeAllHelp(box);
                    box.classList.add("open");
                    btn.setAttribute("aria-expanded", "true");
                });
                box.addEventListener("mouseleave", function () {
                    if (box.classList.contains("pinned")) return;
                    box.classList.remove("open");
                    btn.setAttribute("aria-expanded", "false");
                });
            });
        }
    }

    // ---- form behaviour + preview -----------------------------------------
    function initForm(form, root, data) {
        var el = function (name) { return form.elements[name]; };
        var val = function (name) { var e = el(name); return e ? (e.value || "") : ""; };

        form.querySelectorAll(".inv-apply").forEach(function (b) { b.remove(); });

        function country() { return data.countries[val("country")] ? val("country") : "DE"; }
        function option() {
            var opts = data.countries[country()].options;
            for (var i = 0; i < opts.length; i++) if (opts[i].key === val("tax_option")) return opts[i];
            return opts[0];
        }

        function toggleFields() {
            var opt = option();
            form.querySelectorAll("[data-show-when]").forEach(function (box) {
                var when = box.getAttribute("data-show-when");
                box.hidden = !((when === "client_vat" && opt.clientVat) || (when === "custom" && opt.custom));
            });
        }

        function onCountryChange() {
            var c = data.countries[country()];
            var select = el("tax_option");
            if (select) {
                select.innerHTML = "";
                c.options.forEach(function (o) {
                    var opt = document.createElement("option");
                    opt.value = o.key;
                    opt.textContent = o.label;
                    if (o.key === c.defaultOption) opt.selected = true;
                    select.appendChild(opt);
                });
            }
            if (el("currency")) el("currency").value = c.currency;
            if (el("doc_lang")) el("doc_lang").value = c.docLang;
            ["tax_id", "tax_option"].forEach(function (key) {
                var help = form.querySelector('[data-help-country="' + key + '"]');
                if (help && data.help[key]) help.textContent = data.help[key][country()];
            });
            toggleFields();
        }

        var partner = form.querySelector("#inv-bill-partner");
        if (partner) {
            partner.addEventListener("change", function () {
                var name = el("recipient_name");
                if (!name) return;
                if (partner.checked) {
                    name.value = partner.getAttribute("data-partner-name") || "";
                } else if (name.value === partner.getAttribute("data-partner-name")) {
                    name.value = "";
                    name.focus();
                }
                render();
            });
        }

        // ---- 7b: extra service lines --------------------------------------
        var MAX_EXTRA = 19;
        var extraBox = form.querySelector("[data-extra-services]");
        var extraTpl = form.querySelector("template[data-extra-service-template]");
        var addBtn = form.querySelector("[data-add-service]");

        function extraRows() {
            return extraBox ? Array.prototype.slice.call(extraBox.querySelectorAll("[data-extra-service]")) : [];
        }
        function updateAddButton() {
            if (addBtn) addBtn.hidden = extraRows().length >= MAX_EXTRA;
        }
        extraRows().forEach(function (row) {
            var b = row.querySelector("[data-remove-service]");
            if (b) b.hidden = false;
        });
        if (addBtn && extraBox && extraTpl) {
            addBtn.addEventListener("click", function () {
                var row = extraTpl.content.firstElementChild.cloneNode(true);
                row.querySelector("[data-remove-service]").hidden = false;
                extraBox.appendChild(row);
                row.querySelector("textarea").focus();
                updateAddButton();
                render();
            });
            updateAddButton();
        }
        form.addEventListener("click", function (e) {
            var btn = e.target.closest && e.target.closest("[data-remove-service]");
            if (!btn) return;
            var row = btn.closest("[data-extra-service]");
            if (row) row.remove();
            if (addBtn) addBtn.focus();
            updateAddButton();
            render();
        });
        function extraServices() {
            return extraRows().map(function (row) {
                return [row.querySelector("textarea").value || "", row.querySelector("input").value || ""];
            }).filter(function (r) { return r[0].trim() || r[1].trim(); });
        }

        var rowsBody = root && root.querySelector("[data-preview-rows]");
        var notesBox = root && root.querySelector("[data-preview-notes]");

        function setText(key, value) {
            var node = root.querySelector('[data-preview="' + key + '"]');
            if (node) node.textContent = value && String(value).trim() ? value : "—";
        }

        function setLabel(key, value) {
            root.querySelectorAll('[data-label="' + key + '"]').forEach(function (n) { n.textContent = value; });
        }

        function render() {
            if (!root) return;
            var c = data.countries[country()];
            var lang = data.docLabels[val("doc_lang")] ? val("doc_lang") : c.docLang;
            var L = data.docLabels[lang];
            var fmt = c.number;
            var currency = val("currency") || c.currency;
            var opt = option();
            var rate = opt.custom ? num(val("tax_custom_rate")) : num(opt.rate);
            var taxName = (opt.custom && val("tax_custom_name").trim()) || c.taxNames[lang];
            var services = [[val("service_description") || "—", num(val("net_amount"))]].concat(
                extraServices().map(function (r) { return [r[0] || "—", num(r[1])]; }));
            var net = services.reduce(function (sum, r) { return sum + r[1]; }, 0);
            var travel = num(val("expense_travel_amount"));
            var lodging = num(val("expense_lodging_amount"));
            var tax = Math.round(net * rate) / 100;
            var total = net + tax + travel + lodging;

            Object.keys(L).forEach(function (k) { setLabel(k, L[k]); });
            setLabel("tax_id", c.taxIdLabels[lang]);
            setText("number", val("number"));
            setText("issue_date", formatDate(val("issue_date"), lang));
            setText("service_date", formatDate(val("service_date"), lang));
            ["issuer_name", "issuer_address", "issuer_tax_id", "recipient_name", "recipient_address"].forEach(function (k) {
                setText(k, val(k));
            });
            var vatLine = root.querySelector("[data-preview-client-vat]");
            if (vatLine) {
                vatLine.hidden = !(opt.clientVat && val("client_vat_id").trim());
                vatLine.textContent = L.client_vat + ": " + val("client_vat_id");
            }

            if (rowsBody) {
                var rows = services.slice();
                if (travel > 0) rows.push([L.travel, travel]);
                if (lodging > 0) rows.push([L.lodging, lodging]);
                rowsBody.innerHTML = rows.map(function (r, i) {
                    var amount = money(r[1], fmt) + " " + escapeHtml(currency);
                    return "<tr><td>" + (i + 1) + "</td><td>" + escapeHtml(r[0]) + "</td><td>1</td><td>" +
                        escapeHtml(L.flat) + "</td><td>" + amount + "</td><td>" + amount + "</td></tr>";
                }).join("");
            }

            setText("calc_net", money(net, fmt) + " " + currency);
            setText("calc_tax_label", taxName + " (" + (rate || 0) + " %)");
            setText("calc_tax", money(tax, fmt) + " " + currency);
            setText("calc_total", money(total, fmt) + " " + currency);

            if (notesBox) {
                var notes = [];
                if (opt.note && data.notes[opt.note]) notes.push(data.notes[opt.note][lang]);
                notes.push(val("tax_extra_note"), val("payment_terms"));
                if (val("iban")) notes.push("IBAN: " + val("iban"));
                if (val("bic")) notes.push("BIC: " + val("bic"));
                notesBox.innerHTML = notes.filter(function (n) { return n && n.trim(); })
                    .map(function (n) { return "<p>" + escapeHtml(n) + "</p>"; }).join("");
            }
        }

        form.addEventListener("change", function (e) {
            if (e.target === el("country")) onCountryChange();
            if (e.target === el("tax_option")) toggleFields();
            render();
        });
        form.addEventListener("input", render);
        toggleFields();
        render();
    }

    document.addEventListener("DOMContentLoaded", function () {
        initHelp();
        var dataNode = document.getElementById("inv-data");
        if (!dataNode) return;
        var data = JSON.parse(dataNode.textContent);
        document.querySelectorAll("form").forEach(function (form) {
            if (!form.elements.country || !form.elements.tax_option) return;
            var root = form.id ? document.querySelector('[data-invoice-preview="' + form.id + '"]') : null;
            initForm(form, root, data);
        });
    });
})();
