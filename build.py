#!/usr/bin/env python3
"""
Fox templates directory — static site builder.

    python3 build.py     templates.toml -> docs/

Sibling of the theme docs builders: plain HTML, no webfonts, stylesheet inlined,
and the only script is the analytics tag, so a page is a single blocking request.
No dependencies beyond the standard library.

The 111 exported *.json files and their screenshots live under docs/ and are the
one thing a rebuild does not touch — a template is a committed file, not a call
out to the demo site. Only the preview links still point at the live demos.

GitHub Pages serves the docs/ folder on the default branch, which is why the
build output is committed rather than built by CI.
"""

import html
import json
import re
import shutil
import struct
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "docs"
ASSETS = BUILD / "assets"   # screenshots
FILES = BUILD / "files"     # the exported template *.json
STYLE = ROOT / "style.css"


def load_toml(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


# ------------------------------------------------------------- image dimensions
# Read width/height from the JPEG header so every <img> can carry them. That is
# what keeps layout shift at zero on a page that is nothing but screenshots.


def image_size(path):
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            h, w = struct.unpack(">HH", data[i + 5 : i + 9])
            return w, h
        i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    return None


# -------------------------------------------------------------------- the model


class View:
    """One page: the whole directory, or one slice of it."""

    def __init__(self, kind, slug, title, url, items, lede=""):
        self.kind = kind      # "" | "cat" | "demo"
        self.slug = slug
        self.title = title
        self.url = url
        self.items = items
        self.lede = lede


def preview_url(site, item):
    """Link to the demo the template was taken from.

    The query pair is what Fox Monster used to render the widget on its own, and
    the export endpoint still reads it — but the preview half of that plugin was
    never ported to Fox 7.x, so today the link just opens the whole demo page.
    Kept intact so the links come right again if isolation is ever restored.
    """
    return (f'{site["demo_base"]}{item["demo"]}/'
            f'?builder_used={item["builder"]}&amp;widget_id={html.escape(item["widget_id"])}')


def render_card(site, prefix, item, labels):
    url = preview_url(site, item)
    title = html.escape(item["title"])
    size = image_size(ASSETS / item["image"])
    dims = f' width="{size[0]}" height="{size[1]}"' if size else ""
    cat, demo = item["cat"], item["demo"]
    return (
        '<div class=t>'
        f'<a class=shot href="{url}" target=_blank rel=noopener>'
        f'<img src="{prefix}assets/{item["image"]}" alt="{title}"{dims}'
        ' loading="lazy" decoding="async"></a>'
        f'<h2><a href="{url}" target=_blank rel=noopener>{title}</a></h2>'
        f'<p class=meta><a href="{prefix}category/{cat}/">{html.escape(labels["cat"][cat])}</a>'
        f' · <a href="{prefix}demo/{demo}/">{html.escape(labels["demo"][demo])}</a></p>'
        f'<p class=dl><a href="{prefix}files/{item["slug"]}.json" download>Download</a></p>'
        '</div>'
    )


def render_nav(site, views, current, prefix):
    home = views[0]
    on = " class=on" if current is home else ""
    out = ['<nav class="side" id="nav" aria-label="Template directory">',
           f'<a class=side-home href="{prefix}"{on}>All templates <i>{len(home.items)}</i></a>']
    for kind, heading in (("cat", "By type"), ("demo", "By demo")):
        out.append(f"<b>{heading}</b>")
        for view in views:
            if view.kind != kind:
                continue
            mark = " class=on" if view is current else ""
            aria = ' aria-current="page"' if view is current else ""
            out.append(f'<a href="{view.url}"{mark}{aria}>{html.escape(view.title)} '
                       f'<i>{len(view.items)}</i></a>')
    out.append("</nav>")
    return "".join(out)


def breadcrumb_ld(base_url, trail):
    items = []
    for position, (name, url) in enumerate(trail, 1):
        entry = {"@type": "ListItem", "position": position, "name": name}
        if url:
            entry["item"] = base_url + url
        items.append(entry)
    return json.dumps(
        {"@context": "https://schema.org", "@type": "BreadcrumbList",
         "itemListElement": items},
        separators=(",", ":"),
    )


def analytics(ga_id):
    """Google Analytics tag. Empty string when site.toml carries no ga_id."""
    if not ga_id:
        return ""
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={ga_id}"></script>'
        "<script>window.dataLayer=window.dataLayer||[];"
        "function gtag(){dataLayer.push(arguments);}"
        f"gtag('js',new Date());gtag('config','{ga_id}');</script>"
    )


def shell(site, *, title, description, url, body, nav, crumbs, trail, css):
    base, prefix = site["base_url"], site["path_prefix"]
    head = [
        "<!doctype html><html lang=en><head><meta charset=utf-8>",
        '<meta name=viewport content="width=device-width,initial-scale=1">',
        f"<title>{html.escape(title)}</title>",
        f'<meta name=description content="{html.escape(description)}">',
        f'<link rel=canonical href="{base}{url}">',
        f'<meta property="og:title" content="{html.escape(title)}">',
        f'<meta property="og:url" content="{base}{url}">',
        '<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="{html.escape(site["title"])}">',
        f'<meta property="og:description" content="{html.escape(description)}">',
        '<meta name="twitter:card" content="summary">',
        f'<style>:root{{--a:{site["accent"]}}}{css}</style>',
        f'<script type="application/ld+json">{breadcrumb_ld(base, trail)}</script>',
        analytics(site.get("ga_id")),
    ]
    links = "".join(
        f'<a href="{site[key]}"{rel}>{label}</a>'
        for key, label, rel in (
            ("docs_url", "Fox docs", ""),
            ("demo_base", "Demo", " rel=noopener target=_blank"),
        )
        if site.get(key)
    )
    bar = (
        f'<header class=bar><a class=brand href="{prefix}">'
        f'Fox <span>templates</span></a>'
        f'<nav class=bar-links>{links}</nav>'
        f'<a class=jump href="#nav">Browse</a></header>'
    )
    return (
        "".join(head)
        + "</head><body>"
        + '<a class=skip href="#main">Skip to content</a>'
        + bar
        + '<div class=wrap>'
        + f"<main id=main>{crumbs}{body}</main>"
        + nav
        + "</div>"
        + f'<footer class=foot><a href="{site["home_url"]}">All theme docs</a></footer>'
        + "</body></html>"
    )


# ------------------------------------------------------------------------ build


def build():
    site = load_toml(ROOT / "site.toml")
    prefix = site["path_prefix"]
    labels = load_toml(ROOT / "taxonomy.toml")
    items = load_toml(ROOT / "templates.toml")["template"]

    # comments out, whitespace collapsed — the stylesheet ships inside every page
    css = re.sub(r"/\*.*?\*/", "", STYLE.read_text(), flags=re.S)
    css = re.sub(r"\s+", " ", css).strip()
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css).replace(";}", "}")

    # ---- every referenced file must actually be on disk
    missing = []
    for item in items:
        for path in (ASSETS / item["image"], FILES / f"{item['slug']}.json"):
            if not path.exists():
                missing.append(str(path.relative_to(ROOT)))
        for kind in ("cat", "demo"):
            if item[kind] not in labels[kind]:
                missing.append(f'{kind} "{item[kind]}" missing from taxonomy.toml')
    if missing:
        sys.exit("build stopped:\n  " + "\n  ".join(missing))

    # ---- the views: everything, then one page per type and per demo
    home = View("", "", "All templates", prefix, items)
    views = [home]
    for kind, folder in (("cat", "category"), ("demo", "demo")):
        for slug, name in labels[kind].items():
            sliced = [i for i in items if i[kind] == slug]
            if not sliced:
                continue
            title = name if kind == "cat" else f"{name} demo"
            views.append(View(kind, slug, title, f"{prefix}{folder}/{slug}/", sliced))

    # ---- wipe the generated HTML, leave assets/ and files/ alone
    BUILD.mkdir(parents=True, exist_ok=True)
    for entry in BUILD.iterdir():
        if entry in (ASSETS, FILES):
            continue
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()

    urls = []

    def write(url, markup):
        rest = url.removeprefix(prefix).strip("/")
        target = (BUILD / rest / "index.html") if rest else (BUILD / "index.html")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(markup, encoding="utf-8")
        urls.append(url)

    intro = (
        '<p class=lede>Every predefined section and widget shipped with The Fox, '
        'as a ready-to-import JSON file. Download one and '
        f'<a href="{site["import_url"]}">import it into the builder</a>; click a '
        'screenshot to open the demo it was taken from.</p>'
    )

    for view in views:
        cards = "".join(render_card(site, prefix, i, labels) for i in view.items)
        count = f"{len(view.items)} template{'s' if len(view.items) != 1 else ''}"
        if view.kind:
            crumbs = (f'<nav class=crumbs><a href="{prefix}">Fox templates</a>'
                      f'<span>{html.escape(view.title)}</span></nav>')
            heading = html.escape(view.title)
            lede = (f'<p class=lede>{count} in this group. '
                    f'<a href="{prefix}">Browse all {len(items)}</a>.</p>')
            description = f"{count} for The Fox theme — {view.title.lower()}."
            trail = [("Fox templates", prefix), (view.title, None)]
            title = f"{view.title} — Fox templates"
        else:
            crumbs = ""
            heading = "Fox templates"
            lede = intro + f'<p class=count>{count}.</p>'
            description = (f"{count} for The Fox WordPress theme: sections, post "
                           "grids, carousels and lists, ready to import.")
            trail = [("Fox templates", None)]
            title = "Fox templates — ready-made sections for The Fox theme"

        write(view.url, shell(
            site,
            title=title,
            description=description,
            url=view.url,
            body=f"<h1>{heading}</h1>{lede}<div class=grid>{cards}</div>",
            nav=render_nav(site, views, view, prefix),
            crumbs=crumbs,
            trail=trail,
            css=css,
        ))

    # ---- 404
    (BUILD / "404.html").write_text(shell(
        site,
        title="Page not found",
        description="",
        url=prefix,
        body="<h1>Page not found</h1><p class=lede>That page has moved or never "
             f'existed. <a href="{prefix}">Start from the template directory</a>.</p>',
        nav="", crumbs="", trail=[("Fox templates", prefix)], css=css,
    ), encoding="utf-8")

    (BUILD / ".nojekyll").write_text("")

    base = site["base_url"]
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        sitemap.append(f"<url><loc>{base}{url}</loc></url>")
    sitemap.append("</urlset>")
    (BUILD / "sitemap.xml").write_text("".join(sitemap), encoding="utf-8")

    total = sum(f.stat().st_size for f in BUILD.rglob("*") if f.is_file())
    print(f"  {len(urls)} pages · {len(items)} templates · "
          f"{total / 1024 / 1024:.1f} MB · css {len(css) / 1024:.1f} KB inlined")


if __name__ == "__main__":
    build()
