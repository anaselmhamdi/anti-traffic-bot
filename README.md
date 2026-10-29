# crawlbill

One-evening validation test for an AI-crawler hosting-bill service. Not a product.

- `site/index.html`: landing page; the CTA opens Tally form `5XXNQo`.
- `site/botcheck.py`: stdlib log checker, served at `/botcheck.py`. Tests: `python3 -m unittest discover tests`.

Deploy: `fly deploy`. Custom domain: `fly certs add crawlbill.anas.link` plus a DNS-only `CNAME crawlbill -> crawlbill.fly.dev`.

Kill criteria: unless several people send real invoices showing crawler-driven overages, close the idea for good.
