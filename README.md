# sfp-corporate-site

Static source for [sustainablefinancepartner.com](https://sustainablefinancepartner.com) — Sustainable Finance Partners, LLC corporate parent site.

For the Phronesis product platform, see [phronesisintel.com](https://phronesisintel.com) (source: [`phronesis-product-site`](https://github.com/sustainable-finance-partners/phronesis-product-site)).

## Layout

```
.
├── index.html                       Home page
├── spec.html                        For-agents technical surface (links to canonical /spec)
├── pricing.json                     Pricing manifest (machine-readable)
├── refund-policy.html
├── privacy-policy.html
├── terms-of-service.html
├── styles.css                       Shared design system (byte-identical with phronesis-product-site)
├── manifest.json                    PWA manifest
├── favicon.svg
├── robots.txt
├── sitemap.xml
└── .well-known/
    ├── agents.txt                   Agent-discovery descriptor
    └── agentic-commerce.json        Agentic-commerce capabilities manifest
```

## Hosting

Cloudflare Pages → custom domain `sustainablefinancepartner.com` (root + `www`). Email path
(`mx.sustainablefinancepartner.com.cust.b.hostedemail.com` MX + SPF + DMARC) preserved at
DNS layer through Cloudflare Pages custom-domain wire — see Sprint 5.4 dispatch §AC-SFP-Site-2.

## Contributing

This is a static-content surface. No build step. Edits land via PR; production deploys
auto-trigger from `main` branch via Cloudflare Pages.
