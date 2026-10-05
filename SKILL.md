---
name: labs-research
description: >
  Menu-driven Binance Alpha research: paste a `0x` CA, confirm Alpha listing vs Spot graduation, show per-module Surf credit estimates, then run only the modules the user selects (insider tree, holders, 72h transfers, confirmed sell-out, LP, funding source, mint authorities, clusters, monitoring export). Before paid calls, print selected vs full-run credits and how much is cut. Outputs wallet tables and important transactions. Use when the user runs `/labs-research`, pastes an Alpha CA and wants a custom module mix, or asks for selectable HertzFlow-style Alpha rounds without a full forensic.
---

# labs-research

Selective Binance Alpha runner on HertzFlow helpers. Python owns SQL, numbers, and credits. You collect the CA, show the catalog, get Y/N, then present `report.md`.

Do not copy the HertzFlow tree. Do not invent module ids or credit numbers — they live in `references/modules.json`. Do not store or echo full `sk-surf-` keys.

## Language

From the user's most recent message:

- CJK (`一-鿿`, kana, hangul) → `--lang zh`, reply in Chinese
- otherwise → `--lang en`, reply in English

## Paths

Skill root = this file's directory. Run the CLI from there (or prefix paths).

| What | Where |
|---|---|
| Catalog (ids, deps, `credits_est`) | `references/modules.json` |
| CLI | `python scripts/labs_research.py` |
| HertzFlow helpers | `$HERTZFLOW_ALPHA_ROOT` or `~/.grok/skills/hertzflow/alpha/v06` |
| Reports | workspace `reports/<ca_lower>/labs-research/` |

Windows: set `PYTHONIOENCODING=utf-8` and `PYTHONUTF8=1`. Do not pipe with `2>&1 | Tee-Object`. Use `python` (or `python3` if that is the interpreter).

## Preflight

1. `surf` on PATH. If missing, install, then continue.
2. `surf auth` shows a saved `sk-` key. If not, prompt for a key **and** show this coupon even when they say they already have one:

   http://agents.asksurf.ai/?coupon=hertzflow

   Persist with `surf auth --api-key <pasted>`. Coupon is signup-only; existing accounts top up at agents.asksurf.ai.
3. HertzFlow helpers exist (`helpers/section_a_scope.py` under the HertzFlow root above). If missing, stop and tell the user to install `/hertzflow`.
4. Python 3.10+.

`PAID_BALANCE_ZERO` on a later call means the key is valid but unpaid — stop and tell them to top up. That is distinct from `UNAUTHORIZED`.

## Flow

Extract a CA with `^0x[a-fA-F0-9]{40}$`. If none, ask. Lowercase it.

If the user already named numbers, module ids, or `all`, skip the pick step and still run estimate → Y/N.

```
python scripts/labs_research.py scope --ca 0x... --out <workspace>/reports/<ca>/labs-research/scope.json --lang {en|zh}
python scripts/labs_research.py menu
python scripts/labs_research.py estimate --modules <numbers or ids or all> --listing <alpha_listing_date_utc> --depth first --window 3 --json
python scripts/labs_research.py run --ca 0x... --modules <numbers or ids or all> --out-dir <workspace>/reports/<ca>/labs-research --lang {en|zh} --depth first --window 3
```

1. **Scope (always first).** Abort on `SPOT_GRADUATED`, `NEVER_ALPHA`, `INVALID_CA`, or missing `scope_ok`. Do not offer paid modules.
2. **Menu.** Run `menu` (human text, not `--json`). Paste that numbered list to the user. Do not rewrite the blurbs. Tell them: reply with **numbers** (example `3, 13, 14`), or `all`. Ids still work.
3. **Switches.** Only if they ticked that round. Defaults if they do not answer: `#3` window **3** days, `#8` depth **first**.
   - `#3` in the mix: ask `window 1, 3, or 7` (days). One SQL call. 7 days is the higher ceiling.
   - `#8` in the mix: ask `depth first or second`. **first** = pre-listing dumpers only. **second** = also follow up to 12 next-hop wallets. Second is the run that can drain a small Surf balance. Do not pick second unless they say second.
4. **Estimate.** Run `estimate --modules <reply> --listing <alpha_listing_date_utc> --depth <first|second> --window <1|3|7> --json`. The selection row is a **ceiling**. Also print `likely_credits_est`, `history_chunks`, `depth`, `anomaly_window_days`, and `estimate_note`. Do not recompute:

   | | Credits | USD |
   |---|---|---|
   | Full default pack | `full_pack_credits_est` | `full_pack_usd_est` |
   | Selection (resolved) | `selected_credits_est` | `selected_usd_est` |
   | **Cut** | `cut_credits_est` (`cut_pct`%) | `cut_usd_est` |
   | Scope gate (always, extra) | `scope_credits_est` | `scope_usd_est` |

   USD rate is `usd_per_credit` in the catalog. Also print `requested_labels` / `auto_included_labels`. Ask **Proceed? (Y/N)**.
5. **Gate.** Wait for Y. N or anything else stops with no paid `run`.
6. **Run.** Only after Y. Foreground, wait for exit. Full pack can take several minutes. `run` also echoes the estimate on stderr, then writes `report.md`, `report.html`, `report.pdf`, `wallets.csv`, `transactions.csv`, `result.json`, and (if `monitoring` is selected) `monitoring_wallets.json` + `monitoring_paste.json`.
7. **Present.** Open `report.md` (same content as the HTML and PDF). Lead with the snapshot, wallets, and transactions. Quote pipeline numbers only. Mention actual `credits_used` vs the estimate. `credits_used` is Surf `meta.credits_used` from SQL **and** raw CLI subprocesses (`token-holders`, labels). Point the user at `report.pdf` and `report.html`. Rebuild from a saved JSON with `python scripts/labs_research.py render --in <result.json>` if the layout needs a refresh without a new Surf run.

## Module rules

- Numbers **17–19** (`wash`, `cross_sym`, `flow_ops`) are catalogued as advanced and **not wired**. If the user picks them, say they are skipped (`advanced_not_wired_use_hertzflow`) and point to `/hertzflow` for a full forensic.
- **#1** is the cheap balance pass unless **#8** is also selected. #8 depth **first** traces at most 5 pre-listing dumpers. Depth **second** adds up to 12 next-hop wallets × the same chunks. Pass the depth they chose. Do not default #8 to second.
- **#3** is one SQL call: 4 credits for 1 or 3 days, 8-credit ceiling for 7 days. Pass `--window`.
- **High-credit rounds:** #8 depth second, then #8 depth first on an old listing, then #9, #10, #11, #13. #5 and #16 are free. #2 is about 4 credits.
- Reuse `scope.json` in the out dir. Do not run `scope` again inside `run` if that file is already there for the same CA.
- Report `credits_used` from the pipeline counter. It includes HertzFlow SQL and raw `surf` subprocess stdout. It does not include a key-probe you ran outside `run`.
- SQL modules skip on holder-snapshot chains (`skipped: surf_no_sql`).
- `anomaly72` is the module that keeps transfer hashes; insider/sell-out are often aggregates. Say so if the tx table is thin.
- Do not start a HertzFlow full forensic unless the user asks for `/hertzflow`.
