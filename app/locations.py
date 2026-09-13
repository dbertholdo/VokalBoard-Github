"""
Localização (país/estado/cidade) usada em vários lugares: cadastro,
edição de perfil e formulário de anúncio. Centralizado aqui pra não
duplicar a mesma lista de Bundesländer/Kantone em três routers
diferentes.

País > Estado é uma lista fixa (não muda). País > Estado > Cidade vem
do banco (tabela `cities`, ver db/schema.sql e
scripts/generate_cities_seed.py) — carregada uma vez e mantida em
cache no processo, já que essa lista não muda em runtime; reiniciar o
app (ou chamar reload_city_options(), útil em testes) recarrega.
"""
from app.database import fetch_all

# Países atendidos (DACH) + "outro" — usado no formulário de anúncio,
# no cadastro/perfil e no filtro de busca em /board.
COUNTRY_OPTIONS = ["DE", "AT", "CH", "OTHER"]

# Estados/Bundesländer/Kantone por país — alimenta o <select> de
# "Estado" em cascata (País > Estado) via JS. "OTHER" fica de fora de
# propósito: nesse caso o campo Estado vira texto livre.
STATE_OPTIONS = {
    "DE": [
        "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
        "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
        "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
        "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
    ],
    "AT": [
        "Burgenland", "Kärnten", "Niederösterreich", "Oberösterreich",
        "Salzburg", "Steiermark", "Tirol", "Vorarlberg", "Wien",
    ],
    "CH": [
        "Aargau", "Appenzell Ausserrhoden", "Appenzell Innerrhoden",
        "Basel-Landschaft", "Basel-Stadt", "Bern", "Freiburg", "Genf",
        "Glarus", "Graubünden", "Jura", "Luzern", "Neuenburg",
        "Nidwalden", "Obwalden", "Schaffhausen", "Schwyz", "Solothurn",
        "St. Gallen", "Tessin", "Thurgau", "Uri", "Waadt", "Wallis",
        "Zug", "Zürich",
    ],
}

_city_options_cache: dict[str, list[str]] | None = None


def get_city_options() -> dict[str, list[str]]:
    """
    Devolve {estado: [cidades ordenadas por população desc]}, vindo da
    tabela `cities`. Cacheado em memória no processo — a lista de
    cidades não muda em runtime, então não vale a pena consultar o
    banco a cada requisição.
    """
    global _city_options_cache
    if _city_options_cache is None:
        _city_options_cache = _load_city_options()
    return _city_options_cache


def reload_city_options() -> None:
    """Força recarregar do banco na próxima chamada (útil em testes)."""
    global _city_options_cache
    _city_options_cache = None


def _load_city_options() -> dict[str, list[str]]:
    rows = fetch_all("SELECT name, state FROM cities ORDER BY state, population DESC NULLS LAST, name")
    options: dict[str, list[str]] = {}
    for row in rows:
        options.setdefault(row["state"], []).append(row["name"])
    return options
