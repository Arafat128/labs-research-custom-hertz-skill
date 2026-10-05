# labs-research

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Menu-driven Binance Alpha research for Grok. Paste a contract address, confirm it is still on Alpha (not graduated to Spot), pick the checks you want, see the Surf credit estimate before anything is billed, then get a report with wallets and important transactions.

This is a research workflow. It does not tell you to buy or sell.

## Install

```bash
npx skills add Arafat128/labs-research-custom-hertz-skill
npx skills add HertzFlow/hertzflow-skills
```

In Grok, run `/labs-research`, or paste an Alpha contract and ask for a custom module mix.

## Requirements

- Python 3.10+
- A [Surf](https://agents.asksurf.ai/) account and the [Surf CLI](https://docs.asksurf.ai/cli/cli) (`surf auth`)
- [HertzFlow Alpha helpers](https://github.com/HertzFlow/hertzflow-skills), installed separately

Paid Surf calls run only after you confirm the estimate.

## What you can run

Reply with numbers (for example `3, 13, 14`) or `all`.

| # | Check |
|---|---|
| 1 | Who received tokens before listing |
| 2 | Top holders now |
| 3 | Large transfers (1, 3, or 7 days) |
| 4 | Liquidity and a rough buy-size cap |
| 5 | CEX perpetual listing |
| 6 | When the pool started |
| 7 | Holder roles (pool, deployer, quiet insiders, dump destinations) |
| 8 | Confirmed insider sells |
| 9 | How large wallets received tokens |
| 10 | Mint authorities |
| 11 | High-volume dumpers |
| 12 | Exchange fan-out into many wallets |
| 13 | Hidden wallet groups |
| 14 | Recent spread vs dump-to-exchange |
| 15 | Fresh mints |
| 16 | Watchlist export |

`all` runs 1–16. Wash trading, cross-token whale overlap, and MEV flow are full HertzFlow forensic rounds — use `/hertzflow` for those.

## What you get

1. Alpha vs Spot check. Spot-graduated and never-Alpha tokens stop here.
2. A numbered menu.
3. Credit estimate for your selection versus a full run, before any paid calls.
4. Confirm or cancel.
5. A report: `report.md`, `report.html`, `report.pdf`, plus `wallets.csv` and `transactions.csv`.

## Acknowledgements

Built on [HertzFlow](https://github.com/HertzFlow/hertzflow-skills)'s open-source Alpha research helpers (MIT, Copyright (c) 2026 HertzFlow). Those helpers are installed separately. This repository adds the menu, credit estimate, and report workflow.

## License

[MIT](LICENSE). Copyright (c) 2026 Arafat128.
