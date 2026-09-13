"""
Gera db/seed_cities.sql a partir do pacote `geonamescache` (dados do
GeoNames, https://www.geonames.org/, licença Creative Commons
Attribution 4.0).

Por que assim: montar essa lista à mão (todo Bundesland/Kanton com
suas cidades) seria impraticável e propenso a erro. O GeoNames já tem
esses dados prontos, com nome oficial, população e o código do
estado/cantão (admin1code) de cada cidade — só precisamos mapear esse
código pro nome do estado/cantão (a Alemanha e a Áustria usam códigos
numéricos "01".."16"/"01".."09"; a Suíça já usa a sigla do cantão
diretamente, ex: "ZH", "BE").

Uso:
    pip install geonamescache --break-system-packages
    python3 scripts/generate_cities_seed.py

Isso sobrescreve db/seed_cities.sql. Rode de novo só se quiser trocar
o corte de população ou adicionar outro país.
"""
import geonamescache

# Corte de população: o dataset "cities" do geonamescache já vem
# filtrado (cidades "grandes o suficiente para importar"), mas
# deixamos explícito aqui pra documentar a intenção — cidades muito
# pequenas (vilarejos) não entram, porque o objetivo é cobrir onde as
# pessoas realmente moram/trabalham, não uma lista exaustiva de cada
# povoado.
MIN_POPULATION = 0  # o pacote já filtra por ~15.000 antes de chegar aqui

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

# Exônimos/grafias em inglês que o geonamescache usa como "name"
# principal — corrigidos pra grafia local, já que o site é DE/EN mas
# o público-alvo é da própria região.
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
        # "Zürich (Kreis 11)" e afins são distritos urbanos, não
        # municípios separados — excluídos.
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
        "-- Cidades reais da Alemanha, Áustria e Suíça (fonte: GeoNames, cidades",
        "-- com população >= ~15.000 habitantes), agrupadas por estado/cantão.",
        "-- Gerado automaticamente via scripts/generate_cities_seed.py — não edite",
        "-- este arquivo à mão, rode o script de novo se precisar atualizar.",
        "",
        "INSERT INTO cities (name, state, country_code, population) VALUES",
    ]
    values = [f"    ('{esc(name)}', '{esc(state)}', '{cc}', {pop})" for name, state, cc, pop in rows]
    lines.append(",\n".join(values) + ";")
    lines.append("")

    with open("db/seed_cities.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Gerado db/seed_cities.sql com {len(rows)} cidades.")


if __name__ == "__main__":
    main()
