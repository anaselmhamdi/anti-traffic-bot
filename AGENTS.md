# Agent notes

## Scope

This repo is a time-boxed validation test, not a product. Don't add features, frameworks, a backend or a build step unless the user asks. The success signal is real invoices arriving through the Tally form.

## Layout

- `site/` is served as-is by Caddy. Everything in it is public.
- `site/botcheck.py` must stay stdlib-only, Python 3.9+, one file. Users download and run it on their servers. Add new crawlers to `BOTS`, before broader matches, since the first match wins.
- `tests/test_botcheck.py` holds the unittest tests. Run them with `python3 -m unittest discover tests`.

## Deploy and infra

- Deploy: push to `main`. `.github/workflows/ci.yml` runs the tests, then `flyctl deploy` using the `FLY_API_TOKEN` repo secret (a deploy token scoped to the `crawlbill` app). To deploy by hand: `fly deploy --ha=false --remote-only` (keep a single machine).
- DNS: Cloudflare zone `anas.link`. The `crawlbill` A/AAAA records must stay DNS-only (proxied=false), or the Fly cert breaks.
- The Cloudflare token is account-scoped (`cfat_` prefix). Verify it with `/accounts/{account_id}/tokens/verify`, because `/user/tokens/verify` rejects it with error 6111.

## Secrets

- `.env` (`CLOUDFLARE_API_TOKEN`, `TALLY_API_KEY`) and `~/.cloudflare/credentials` hold credentials. Never print, commit or bake them into the image. `.env` is git- and docker-ignored.
- Load them with `set -a; . .env; set +a`.

## Gotchas

- The Hallmark linter writes `.hallmark/` next to its target. It's ignored by git and docker.
- When you test a new hostname, the local macOS resolver may cache a miss. Use `curl --resolve host:443:66.241.124.100` or `dig @1.1.1.1`.

## Working with the user

Keep replies concise and code comments sparse. Confirm before outward-facing actions: posting in communities, sending email, changing the Tally form, deleting DNS records.
