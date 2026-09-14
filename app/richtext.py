"""
Support for the WordPress-style post editor (see
app/templates/admin_posts.html and app/static/js/post-editor.js).

The editor runs in the browser as a <div contenteditable> — the HTML
it produces (bold, lists, links, already-uploaded images) arrives
ready in the form's "body" field. Before writing to the database,
this HTML goes through sanitize_post_body(): only a short list of
tags/attributes is allowed, everything else is removed — even though
only an admin (level 2+) publishes posts, this prevents a
<script>/onclick/etc (pasted in by accident from Word, for example,
or by a compromised admin) from ending up on a page everyone visits.

Reading it back uses {{ p.body | safe }} in the templates — it's only
safe precisely because everything that gets there already went
through this sanitization when it was saved.
"""
import re

import nh3

# Tags/attributes that the editor (app/static/js/post-editor.js)
# actually produces. Anything outside this is removed (not escaped —
# the "src"/"href" attributes still go through nh3's scheme check,
# which already blocks "javascript:" by default).
_ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "s",
    "h2", "h3",
    "ul", "ol", "li",
    "a", "img", "span",
    "blockquote", "code", "pre",
}
_ALLOWED_ATTRIBUTES = {
    # "rel" is deliberately NOT in here: link_rel="noopener noreferrer"
    # (below) already lets nh3 itself manage that attribute on every
    # <a> — also listing "rel" in the allowlist conflicts with this
    # (nh3 refuses with ValueError, "rel attribute is not allowed...
    # when link_rel is set").
    "a": {"href", "target"},
    # "class" is deliberately NOT listed here: allowed_classes below
    # already manages it for "img" (alignment only — align-left/
    # right/center, added by the image toolbar in post-editor.js) —
    # same conflict as "rel" above, nh3 refuses if both are set.
    "img": {"src", "alt"},
    # "span style" is how the color/font picker (execCommand with
    # styleWithCSS on) marks up text — filter_style_properties below
    # keeps only the two properties the toolbar actually sets, so this
    # can't become a vector for arbitrary CSS.
    "span": {"style"},
}
_ALLOWED_CLASSES = {
    "img": {"align-left", "align-right", "align-center"},
}
_ALLOWED_STYLE_PROPERTIES = {"color", "font-family"}

_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_post_body(raw_html: str) -> str:
    """Removes any tag/attribute outside the allowed list above."""
    return nh3.clean(
        raw_html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        allowed_classes=_ALLOWED_CLASSES,
        filter_style_properties=_ALLOWED_STYLE_PROPERTIES,
        link_rel="noopener noreferrer",
    )


def html_to_excerpt(html: str, max_chars: int = 220) -> tuple[str, bool]:
    """
    Plain-text version (no tags) of the start of a post, for the
    preview card on the home page — returns (text, was_truncated).
    Used only for short display; the full post (with formatting)
    lives at /posts/{id} — see app/routers/listings_routes.py.
    """
    text = _TAG_RE.sub(" ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text, False
    # cut at a space so we don't split a word in the middle
    cut = text[:max_chars].rsplit(" ", 1)[0] or text[:max_chars]
    return cut, True
