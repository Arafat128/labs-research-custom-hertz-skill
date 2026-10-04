# labs-research

Menu-driven Binance Alpha research skill. Paste a `0x` contract address, confirm it is Alpha-listed (and not Spot-graduated), pick which forensic modules to run, see how many Surf credits that cuts versus a full default pack, then get a report with wallets and important transactions.

Install:

```bash
npx skills add Arafat128/labs-research-custom-hertz-skill
```

In Grok: `/labs-research` (or paste an Alpha CA and ask for a custom module mix).

## What it needs

- Python 3.10+
- [Surf CLI](https://docs.asksurf.ai/cli/cli) with a paid or credited API key (`surf auth`)
- [HertzFlow](https://github.com/HertzFlow/hertzflow-skills) Alpha helpers (`npx skills add HertzFlow/hertzflow-skills`)

This skill wraps HertzFlow helpers. It does not vendor-copy that tree. Optional override: `HERTZFLOW_ALPHA_ROOT` pointing at `.../hertzflow/alpha/v06`.

New Surf accounts can claim credits at http://agents.asksurf.ai/?coupon=hertzflow (signup-only).

## Flow

1. Scope gate (Alpha vs Spot)
2. Module menu from `references/modules.json`
3. Credit estimate: selected vs full pack vs **cut** (USD at `$0.006` / credit)
4. Proceed Y/N
5. Run only the chosen modules → `report.md` (wallets + txs)

CLI (from this folder):

```bash
python scripts/labs_research.py menu
python scripts/labs_research.py estimate --modules sellout,holders
python scripts/labs_research.py scope --ca 0x... --lang en
python scripts/labs_research.py run --ca 0x... --modules sellout,holders --out-dir ./out --lang en
```

`--modules all` is the default pack (every non-advanced module). Advanced `wash` / `cross_sym` / `flow_ops` are catalogued but not wired; use `/hertzflow` for those.
