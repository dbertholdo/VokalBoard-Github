"""
Location (country/state/city) used in several places: sign-up, profile
editing and the listing form. Centralized here to avoid duplicating
the same Bundesländer/Kantone list across three different routers.

Country > State is a fixed list (doesn't change). Country > State >
City comes from the database (`cities` table, see db/schema.sql and
scripts/generate_cities_seed.py) — loaded once and cached in the
process, since this list doesn't change at runtime; restarting the app
(or calling reload_city_options(), useful in tests) reloads it.
"""
from app.database import fetch_all

# Countries served (DACH) + "other" — used in the listing form,
# sign-up/profile, and the search filter on /board.
COUNTRY_OPTIONS = ["DE", "AT", "CH", "OTHER"]

# States/Bundesländer/Kantone per country — feeds the cascading
# "State" <select> (Country > State) via JS. "OTHER" is deliberately
# left out: in that case the State field becomes free text.
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
    Returns {state: [cities ordered by population desc]}, sourced from
    the `cities` table. Cached in process memory — the city list
    doesn't change at runtime, so it isn't worth querying the database
    on every request.
    """
    global _city_options_cache
    if _city_options_cache is None:
        _city_options_cache = _load_city_options()
    return _city_options_cache


def reload_city_options() -> None:
    """Forces a reload from the database on the next call (useful in tests)."""
    global _city_options_cache
    _city_options_cache = None


def _load_city_options() -> dict[str, list[str]]:
    rows = fetch_all("SELECT name, state FROM cities ORDER BY state, population DESC NULLS LAST, name")
    options: dict[str, list[str]] = {}
    for row in rows:
        options.setdefault(row["state"], []).append(row["name"])
    return options
