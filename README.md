# crawlbill

One-evening validation test for an AI-crawler hosting-bill service. Not a product.

Live at https://crawlbill.anas.link (Fly app `crawlbill`, also https://crawlbill.fly.dev).

## What's here

- `site/index.html`: landing page. The CTA opens Tally form [`5XXNQo`](https://tally.so/r/5XXNQo), which collects email, site, host, bills and an invoice upload.
- `site/botcheck.py`: stdlib-only checker for access logs in Combined Log Format. It reports requests, bytes and estimated cost per AI crawler, and is served at `/botcheck.py`.
- `Dockerfile`, `Caddyfile`, `fly.toml`: Caddy serving `site/` on Fly (cdg, a single machine that stops automatically).

## botcheck

```bash
curl -O https://crawlbill.anas.link/botcheck.py
python3 botcheck.py /var/log/nginx/access.log*
zcat access.log.*.gz | python3 botcheck.py - --price-per-gb 0.09 --json
```

## Develop

```bash
python3 -m unittest discover tests
python3 -m http.server -d site 8000
fly deploy --ha=false --remote-only
```

## DNS

`anas.link` is on Cloudflare. `crawlbill` has DNS-only (unproxied) records `A 66.241.124.100` and `AAAA 2a09:8280:1::1d6:373e:0`. The Fly cert is issued by Let's Encrypt and renews automatically.

## Kill criteria

Unless several people send real invoices showing crawler-driven overages, close the idea for good.
