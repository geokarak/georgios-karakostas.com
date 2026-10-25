import datetime as dt
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


def build_template_env():
    templates = Path(__file__).resolve().parents[1] / "theme" / "templates"
    env = Environment(loader=FileSystemLoader(str(templates)))
    env.filters["strftime"] = lambda value, fmt: value.strftime(fmt)
    return env


def render_article(content):
    env = build_template_env()
    template = env.get_template("article.html")
    article = SimpleNamespace(
        category="blog",
        title="Math article",
        date=dt.datetime(2026, 7, 28),
        content=content,
    )
    return template.render(
        article=article,
        SITENAME="Site",
        SITEURL="",
        output_file="blog/test.html",
        page=None,
    )


def render_gallery_page():
    env = build_template_env()
    template = env.get_template("gallery.html")
    page = SimpleNamespace(slug="iphone", title="iPhone")
    return template.render(
        page=page,
        photos_by_category={"iphone": []},
        SITENAME="Site",
        SITEURL="",
        output_file="iphone.html",
        article=None,
    )


def render_vega_article():
    env = build_template_env()
    template = env.get_template("article.html")
    article = SimpleNamespace(
        category="blog",
        title="Vega article",
        date=dt.datetime(2026, 7, 28),
        content="<p>Chart</p>",
        include=["vega"],
        description="",
        summary="",
        url="blog/vega.html",
        thumbnail=None,
        modified=dt.datetime(2026, 7, 28),
    )
    return template.render(
        article=article,
        SITENAME="Site",
        SITEURL="",
        SITELOGO="",
        AUTHOR="Author",
        TWITTER_HANDLE="",
        output_file="blog/vega.html",
        page=None,
    )


def test_article_template_includes_mathjax_for_inline_tex():
    rendered = render_article("<p>At $t$ and $t + 1$.</p>")

    assert "MathJax" in rendered
    assert "/theme/vendor/mathjax/tex-chtml.js" in rendered


def test_article_template_skips_mathjax_without_inline_tex():
    rendered = render_article("<p>No math here.</p>")

    assert "tex-chtml.js" not in rendered


def test_gallery_template_uses_local_glightbox_assets():
    rendered = render_gallery_page()

    assert "/theme/vendor/glightbox/glightbox.min.css" in rendered
    assert "/theme/vendor/glightbox/glightbox.min.js" in rendered


def test_article_template_uses_local_vega_assets():
    rendered = render_vega_article()

    assert "/theme/vendor/vega/vega.min.js" in rendered
    assert "/theme/vendor/vega/vega-lite.min.js" in rendered
    assert "/theme/vendor/vega/vega-embed.min.js" in rendered
    assert "cdn.jsdelivr.net" not in rendered
