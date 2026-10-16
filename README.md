# sfp-corporate-site

Static source for [sustainablefinancepartner.com](https://sustainablefinancepartner.com) — Sustainable Finance Partners, LLC corporate parent site.

For the Phronesis product platform, see [phronesisintel.com](https://phronesisintel.com) (source: [`phronesis-product-site`](https://github.com/sustainable-finance-partners/phronesis-product-site)).

## Layout

Only `site/` is published. The repository root (this README, `.github/`, any operating
notes) is not served by the host.

```
.
├── README.md                            This file (not published)
├── .github/                             CI gates and their scripts (not published)
└── site/                                The published tree (Cloudflare Pages build output directory)
    ├── index.html                       Home page
    ├── 404.html                         Answers every path that matches no file, with status 404
    ├── spec.html                        For-agents technical surface (links to canonical /spec)
    ├── pricing.json                     Pricing manifest (machine-readable)
    ├── llms.txt
    ├── refund-policy.html
    ├── privacy-policy.html
    ├── terms-of-service.html
    ├── styles.css                       Shared design system (byte-identical with phronesis-product-site)
    ├── manifest.json                    PWA manifest
    ├── favicon.svg
    ├── robots.txt
    ├── sitemap.xml
    ├── _headers                         Cloudflare Pages response headers (not served as a file)
    └── .well-known/
        ├── agents.txt                   Agent-discovery descriptor
        └── agentic-commerce.json        Agentic-commerce capabilities manifest
```

`site/404.html` matters: without it Cloudflare Pages treats the site as a single-page app
and answers 200 with `index.html` for every unknown path.

## Hosting

Cloudflare Pages project `sfp-corporate-site`, Git-connected to this repository, build output
directory `site`, no build command → custom domain `sustainablefinancepartner.com` (root +
`www`). Email path (`mx.sustainablefinancepartner.com.cust.b.hostedemail.com` MX + SPF + DMARC)
preserved at DNS layer through Cloudflare Pages custom-domain wire.

The gate `unpublished-paths-404` (in `.github/workflows/static-site-canonical-sync.yml`) probes
each PR's preview deployment, and production after each push to `main`: every tracked file
outside `site/` must answer 404 and every file in `site/` must answer 200 (except `404.html`
and the Pages control files such as `_headers`, which are not served as files). `main` is not
branch-protected, so merge only when that check is green.

## Contributing

This is a static-content surface. No build step. Edits land via PR; production deploys
auto-trigger from `main` branch via Cloudflare Pages.
