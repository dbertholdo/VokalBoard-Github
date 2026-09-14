"""
Generates db/seed_cities.sql from the `geonamescache` package (GeoNames
data, https://www.geonames.org/, Creative Commons Attribution 4.0
license).

Why do it this way: building this list by hand (every Bundesland/Kanton
with its cities) would be impractical and error-prone. GeoNames already
has this data ready, with the official name, population and the
state/canton code (admin1code) of each city — we just need to map that
code to the state/canton name (Germany and Austria use numeric codes
"01".."16"/"01".."09"; Switzerland already uses the canton abbreviation
directly, e.g. "ZH", "BE").

Usage:
    pip install geonamescache --break-system-packages
    python3 scripts/generate_cities_seed.py

This overwrites db/seed_cities.sql. Rerun it only if you want to change
the population cutoff or add another country.
"""
import geonamescache

# Population cutoff: the geonamescache "cities" dataset already comes
# filtered (cities "large enough to be worth importing"), but we make
# it explicit here to document the intent — very small places
# (villages) are excluded, because the goal is to cover where people
# actually live/work, not an exhaustive list of every settlement.
MIN_POPULATION = 0  # the package already filters to ~15,000 before this

DE_STATES = {
    "01": "Baden-Württemberg", "02": "Bayern", "03": "Bremen", "04": "Hamburg",
    "05": "Hessen", "06": "Niedersachsen", "07": "Nordrhein-Westfalen",
    "08": "Rheinland-Pfalz", "09": "Saarland", "10": "Schleswig-Holstein",
    "11": "Brandenburg", "12": "Mecklenburg-Vorpommern", "13": "Sachsen",
    "14": "Sachsen-Anhalt", "15": "Thüringen", "16": "Berlin",
}
AT_STATES = {
    "01": "Burgenland", "02": "Kärnten", "03": "Niederösterreich", "04": "Oberösterreich",
    "05": "Salzburg", "06": "Steiermark", "07": "Tirol", "08": "Vorarlberg", "09": "Wien",
}
CH_CANTONS = {
    "AG": "Aargau", "AR": "Appenzell Ausserrhoden", "AI": "Appenzell Innerrhoden",
    "BL": "Basel-Landschaft", "BS": "Basel-Stadt", "BE": "Bern", "FR": "Freiburg",
    "GE": "Genf", "GL": "Glarus", "GR": "Graubünden", "JU": "Jura", "LU": "Luzern",
    "NE": "Neuenburg", "NW": "Nidwalden", "OW": "Obwalden", "SH": "Schaffhausen",
    "SZ": "Schwyz", "SO": "Solothurn", "SG": "St. Gallen", "TI": "Tessin",
    "TG": "Thurgau", "UR": "Uri", "VD": "Waadt", "VS": "Wallis", "ZG": "Zug", "ZH": "Zürich",
}

# Exonyms/English spellings that geonamescache uses as the main
# "name" — corrected to the local spelling, since the site is DE/EN
# but the target audience is from the region itself.
NAME_OVERRIDES = {
    "Munich": "München", "Cologne": "Köln", "Nuremberg": "Nürnberg",
    "Hanover": "Hannover", "Brunswick": "Braunschweig", "Vienna": "Wien",
    "Geneva": "Genève", "Sankt Gallen": "St. Gallen",
}


def build(cities, country_code, state_map):
    subset = [c for c in cities.values() if c["countrycode"] == country_code]
    rows, seen = [], set()
    for c in subset:
        name = c["name"]
        # "Zürich (Kreis 11)" and similar are urban districts, not
        # separate municipalities — excluded.
        if "Kreis" in name or "/" in name:
            continue
        name = NAME_OVERRIDES.get(name, name)
        state = state_map.get(c["admin1code"])
        if not state or c["population"] < MIN_POPULATION:
            continue
        key = (name, state)
        if key in seen:
            continue
        seen.add(key)
        rows.append((name, state, country_code, c["population"]))
    rows.sort(key=lambda r: (r[1], -r[3]))
    return rows


def esc(s: str) -> str:
    return s.replace("'", "''")


def main():
    gc = geonamescache.GeonamesCache()
    cities = gc.get_cities()

    rows = (
        build(cities, "DE", DE_STATES)
        + build(cities, "AT", AT_STATES)
        + build(cities, "CH", CH_CANTONS)
    )

    lines = [
        "-- Real cities in Germany, Austria and Switzerland (source: GeoNames,",
        "-- cities with population >= ~15,000), grouped by state/canton.",
        "-- Auto-generated via scripts/generate_cities_seed.py — do not edit",
        "-- this file by hand, rerun the script if you need to update it.",
        "",
        "INSERT INTO cities (name, state, country_code, population) VALUES",
    ]
    values = [f"    ('{esc(name)}', '{esc(state)}', '{cc}', {pop})" for name, state, cc, pop in rows]
    lines.append(",\n".join(values) + ";")
    lines.append("")

    with open("db/seed_cities.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated db/seed_cities.sql with {len(rows)} cities.")


if __name__ == "__main__":
    main()
