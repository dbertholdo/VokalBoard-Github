/* Rechnungmaker — live WYSIWYG preview (19/09/2026, Daniel: "enquanto vá
 * editando, vá vendo cada elemento da página").
 *
 * Entirely client-side: reads the invoice form's own fields on every
 * input/change and re-renders a paper-style mock of the PDF next to it.
 * Nothing here is sent to the server — the Rechnung's Zero-Storage
 * Policy (CLAUDE.md §2) already keeps address/bank data out of the
 * database and off disk until the real PDF is generated; this preview
 * has to honor the same rule, so it never posts a byte anywhere.
 *
 * Mirrors two bits of server logic on purpose, kept in sync by hand:
 *   - app/invoice_tax_presets.py resolve_tax() → TAX_RATE_DEFAULTS / LEGAL_PHRASES below
 *   - app/invoice_pdf.py InvoiceDocument.validate() → the net/tax/total math below
 * If either of those ever changes, update this file too.
 */
(function () {
    "use strict";

    var STANDARD_RATE_DEFAULT = { DE: "19", AT: "20", CH: "8.1" };
    var LEGAL_PHRASES = {
        "DE:kleinunternehmer": "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
        "DE:cultural": "Umsatzsteuerfreie künstlerische Leistung gemäß § 4 Nr. 20 UStG.",
        "AT:kleinunternehmer": "Kleinunternehmerregelung — keine Umsatzsteuer ausgewiesen (Steuerbefreiung bitte mit Ihrem Steuerberater bestätigen).",
        "AT:cultural": "Steuerbefreite künstlerische Leistung (genaue Rechtsgrundlage bitte mit Ihrem Steuerberater bestätigen).",
        "CH:kleinunternehmer": "Von der Mehrwertsteuer befreit (Kleinunternehmen) — bitte mit Ihrer Treuhandstelle bestätigen.",
        "CH:cultural": "Von der Mehrwertsteuer befreite künstlerische Leistung — bitte mit Ihrer Treuhandstelle bestätigen.",
    };

    function num(value) {
        var n = parseFloat(String(value || "0").replace(",", "."));
        return isNaN(n) ? 0 : n;
    }

    function money(n) {
        return n.toFixed(2);
    }

    function resolveTax(country, status, customText, rateOverride) {
        country = ["DE", "AT", "CH", "OTHER"].indexOf(country) >= 0 ? country : "OTHER";
        if (country === "OTHER" || status === "other") {
            return { rate: num(rateOverride) || 0, note: (customText || "").trim() };
        }
        if (status === "standard") {
            var rate = rateOverride ? num(rateOverride) : num(STANDARD_RATE_DEFAULT[country] || "0");
            return { rate: rate, note: (customText || "").trim() };
        }
        var phrase = (customText || "").trim() || LEGAL_PHRASES[country + ":" + status] || "";
        return { rate: 0, note: phrase };
    }

    function field(form, name) {
        var el = form.elements[name];
        if (!el) return "";
        return el.value || "";
    }

    function setText(root, key, value) {
        var el = root.querySelector('[data-preview="' + key + '"]');
        if (el) el.textContent = value && String(value).trim() ? value : "—";
    }

    function initInvoicePreview(form, root) {
        var rowsBody = root.querySelector("[data-preview-rows]");
        var notesBox = root.querySelector("[data-preview-notes]");

        function render() {
            var currency = field(form, "currency") || "EUR";
            var net = num(field(form, "net_amount"));
            var travel = num(field(form, "expense_travel_amount"));
            var lodging = num(field(form, "expense_lodging_amount"));
            // One "COUNTRY:status" select (the server parses the same value).
            var preset = (field(form, "tax_preset") || "DE:standard").split(":");
            var tax = resolveTax(
                preset[0] || "DE",
                preset[1] || "standard",
                field(form, "tax_custom_text"),
                field(form, "tax_rate_override")
            );
            var taxAmount = net * (tax.rate / 100);
            var total = net + taxAmount + travel + lodging;

            setText(root, "number", field(form, "number"));
            setText(root, "issue_date", field(form, "issue_date"));
            setText(root, "service_date", field(form, "service_date"));
            setText(root, "issuer_name", field(form, "issuer_name"));
            setText(root, "issuer_address", field(form, "issuer_address"));
            setText(root, "issuer_tax_id", field(form, "issuer_tax_id"));
            setText(root, "recipient_name", field(form, "recipient_name"));
            setText(root, "recipient_address", field(form, "recipient_address"));

            if (rowsBody) {
                var serviceDescription = field(form, "service_description") || "—";
                var rowsHtml = "";
                var pos = 1;
                rowsHtml += invoiceRow(pos, serviceDescription, money(net), currency);
                if (travel > 0) {
                    pos += 1;
                    rowsHtml += invoiceRow(pos, "Fahrkosten", money(travel), currency);
                }
                if (lodging > 0) {
                    pos += 1;
                    rowsHtml += invoiceRow(pos, "Übernachtungskosten", money(lodging), currency);
                }
                rowsBody.innerHTML = rowsHtml;
            }

            setText(root, "calc_net", money(net) + " " + currency);
            setText(root, "calc_tax_label", "Umsatzsteuer (" + (tax.rate || 0) + "%)");
            setText(root, "calc_tax", money(taxAmount) + " " + currency);
            setText(root, "calc_total", money(total) + " " + currency);

            if (notesBox) {
                var notes = [tax.note, field(form, "payment_terms")];
                var iban = field(form, "iban");
                var bic = field(form, "bic");
                if (iban) notes.push("IBAN: " + iban);
                if (bic) notes.push("BIC: " + bic);
                notes = notes.filter(function (n) { return n && n.trim(); });
                notesBox.innerHTML = notes.length
                    ? notes.map(function (n) { return "<p>" + escapeHtml(n) + "</p>"; }).join("")
                    : "";
            }
        }

        function invoiceRow(pos, label, amount, currency) {
            return (
                "<tr><td>" + pos + "</td><td>" + escapeHtml(label) +
                "</td><td>1</td><td>pausch.</td><td>" + amount + " " + currency +
                "</td><td>" + amount + " " + currency + "</td></tr>"
            );
        }

        function escapeHtml(value) {
            var div = document.createElement("div");
            div.textContent = value;
            return div.innerHTML;
        }

        form.addEventListener("input", render);
        form.addEventListener("change", render);
        render();
    }

    document.addEventListener("DOMContentLoaded", function () {
        var previews = document.querySelectorAll("[data-invoice-preview]");
        previews.forEach(function (root) {
            var formId = root.getAttribute("data-invoice-preview");
            var form = document.getElementById(formId);
            if (form) initInvoicePreview(form, root);
        });
    });
})();
