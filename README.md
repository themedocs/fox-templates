# Fox templates

The template directory for The Fox theme — published at
<https://fox-templates.heronwp.com/>.

Migrated off the old WordPress template site (2026-08-06), then off
themedocs.github.io onto Cloudflare Pages (2026-09-02). The exported `*.json`
files are committed here, so a download no longer depends on the demo multisite
being up.

## Layout

```
templates.toml     one entry per template — the whole directory
taxonomy.toml      display names for the types and the demos
site.toml          URLs, accent, where the demos live
build.py           templates.toml -> docs/
docs/assets/       screenshots, 640px wide
docs/files/        the exported template JSON, one per template
docs/              build output — uploaded to Cloudflare Pages
```

`docs/assets/` and `docs/files/` are the two folders a rebuild does not touch.

## Editing

1. Edit `templates.toml` (and drop the screenshot + JSON into `docs/assets/`
   and `docs/files/` if you are adding one).
2. `python3 ../deploy-fox-templates.py --deploy --stubs`
3. Commit and push.

`deploy-fox-templates.py` (in the parent directory, next to the docs builders)
runs `build.py`, uploads the result to the `fox-templates` Cloudflare Pages
project, and then rewrites `docs/` as meta-refresh forwards — what GitHub Pages
keeps serving on the old `themedocs.github.io/fox-templates/` URLs. That is why
the `docs/*.html` committed here are forwards and not pages; `docs/assets/` and
`docs/files/` stay real so old screenshot and download links keep working.

Running `python3 build.py` on its own leaves real pages in `docs/` — fine for
previewing with `python3 -m http.server -d docs`, but don't commit that state.

The build refuses to run if a template names an image, a JSON file or a
taxonomy term that isn't there.

## Adding a template

Export it from the builder on the demo site, then:

```
docs/files/<slug>.json     the exported file
docs/assets/<slug>.jpg     a screenshot, 640px wide
```

and add the matching `[[template]]` block to `templates.toml`. `widget_id` and
`demo` are what build the link back to the demo.

## Preview links

Each card links to `https://fox.heronwp.com/<demo>/?builder_used=…&widget_id=…`.
The query pair used to render that one widget on its own, but Fox Monster's
preview code was never ported to Fox 7.x, so the link currently opens the whole
demo page. The pair is kept so the links come right again if it is restored.
