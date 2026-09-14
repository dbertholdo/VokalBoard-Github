"""
Suporte ao editor de posts estilo WordPress (ver
app/templates/admin_posts.html e app/static/js/post-editor.js).

O editor roda no navegador como uma <div contenteditable> — o HTML que
ele produz (negrito, listas, links, imagens já enviadas) chega pronto
no campo "body" do formulário. Antes de gravar no banco, esse HTML
passa por sanitize_post_body(): só uma lista curta de tags/atributos é
permitida, o resto é removido — mesmo sendo só admin (nível 2+) quem
publica posts, isso evita que um <script>/onclick/etc (colado sem
querer do Word, por exemplo, ou por um admin comprometido) vá parar
numa página que todo mundo visita.

A leitura de volta usa {{ p.body | safe }} nos templates — só é seguro
justamente porque tudo que chega até lá já passou por essa sanitização
no momento de salvar.
"""
import re

import nh3

# Tags/atributos que o editor (app/static/js/post-editor.js) realmente
# produz. Qualquer coisa fora disso é removida (não escapada — os
# atributos "src"/"href" continuam passando pela checagem de esquema
# do nh3, que já bloqueia "javascript:" por padrão).
_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "h2", "h3",
    "ul", "ol", "li",
    "a", "img",
    "blockquote", "code", "pre",
}
_ALLOWED_ATTRIBUTES = {
    # "rel" NÃO entra aqui de propósito: link_rel="noopener noreferrer"
    # (abaixo) já deixa o próprio nh3 gerenciar esse atributo em todo
    # <a> — listar "rel" também na allowlist conflita com isso (o nh3
    # recusa com ValueError, "rel attribute is not allowed... when
    # link_rel is set").
    "a": {"href", "target"},
    "img": {"src", "alt"},
}

_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_post_body(raw_html: str) -> str:
    """Remove qualquer tag/atributo fora da lista permitida acima."""
    return nh3.clean(
        raw_html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer",
    )


def html_to_excerpt(html: str, max_chars: int = 220) -> tuple[str, bool]:
    """
    Versão em texto puro (sem tags) do início de um post, pro card de
    preview na home — devolve (texto, foi_cortado). Usado só pra
    exibição curta; o post inteiro (com formatação) mora em
    /posts/{id} — ver app/routers/listings_routes.py.
    """
    text = _TAG_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text, False
    # corta num espaço pra não partir uma palavra no meio
    cut = text[:max_chars].rsplit(" ", 1)[0] or text[:max_chars]
    return cut, True
