"""
P3.E: "compatibilidade" usada pra ordenar anúncios (Home, e depois
qualquer diretório futuro que precise da mesma regra) — decisões
confirmadas por Daniel em 18/09/2026:

  Tipo de voz (peso máximo, mas já é um FILTRO binário aplicado antes
  disso — sim/não, nunca "aproxima" — ver home() em listings_routes.py,
  não entra aqui)
  > Fach — EXCLUÍDO de propósito ("muito subjetivo pra ser critério")
  > Cidade (cascata cidade > estado > país — sem lat/long na tabela
    `cities`, então não dá pra fazer proximidade em km de verdade)
  > Nota (média de estrelas do autor do anúncio — NUNCA exibida
    publicamente, é só um sinal de desempate interno; a única exceção é
    o próprio dono vendo a própria média, ou o Admin abrindo "Manage")

Isso não decide SE a compatibilidade aparece pro usuário final — só
calcula o valor. A exibição fica atrás do toggle `compatibility_score_visible`
em system_settings (ver app/system_flags.py), que nasce desligado.
"""

# Cascata de proximidade: 0 = mesma cidade, 1 = mesmo estado (cidade
# diferente ou em branco), 2 = mesmo país (fora os dois casos acima),
# 3 = nada bate (ou o visitante não tem localização própria pra comparar).
CITY_TIER_SQL = """
    CASE
        WHEN :viewer_city != '' AND l.city ILIKE :viewer_city THEN 0
        WHEN :viewer_state != '' AND l.state = :viewer_state THEN 1
        WHEN :viewer_country != '' AND l.country = :viewer_country THEN 2
        ELSE 3
    END
"""

# Média de estrelas de quem publicou o anúncio — usada só como
# desempate (nunca exibida ao público, ver docstring acima). Um
# LEFT JOIN com AVG() em vez de subquery por linha evita o padrão N+1
# proibido pelo CLAUDE.md (seção 4.2).
RATING_JOIN_SQL = """
    LEFT JOIN (
        SELECT rated_id, AVG(stars) AS avg_stars
        FROM ratings
        GROUP BY rated_id
    ) author_rating ON author_rating.rated_id = l.author_id
"""

# Ordem completa da Home, confirmada por Daniel: quem paga mais
# primeiro; "a negociar" sempre por último, e dentro de cada grupo,
# desempate por compatibilidade (cidade > nota) e por fim o mais
# recente primeiro.
FEE_COMPATIBILITY_ORDER_SQL = f"""
    l.fee_negotiable ASC,
    CASE WHEN NOT l.fee_negotiable THEN l.fee_amount END DESC NULLS LAST,
    {CITY_TIER_SQL} ASC,
    author_rating.avg_stars DESC NULLS LAST,
    l.created_at DESC
"""


def viewer_location_params(user: dict | None) -> dict:
    """
    Builds the :viewer_city/:viewer_state/:viewer_country params that
    CITY_TIER_SQL expects. Works for a logged-in user's own profile
    fields, or an empty dict (anonymous visitor — always falls to tier
    3, no personalization possible, per Daniel: "se a pessoa não tá
    logada... anúncios genéricos e mistos").
    """
    if not user:
        return {"viewer_city": "", "viewer_state": "", "viewer_country": ""}
    return {
        "viewer_city": (user.get("city") or "").strip(),
        "viewer_state": (user.get("state") or "").strip(),
        "viewer_country": (user.get("country") or "").strip(),
    }
