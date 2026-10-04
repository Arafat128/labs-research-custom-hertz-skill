#!/usr/bin/env python3
"""labs-research — menu-driven Binance Alpha runner on HertzFlow helpers.

Commands:
  menu                         print module catalog
  estimate --modules a,b       credit estimate vs full default pack
  scope --ca 0x...             Alpha / Spot gate only
  run --ca 0x... --modules a,b --out-dir DIR
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = SKILL_ROOT / "references" / "modules.json"
CA_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
EXPLORER = {
    "bsc": ("https://bscscan.com/address/", "https://bscscan.com/tx/"),
    "ethereum": ("https://etherscan.io/address/", "https://etherscan.io/tx/"),
    "base": ("https://basescan.org/address/", "https://basescan.org/tx/"),
    "arbitrum": ("https://arbiscan.io/address/", "https://arbiscan.io/tx/"),
    "polygon": ("https://polygonscan.com/address/", "https://polygonscan.com/tx/"),
    "optimism": ("https://optimistic.etherscan.io/address/", "https://optimistic.etherscan.io/tx/"),
}


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def module_index(cat: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["id"]: m for m in cat["modules"]}


def number_index(cat: dict[str, Any]) -> dict[int, str]:
    out: dict[int, str] = {}
    for i, m in enumerate(cat["modules"], start=1):
        n = int(m.get("n") or i)
        out[n] = m["id"]
        m["n"] = n
    return out


def _label(m: dict[str, Any]) -> str:
    return f"#{m.get('n')} {m.get('name')}"


def resolve_modules(wanted: list[str], idx: dict[str, dict[str, Any]]) -> list[str]:
    unknown = [w for w in wanted if w not in idx]
    if unknown:
        raise SystemExit(f"unknown module(s): {', '.join(unknown)}")
    ordered_ids = [m["id"] for m in load_catalog()["modules"]]
    seen: set[str] = set()
    out: list[str] = []

    def add(mid: str) -> None:
        if mid in seen:
            return
        for dep in idx[mid].get("depends_on") or []:
            add(dep)
        if mid not in seen:
            seen.add(mid)
            out.append(mid)

    for w in wanted:
        add(w)
    return [i for i in ordered_ids if i in seen]


def default_pack(idx: dict[str, dict[str, Any]]) -> list[str]:
    return [mid for mid, m in idx.items() if m.get("default_on") and not m.get("advanced")]


def module_credits(mid: str, idx: dict[str, dict[str, Any]], resolved: list[str]) -> int:
    """Light estimate unless a sibling in heavy_when is also in the run.

    Insider destination tracing (step 4) is the costly path. It runs only
    when sellout is selected, so the menu number stays the cheap balance pass.
    """
    m = idx[mid]
    triggers = m.get("heavy_when") or []
    if triggers and any(t in resolved for t in triggers) and m.get("credits_est_heavy") is not None:
        return int(m["credits_est_heavy"])
    return int(m["credits_est"])


def estimate(selected: list[str], cat: dict[str, Any]) -> dict[str, Any]:
    idx = module_index(cat)
    resolved = resolve_modules(selected, idx)
    full = resolve_modules(default_pack(idx), idx)
    usd = float(cat["usd_per_credit"])
    sel_cr = sum(module_credits(m, idx, resolved) for m in resolved)
    # Full pack includes sellout, so insider is priced at the heavy trace.
    full_cr = sum(module_credits(m, idx, full) for m in full)
    cut = max(0, full_cr - sel_cr)
    auto = [m for m in resolved if m not in selected]
    scope_cr = int(cat.get("scope_credits_est") or 0)
    return {
        "requested": selected,
        "resolved": resolved,
        "auto_included": auto,
        "selected_credits_est": sel_cr,
        "full_pack_credits_est": full_cr,
        "cut_credits_est": cut,
        "cut_pct": round(100.0 * cut / full_cr, 1) if full_cr else 0.0,
        "selected_usd_est": round(sel_cr * usd, 2),
        "full_pack_usd_est": round(full_cr * usd, 2),
        "cut_usd_est": round(cut * usd, 2),
        "usd_per_credit": usd,
        "scope_credits_est": scope_cr,
        "scope_usd_est": round(scope_cr * usd, 2),
        "selected_plus_scope_credits_est": sel_cr + scope_cr,
        "full_plus_scope_credits_est": full_cr + scope_cr,
        "per_module": [
            {
                "n": idx[m].get("n"),
                "id": m,
                "name": idx[m]["name"],
                "credits_est": module_credits(m, idx, resolved),
                "auto_included": m in auto,
            }
            for m in resolved
        ],
        "requested_labels": [_label(idx[m]) for m in resolved if m in selected],
        "auto_included_labels": [_label(idx[m]) for m in auto],
        "resolved_labels": [_label(idx[m]) for m in resolved],
    }


def find_hertzflow_root() -> Path:
    env = os.environ.get("HERTZFLOW_ALPHA_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env))
    home = Path.home()
    candidates.extend(
        [
            home / ".grok" / "skills" / "hertzflow" / "alpha" / "v06",
            home / ".claude" / "skills" / "hertzflow" / "alpha" / "v06",
        ]
    )
    for p in candidates:
        if (p / "helpers" / "section_a_scope.py").is_file():
            return p
    raise SystemExit(
        "HertzFlow alpha helpers not found. Set HERTZFLOW_ALPHA_ROOT to "
        ".../hertzflow/alpha/v06"
    )


def boot_hertzflow(lang: str) -> Path:
    root = find_hertzflow_root()
    helpers = str(root / "helpers")
    if helpers not in sys.path:
        sys.path.insert(0, helpers)
    os.environ["BINANCE_ALPHA_LANG"] = lang
    from i18n import set_lang

    set_lang(lang)
    return root


def cmd_menu(as_json: bool) -> int:
    cat = load_catalog()
    number_index(cat)
    if as_json:
        print(json.dumps(cat, ensure_ascii=False, indent=2))
        return 0
    usd = cat["usd_per_credit"]
    print("Pick what to run. Reply with numbers (example: 3, 13, 14) or all.")
    print()
    print(
        f"Scope check always runs first (~{cat['scope_credits_est']} cr). "
        f"Needed extras are added automatically. ${usd}/credit."
    )
    print()
    regular = [m for m in cat["modules"] if not m.get("advanced")]
    advanced = [m for m in cat["modules"] if m.get("advanced")]
    for m in regular:
        print(f"{m['n']}. {m['name']}  ·  ~{m['credits_est']} cr")
        print(f"   {m.get('plain') or m.get('what') or ''}")
        print()
    if advanced:
        print("Advanced (not available here — use /hertzflow):")
        print()
        for m in advanced:
            print(f"{m['n']}. {m['name']}  ·  ~{m['credits_est']} cr")
            print(f"   {m.get('plain') or m.get('what') or ''}")
            print()
    idx = module_index(cat)
    full = estimate(default_pack(idx), cat)
    print(
        f"all = everything 1–16  ·  {full['full_pack_credits_est']} cr "
        f"(~${full['full_pack_usd_est']})"
    )
    return 0


def cmd_estimate(modules: str, as_json: bool) -> int:
    cat = load_catalog()
    number_index(cat)
    idx = module_index(cat)
    wanted = _parse_modules(modules, idx, cat)
    est = estimate(wanted, cat)
    if as_json:
        print(json.dumps(est, ensure_ascii=False, indent=2))
        return 0
    print("Credit estimate (before paid run)")
    print()
    print("| | Credits | USD |")
    print("|---|---:|---:|")
    print(f"| Full default pack | {est['full_pack_credits_est']} | ${est['full_pack_usd_est']} |")
    print(f"| Your selection | {est['selected_credits_est']} | ${est['selected_usd_est']} |")
    print(f"| **Cut** | **{est['cut_credits_est']}** | **${est['cut_usd_est']}** |")
    print(
        f"| Scope gate (always, extra) | {est['scope_credits_est']} | "
        f"${est['scope_usd_est']} |"
    )
    print(
        f"| Selection + scope | {est['selected_plus_scope_credits_est']} | "
        f"${round(est['selected_plus_scope_credits_est'] * est['usd_per_credit'], 2)} |"
    )
    print()
    print("You picked: " + ", ".join(est["requested_labels"]))
    if est["auto_included_labels"]:
        print("Also added: " + ", ".join(est["auto_included_labels"]))
    print("Will run: " + ", ".join(est["resolved_labels"]))
    print(f"Cut vs full pack: {est['cut_pct']}%")
    print("Proceed? (Y/N)")
    return 0


def _parse_modules(
    raw: str,
    idx: dict[str, dict[str, Any]],
    cat: dict[str, Any] | None = None,
) -> list[str]:
    raw = (raw or "").strip().lower()
    if raw in ("all", "default", "*"):
        return default_pack(idx)
    parts = [p.strip().lstrip("#") for p in re.split(r"[\s,;]+", raw) if p.strip()]
    if not parts:
        raise SystemExit("no modules given (use --modules 3,13,14 or --modules all)")
    cat = cat or load_catalog()
    nmap = number_index(cat)
    out: list[str] = []
    unknown: list[str] = []
    for p in parts:
        if p.isdigit():
            mid = nmap.get(int(p))
            if mid:
                out.append(mid)
            else:
                unknown.append(p)
        elif p in idx:
            out.append(p)
        else:
            unknown.append(p)
    if unknown:
        raise SystemExit(f"unknown module(s): {', '.join(unknown)}")
    return out


def cmd_scope(ca: str, out: Path | None, lang: str) -> int:
    if not CA_RE.match(ca):
        print("INSUFFICIENT_DATA: CA failed regex ^0x[a-fA-F0-9]{40}$", file=sys.stderr)
        return 2
    boot_hertzflow(lang)
    from section_a_scope import run as section_a_run

    scope = section_a_run(ca.lower())
    payload = json.dumps(scope, ensure_ascii=False, indent=2, default=str)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(payload)
    if not scope.get("scope_ok"):
        return 1
    return 0


def _credit_snap() -> dict[str, Any]:
    try:
        from section_a_scope import _surf_credit_snapshot

        return _surf_credit_snapshot()
    except Exception:
        return {"credits": 0.0, "calls": 0, "seconds": 0.0, "attempts": 0}


def _date_floor(listing_iso: str | None) -> str:
    try:
        from surf_constraints import surf_safe_date_floor

        return surf_safe_date_floor(listing_iso)
    except Exception:
        if listing_iso:
            try:
                ld = date.fromisoformat(listing_iso[:10])
                return (ld - timedelta(days=364)).isoformat()
            except ValueError:
                pass
        return (date.today() - timedelta(days=364)).isoformat()


def _norm(a: str | None) -> str:
    return (a or "").lower()


def _empty_rule11() -> dict[str, Any]:
    return {
        "deployer": None,
        "mint_evt_ref": None,
        "mint_ts": None,
        "pre_launch_receivers": [],
        "quiet_wallets": [],
        "dumper_destinations": {},
        "waves_proposal": [],
        "summary_text": "",
        "_trace_unavailable": True,
    }


def run_selected(
    ca: str,
    modules: list[str],
    lang: str,
    out_dir: Path,
) -> dict[str, Any]:
    from chain_router import (
        UnsupportedChainError,
        get_active_chain,
        requires_holder_snapshot,
        set_active_chain,
        sql_supported,
    )
    from evidence_graph import EvidenceGraph
    from i18n import set_lang
    from section_a_scope import run as section_a_run

    set_lang(lang)
    ca = ca.lower()
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    credits0 = _credit_snap()
    timings: dict[str, float] = {}
    raw: dict[str, Any] = {}
    errors: dict[str, str] = {}
    skipped: dict[str, str] = {}
    eg = EvidenceGraph()

    credit_by_module: dict[str, float] = {}

    def tick(name: str, fn):
        t = time.perf_counter()
        c0 = _credit_snap()
        try:
            val = fn()
            raw[name] = val
            return val
        except Exception as e:
            errors[name] = str(e)[:400]
            raw[name] = {"_error": str(e)[:400]}
            print(f"[{name}] failed: {e}", file=sys.stderr)
            return raw[name]
        finally:
            timings[name] = time.perf_counter() - t
            c1 = _credit_snap()
            spent = round(float(c1.get("credits") or 0) - float(c0.get("credits") or 0), 2)
            credit_by_module[name] = spent
            print(
                f"[timing] {name}: {timings[name]:.1f}s · {spent} cr",
                file=sys.stderr,
                flush=True,
            )

    scope = None
    scope_path = out_dir / "scope.json"
    if scope_path.is_file():
        try:
            cached = json.loads(scope_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = None
        cached_ca = str((cached or {}).get("contract_address") or "").lower()
        if cached and cached.get("scope_ok") and cached_ca == ca:
            scope = cached
            timings["scope"] = 0.0
            credit_by_module["scope"] = 0.0
            print("[scope] reused scope.json (no extra Surf)", file=sys.stderr, flush=True)
    if scope is None:
        scope = tick("scope", lambda: section_a_run(ca))
    if not scope.get("scope_ok"):
        result = {
            "_status": "abort",
            "_reason": scope.get("reason"),
            "_detail": scope.get("detail"),
            "scope": scope,
            "timings": timings,
        }
        _write_result(out_dir, result, lang)
        return result

    chain_id = scope.get("chain_id")
    if not chain_id:
        result = {
            "_status": "abort",
            "_reason": "missing_chain_id",
            "scope": scope,
        }
        _write_result(out_dir, result, lang)
        return result
    try:
        active = set_active_chain(chain_id)
    except UnsupportedChainError as e:
        result = {"_status": "abort", "_reason": "unsupported_chain", "_detail": str(e)}
        _write_result(out_dir, result, lang)
        return result

    holder_snap = requires_holder_snapshot()
    sql_ok = sql_supported()
    listing = scope.get("alpha_listing_date_utc")
    floor = _date_floor(listing)
    want = set(modules)

    def need_sql(mid: str) -> bool:
        return module_index(load_catalog())[mid].get("sql") and not sql_ok

    # --- insider ---
    rule11 = _empty_rule11()
    if "insider" in want:
        if need_sql("insider"):
            skipped["insider"] = "surf_no_sql"
            rule11["_skip_reason"] = "surf_no_sql"
        else:
            import rule_11_backward_trace as r11

            # Step 4 traces every dumper × 90-day chunk (BTW: 15 × 5 = 75 SQL
            # calls). Chips and the holder table only need steps 1–3. Destination
            # tracing runs when confirmed sells (#8) is in the mix.
            skip_step4 = "sellout" not in want
            orig_flat = r11.parallel_run_flat_tasks

            def _flat(fn, tasks, max_workers=8):
                if skip_step4:
                    print(
                        f"[rule_11] step4 skipped ({len(tasks)} destination queries) "
                        "— #8 confirmed sells not selected",
                        file=sys.stderr,
                        flush=True,
                    )
                    return [{"data": []} for _ in tasks]
                return orig_flat(fn, tasks, max_workers=max_workers)

            def _r11():
                r11.parallel_run_flat_tasks = _flat
                try:
                    r = r11.run_backward_trace(
                        ca=ca, alpha_listing_date=listing, evidence_graph=eg
                    )
                finally:
                    r11.parallel_run_flat_tasks = orig_flat
                if "error" in r:
                    r = {**_empty_rule11(), "_error": r.get("error")}
                r["_step4"] = "skipped_no_sellout" if skip_step4 else "ran"
                return r

            rule11 = tick("insider", _r11)

    holders: dict[str, Any] = {"top_holders": []}
    if "holders" in want:
        from section_f_holders import run as holders_run

        holders = tick(
            "holders",
            lambda: holders_run(
                ca=ca,
                listing_date=listing,
                total_supply=scope.get("chain_total_supply_ui") or scope.get("total_supply"),
                limit=50,
                chain_decimals=scope.get("chain_decimals"),
            ),
        )

    liq: dict[str, Any] = {}
    if "liq" in want:
        from section_liq import run as liq_run

        liq = tick(
            "liq",
            lambda: liq_run(
                ca=ca,
                symbol=scope.get("symbol") or "",
                alpha_vol_24h_usd=scope.get("alpha_vol_24h_usd"),
                alpha_price_usd=scope.get("alpha_price_usd"),
                scope_chain_lp=scope.get("chain_lp_realtime"),
                scope_realtime_token_info=scope.get("realtime_token_info"),
                primary_chain=scope.get("primary_chain"),
            ),
        )

    price = (liq or {}).get("current_price_usd") or scope.get("alpha_price_usd")

    if "anomaly72" in want:
        if need_sql("anomaly72"):
            skipped["anomaly72"] = "surf_no_sql"
        else:
            from section_anomaly_72h import run as anom_run

            tick(
                "anomaly72",
                lambda: anom_run(
                    ca=ca, evidence_graph=eg, threshold_token_amount=100_000, price_usd=price
                ),
            )

    if "cex" in want:
        from section_cex_trace import run as cex_run

        tick(
            "cex",
            lambda: cex_run(
                symbol=scope.get("symbol") or "",
                alpha_listing_date=listing or "",
            ),
        )

    if "tge" in want:
        if need_sql("tge"):
            skipped["tge"] = "surf_no_sql"
        else:
            from section_tge import run as tge_run

            tick(
                "tge",
                lambda: tge_run(
                    ca=ca,
                    alpha_listing_ts_ms=scope.get("alpha_listing_ts_ms") or 0,
                    pool_addr=(liq or {}).get("dex_pool_addr"),
                    current_price_usd=price,
                ),
            )

    if "chips" in want:
        from section_alloc import run as alloc_run
        from section_l_distribution import run as dist_run

        def _chips():
            dist = dist_run(
                top_holders=holders.get("top_holders") or [],
                rule11=rule11,
                dex_pool_addr=(liq or {}).get("dex_pool_addr"),
                total_supply=scope.get("total_supply"),
                current_price_usd=price,
                eg=eg,
            )
            alloc = alloc_run(
                total_supply=scope.get("total_supply"),
                circulating_supply=scope.get("circulating_supply"),
                rule11=rule11,
                current_price_usd=price,
                burn_balance=holders.get("burn_balance"),
                burn_pct_of_supply=holders.get("burn_pct_of_supply"),
            )
            return {"distribution": dist, "alloc": alloc}

        tick("chips", _chips)

    if "sellout" in want:
        if need_sql("sellout"):
            skipped["sellout"] = "surf_no_sql"
        else:
            from dump_tracker import run as dump_run

            tick(
                "sellout",
                lambda: dump_run(
                    rule11=rule11,
                    ca=ca,
                    symbol=scope.get("symbol") or "",
                    listing_ts_ms=scope.get("alpha_listing_ts_ms"),
                    listing_date=listing,
                    circulating_supply=scope.get("circulating_supply"),
                    total_supply=scope.get("total_supply"),
                    spot_price_usd=price,
                ),
            )

    if "funding" in want:
        if need_sql("funding"):
            skipped["funding"] = "surf_no_sql"
        else:
            from funding_source_attribution import attribute_funding

            addrs: list[str] = []
            seen: set[str] = set()

            def add_a(a):
                n = _norm(a)
                if n and n not in seen:
                    seen.add(n)
                    addrs.append(n)

            for r in rule11.get("pre_launch_receivers") or []:
                add_a(r.get("addr"))
            for h in (holders.get("top_holders") or [])[:30]:
                add_a(h.get("addr"))
            pools = []
            for v in (scope.get("chain_lp_realtime") or {}).values():
                if isinstance(v, dict) and v.get("top_pool_addr"):
                    pools.append(v["top_pool_addr"])
            tick(
                "funding",
                lambda: attribute_funding(
                    ca=ca,
                    high_value_addrs=addrs,
                    dex_pair_addrs=pools,
                    date_floor=floor,
                    max_addrs=200,
                ),
            )

    if "mint_auth" in want:
        if need_sql("mint_auth"):
            skipped["mint_auth"] = "surf_no_sql"
        else:
            from funding_source_attribution import (
                discover_mint_authorities,
                query_mining_fed_outflows,
            )

            def _ma():
                disco = discover_mint_authorities(
                    ca=ca,
                    date_floor=floor,
                    exclude_addrs=[rule11.get("deployer")] if rule11.get("deployer") else None,
                    top_n=10,
                    min_pct_supply=0.001,
                    total_supply=scope.get("total_supply"),
                )
                auths = [
                    a["addr"]
                    for a in (disco.get("authorities") or [])
                    if a.get("addr") and not a.get("is_excluded")
                ]
                dumps = {}
                if auths:
                    dumps = query_mining_fed_outflows(
                        ca=ca, mining_fed_addrs=auths, date_floor=floor, max_addrs=30
                    )
                return {"authorities": disco, "dumps": dumps}

            tick("mint_auth", _ma)

    if "ht_dumpers" in want:
        if need_sql("ht_dumpers"):
            skipped["ht_dumpers"] = "surf_no_sql"
        else:
            from funding_source_attribution import discover_high_throughput_dumpers

            tick(
                "ht_dumpers",
                lambda: discover_high_throughput_dumpers(
                    ca=ca,
                    date_floor=floor,
                    exclude_addrs=[rule11.get("deployer")] if rule11.get("deployer") else None,
                    min_throughput=1_000_000.0,
                    max_balance_frac=0.05,
                    min_n_tx=1000,
                    top_n=100,
                    total_supply=scope.get("total_supply"),
                ),
            )

    if "cex_fanout" in want:
        if need_sql("cex_fanout"):
            skipped["cex_fanout"] = "surf_no_sql"
        else:
            from funding_source_attribution import discover_cex_fanout_hubs

            tick(
                "cex_fanout",
                lambda: discover_cex_fanout_hubs(
                    ca=ca,
                    date_floor=floor,
                    min_recipients=5,
                    max_recipients=50,
                    min_per_recipient=100_000.0,
                    min_total_out=1_000_000.0,
                    top_n_hubs=30,
                ),
            )

    if "clusters" in want:
        if need_sql("clusters"):
            skipped["clusters"] = "surf_no_sql"
        else:
            from wallet_cluster_graph_detector import discover_wallet_cluster_graph

            def _cl():
                cands = set()
                total = scope.get("total_supply") or 0
                min_bal = total * 0.001 if total else 0
                for h in holders.get("top_holders") or []:
                    addr = h.get("addr")
                    if addr and (not min_bal or (h.get("balance") or 0) >= min_bal):
                        cands.add(_norm(addr))
                fund = raw.get("funding") or {}
                attrs = fund.get("attributions") or {}
                if isinstance(attrs, dict):
                    for a in attrs:
                        cands.add(_norm(a))
                ma = ((raw.get("mint_auth") or {}).get("authorities") or {}).get("authorities") or []
                for a in ma:
                    if a.get("addr"):
                        cands.add(_norm(a["addr"]))
                return discover_wallet_cluster_graph(
                    ca=ca,
                    candidates=sorted(cands),
                    total_supply=total,
                    date_floor=floor,
                    resolve_candidate_labels=True,
                )

            tick("clusters", _cl)

    if "recent_flow" in want:
        if need_sql("recent_flow"):
            skipped["recent_flow"] = "surf_no_sql"
        else:
            from recent_flow_actions import detect_recent_flow_actions

            def _rf():
                ops, cexs, infra = set(), set(), set()
                if rule11.get("deployer"):
                    ops.add(_norm(rule11["deployer"]))
                ma = ((raw.get("mint_auth") or {}).get("authorities") or {}).get("authorities") or []
                for a in ma:
                    if a.get("addr"):
                        ops.add(_norm(a["addr"]))
                for h in holders.get("top_holders") or []:
                    et = (h.get("entity_type") or "").lower()
                    if et == "cex":
                        cexs.add(_norm(h.get("addr")))
                    if et == "dex":
                        infra.add(_norm(h.get("addr")))
                if (liq or {}).get("dex_pool_addr"):
                    infra.add(_norm(liq["dex_pool_addr"]))
                return detect_recent_flow_actions(
                    ca=ca, operator_addrs=ops, cex_addrs=cexs, infra_addrs=infra
                )

            tick("recent_flow", _rf)

    if "recent_mint" in want:
        if need_sql("recent_mint"):
            skipped["recent_mint"] = "surf_no_sql"
        else:
            from recent_mint_events import detect_recent_mint_events

            tick(
                "recent_mint",
                lambda: detect_recent_mint_events(
                    ca=ca,
                    circ_supply=float(scope.get("circulating_supply") or 0),
                ),
            )

    if "wash" in want:
        skipped["wash"] = "advanced_not_wired_use_hertzflow"
    if "cross_sym" in want:
        skipped["cross_sym"] = "advanced_not_wired_use_hertzflow"
    if "flow_ops" in want:
        skipped["flow_ops"] = "advanced_not_wired_use_hertzflow"

    wallets = collect_wallets(raw, rule11, holders, scope)
    txs = collect_txs(eg)
    if "monitoring" in want:
        raw["monitoring"] = {
            "wallets": wallets,
            "n": len(wallets),
        }
        (out_dir / "monitoring_wallets.json").write_text(
            json.dumps(wallets, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        paste = [{"address": w["address"], "name": w.get("label") or w.get("role"), "emoji": "👁"} for w in wallets]
        (out_dir / "monitoring_paste.json").write_text(
            json.dumps(paste, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    credits1 = _credit_snap()
    used = float(credits1.get("credits") or 0) - float(credits0.get("credits") or 0)
    result = {
        "_status": "ok",
        "ca": ca,
        "lang": lang,
        "active_chain": get_active_chain(),
        "holder_snapshot_mode": holder_snap,
        "sql_supported": sql_ok,
        "modules_requested": modules,
        "scope": _jsonable(scope),
        "raw": {k: _jsonable(v) for k, v in raw.items()},
        "wallets": wallets,
        "transactions": txs,
        "errors": errors,
        "skipped": skipped,
        "timings": timings,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        "credits_used": round(used, 2),
        "credits_by_module": credit_by_module,
        "surf_calls": int(credits1.get("calls") or 0) - int(credits0.get("calls") or 0),
        "evidence_graph": eg.to_dict() if hasattr(eg, "to_dict") else {},
    }
    cat = load_catalog()
    result["credit_estimate"] = estimate(modules, cat)
    _write_result(out_dir, result, lang)
    return result


def _jsonable(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items() if k != "evidence_graph"}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


def collect_wallets(
    raw: dict[str, Any],
    rule11: dict[str, Any],
    holders: dict[str, Any],
    scope: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}

    def put(addr: str | None, role: str, **extra: Any) -> None:
        a = _norm(addr)
        if not a or not a.startswith("0x") or len(a) != 42:
            return
        cur = rows.get(a)
        if cur is None:
            rows[a] = {"address": a, "role": role, **extra}
        else:
            if extra.get("why") and extra["why"] not in (cur.get("why") or ""):
                cur["why"] = (cur.get("why") or "") + "; " + extra["why"]
            if role and role not in (cur.get("role") or ""):
                cur["role"] = f"{cur.get('role')},{role}"

    if rule11.get("deployer"):
        put(rule11["deployer"], "deployer", why="mint/deployer")
    for r in rule11.get("pre_launch_receivers") or []:
        dumped = r.get("dumped_pct")
        if dumped is None:
            role = "pre_launch"
        elif dumped <= 0:
            role = "quiet"
        elif dumped >= 95:
            role = "full_dumper"
        else:
            role = "partial_dumper"
        put(
            r.get("addr"),
            role,
            balance=r.get("current_balance"),
            dumped_pct=dumped,
            label=r.get("arkham_label"),
            why="pre-listing receiver",
        )
    for h in holders.get("top_holders") or []:
        put(
            h.get("addr"),
            "holder",
            balance=h.get("balance"),
            pct=h.get("pct_of_total"),
            label=h.get("entity_name") or h.get("entity_type"),
            why="top holder",
        )
    for a in ((raw.get("mint_auth") or {}).get("authorities") or {}).get("authorities") or []:
        put(a.get("addr"), "mint_authority", why="received from 0x0")
    for d in (raw.get("ht_dumpers") or {}).get("dumpers") or []:
        if d.get("is_excluded") or d.get("is_infra"):
            continue
        put(d.get("addr"), "ht_dumper", why="high-throughput cleared allocation")
    for hub in (raw.get("cex_fanout") or {}).get("hubs") or []:
        put(hub.get("addr"), "cex_fanout_hub", why="CEX fan-out hub")
    for cl in (raw.get("clusters") or {}).get("clusters") or []:
        for a in cl.get("addrs") or []:
            put(a, "cluster", why="wallet-cluster graph")
    attrs = (raw.get("funding") or {}).get("attributions") or {}
    if isinstance(attrs, dict):
        for addr, info in attrs.items():
            src = info.get("primary_source") if isinstance(info, dict) else None
            put(addr, "funding", why=f"funding:{src}" if src else "funding source")
    for a in (raw.get("anomaly72") or {}).get("actors") or []:
        put(a, "anomaly72", why="72h large-transfer actor")
    return sorted(rows.values(), key=lambda w: (-(float(w.get("balance") or 0)), w["address"]))


def collect_txs(eg: Any) -> list[dict[str, Any]]:
    out = []
    data = eg.to_dict() if hasattr(eg, "to_dict") else {}
    # EvidenceGraph.to_dict() is a flat {evt_001: {kind, tx_hash, ...}, ...}
    items: list[tuple[str, dict[str, Any]]] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                items.append((str(k), v))
            elif k in ("events", "evt") and isinstance(v, list):
                for i, e in enumerate(v):
                    if isinstance(e, dict):
                        items.append((str(e.get("id") or i), e))
    for eid, e in items:
        if e.get("kind") not in (None, "event"):
            continue
        tx = e.get("tx_hash") or e.get("tx")
        if not tx:
            continue
        out.append(
            {
                "id": e.get("id") or eid,
                "type": e.get("type"),
                "ts": e.get("ts"),
                "from": e.get("from_addr") or e.get("from"),
                "to": e.get("to_addr") or e.get("to"),
                "amount": e.get("amount"),
                "usd": e.get("usd_value"),
                "tx_hash": tx,
            }
        )
    out.sort(key=lambda t: (str(t.get("ts") or ""), str(t.get("id") or "")), reverse=True)
    return out


def _write_result(out_dir: Path, result: dict[str, Any], lang: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    from report_render import write_reports

    write_reports(out_dir, result, lang)


def cmd_run(ca: str, modules: str, out_dir: Path, lang: str) -> int:
    if not CA_RE.match(ca):
        print("INSUFFICIENT_DATA: CA failed regex ^0x[a-fA-F0-9]{40}$", file=sys.stderr)
        return 2
    cat = load_catalog()
    number_index(cat)
    idx = module_index(cat)
    wanted = _parse_modules(modules, idx, cat)
    resolved = resolve_modules(wanted, idx)
    est = estimate(wanted, cat)
    print(json.dumps({"credit_estimate": est}, ensure_ascii=False, indent=2), file=sys.stderr)
    boot_hertzflow(lang)
    result = run_selected(ca, resolved, lang, out_dir)
    if result.get("_status") != "ok":
        return 1
    return 0


def cmd_render(src: Path, out_dir: Path | None) -> int:
    data = json.loads(src.read_text(encoding="utf-8"))
    dest = out_dir or src.parent
    from report_render import write_reports

    write_reports(dest, data, data.get("lang") or "en")
    return 0


def main() -> int:
    _utf8_stdio()
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    ap = argparse.ArgumentParser(description="labs-research selective Alpha runner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_menu = sub.add_parser("menu")
    p_menu.add_argument("--json", action="store_true")

    p_est = sub.add_parser("estimate")
    p_est.add_argument("--modules", required=True)
    p_est.add_argument("--json", action="store_true")

    p_scope = sub.add_parser("scope")
    p_scope.add_argument("--ca", required=True)
    p_scope.add_argument("--out", type=Path, default=None)
    p_scope.add_argument("--lang", default="en", choices=("en", "zh"))

    p_run = sub.add_parser("run")
    p_run.add_argument("--ca", required=True)
    p_run.add_argument("--modules", required=True, help="numbers, ids, or 'all' (e.g. 3,13,14)")
    p_run.add_argument("--out-dir", type=Path, required=True)
    p_run.add_argument("--lang", default="en", choices=("en", "zh"))

    p_render = sub.add_parser("render")
    p_render.add_argument("--in", dest="src", type=Path, required=True)
    p_render.add_argument("--out-dir", type=Path, default=None)

    args = ap.parse_args()
    if args.cmd == "menu":
        return cmd_menu(args.json)
    if args.cmd == "estimate":
        return cmd_estimate(args.modules, args.json)
    if args.cmd == "scope":
        return cmd_scope(args.ca, args.out, args.lang)
    if args.cmd == "run":
        return cmd_run(args.ca, args.modules, args.out_dir, args.lang)
    if args.cmd == "render":
        return cmd_render(args.src, args.out_dir)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
