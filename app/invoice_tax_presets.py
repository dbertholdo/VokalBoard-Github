"""P4: opções de tributação (USt/MWST) para o formulário de Rechnung —
usado pelos dois fluxos (Gerador Avulso e Match-Rechnungen).

Decisão do Daniel (18/09/2026): radios fixos com "padrões" por país
(Alemanha, Áustria, Suíça) + uma opção "Outro" com texto livre pra
quem está em outro país (EUA, resto da UE etc.).

As frases legais exatas do § 19 UStG e do § 4 Nr. 20 UStG (Alemanha)
vêm literalmente do documento-fonte do Daniel — são texto dele, não
uma citação legal que o Claude inventou. Para Áustria e Suíça o
Claude NÃO tem uma citação de parágrafo verificada equivalente, então
o texto fica genérico e sinaliza a necessidade de confirmação com um
contador/Steuerberater local antes de usar em produção — evita
apresentar uma citação legal não verificada como se fosse exata.
"""

TAX_COUNTRIES = ("DE", "AT", "CH", "OTHER")
TAX_STATUSES = ("kleinunternehmer", "cultural", "standard", "other")

# Menu suspenso único de país+tributação (to-do do P4, adicionada em
# 18/09/2026) — junta os dois radios antigos (país / status) numa lista
# só, já mostrando o par completo ("Deutschland — Kleinunternehmer...").
# O valor de cada opção é "PAIS:status" — o formulário faz o split em
# JS puro pros dois campos ocultos que o backend já espera
# (tax_country/tax_status), então resolve_tax() nem precisa mudar.
# "Outro" continua sendo texto livre (campo tax_custom_text já existe).
TAX_PRESET_OPTIONS = (
    # (value "COUNTRY:status", i18n label key) — labels are translated in the template.
    ("DE:kleinunternehmer", "inv_tax_de_klein"),
    ("DE:cultural", "inv_tax_de_cultural"),
    ("DE:standard", "inv_tax_de_standard"),
    ("AT:kleinunternehmer", "inv_tax_at_klein"),
    ("AT:cultural", "inv_tax_at_cultural"),
    ("AT:standard", "inv_tax_at_standard"),
    ("CH:kleinunternehmer", "inv_tax_ch_exempt"),
    ("CH:cultural", "inv_tax_ch_cultural"),
    ("CH:standard", "inv_tax_ch_standard"),
    ("OTHER:other", "inv_tax_other"),
)
TAX_PRESET_DEFAULT = "DE:standard"


def parse_tax_preset(value: str | None) -> tuple[str, str, str]:
    """(country, status, preset) from the form's single "tax_preset" select.
    FIX 2026-09-27: the select used an inline onchange handler to copy the
    choice into two hidden fields — blocked by our CSP, so every invoice was
    silently "DE:standard" (19 % VAT, even for Kleinunternehmer). The server
    now reads the select itself; unknown values fall back to the default."""
    preset = value if value in dict(TAX_PRESET_OPTIONS) else TAX_PRESET_DEFAULT
    country, status = preset.split(":")
    return country, status, preset

# Alíquota padrão sugerida (editável pelo usuário) quando "standard" é
# escolhido — não é aconselhamento fiscal, só um ponto de partida.
STANDARD_RATE_DEFAULT = {"DE": "19", "AT": "20", "CH": "8.1"}

# Frases automáticas — só as da Alemanha são citação literal do
# documento-fonte (verificada pelo Daniel). AT/CH ficam genéricas de
# propósito.
_LEGAL_PHRASES = {
    ("DE", "kleinunternehmer"): "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
    ("DE", "cultural"): "Umsatzsteuerfreie künstlerische Leistung gemäß § 4 Nr. 20 UStG.",
    ("AT", "kleinunternehmer"): "Kleinunternehmerregelung — keine Umsatzsteuer ausgewiesen (Steuerbefreiung bitte mit Ihrem Steuerberater bestätigen).",
    ("AT", "cultural"): "Steuerbefreite künstlerische Leistung (genaue Rechtsgrundlage bitte mit Ihrem Steuerberater bestätigen).",
    ("CH", "kleinunternehmer"): "Von der Mehrwertsteuer befreit (Kleinunternehmen) — bitte mit Ihrer Treuhandstelle bestätigen.",
    ("CH", "cultural"): "Von der Mehrwertsteuer befreite künstlerische Leistung — bitte mit Ihrer Treuhandstelle bestätigen.",
}


def resolve_tax(country: str, status: str, custom_text: str, rate_override: str | None) -> tuple[str, str]:
    """Returns (tax_rate, tax_note) to feed into InvoiceDocument.

    - status in ('kleinunternehmer', 'cultural'): rate is always "0",
      note is the fixed phrase for that country (or the custom text,
      if the person edited it).
    - status == 'standard': rate is rate_override or the country's
      suggested default; note is whatever the person typed (if any).
    - status == 'other' (or country == 'OTHER'): rate is rate_override
      or "0"; note is exactly the person's own free text.
    """
    country = country if country in TAX_COUNTRIES else "OTHER"
    if country == "OTHER" or status == "other":
        rate = (rate_override or "0").strip()
        return rate, (custom_text or "").strip()
    if status == "standard":
        rate = (rate_override or STANDARD_RATE_DEFAULT.get(country, "0")).strip()
        return rate, (custom_text or "").strip()
    # kleinunternehmer / cultural — no tax, fixed (or person-edited) phrase.
    phrase = (custom_text or "").strip() or _LEGAL_PHRASES.get((country, status), "")
    return "0", phrase
