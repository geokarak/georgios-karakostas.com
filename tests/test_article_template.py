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


def test_article_template_includes_mathjax_for_inline_tex():
    rendered = render_article("<p>At $t$ and $t + 1$.</p>")

    assert "MathJax" in rendered
    assert "tex-chtml.js" in rendered


def test_article_template_skips_mathjax_without_inline_tex():
    rendered = render_article("<p>No math here.</p>")

    assert "tex-chtml.js" not in rendered
