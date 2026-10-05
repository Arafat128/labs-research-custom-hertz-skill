"""Structured labs-research reports: Markdown, HTML, and PDF from one layout."""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SKILL_ROOT = Path(__file__).resolve().parent.parent
EXPLORER = {
    "bsc": ("https://bscscan.com/address/", "https://bscscan.com/tx/"),
    "ethereum": ("https://etherscan.io/address/", "https://etherscan.io/tx/"),
    "base": ("https://basescan.org/address/", "https://basescan.org/tx/"),
    "arbitrum": ("https://arbiscan.io/address/", "https://arbiscan.io/tx/"),
    "polygon": ("https://polygonscan.com/address/", "https://polygonscan.com/tx/"),
    "optimism": ("https://optimistic.etherscan.io/address/", "https://optimistic.etherscan.io/tx/"),
}


def _catalog() -> dict[str, dict[str, Any]]:
    path = SKILL_ROOT / "references" / "modules.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data["modules"]}


def _fmt_n(n: Any) -> str:
    if n is None or n == "":
        return "—"
    try:
        x = float(n)
    except (TypeError, ValueError):
        return str(n)
    ax = abs(x)
    if ax >= 1_000_000_000:
        return f"{x/1e9:.2f}B"
    if ax >= 1_000_000:
        return f"{x/1e6:.2f}M"
    if ax >= 1_000:
        return f"{x:,.0f}"
    return f"{x:,.4g}"


def _fmt_usd(n: Any) -> str:
    if n is None or n == "":
        return "—"
    try:
        x = float(n)
    except (TypeError, ValueError):
        return str(n)
    sign = "-" if x < 0 else ""
    ax = abs(x)
    if ax >= 1_000_000:
        return f"{sign}${ax/1e6:.2f}M"
    if ax >= 1_000:
        return f"{sign}${ax:,.0f}"
    if ax >= 1:
        return f"{sign}${ax:,.2f}"
    if ax >= 0.01:
        return f"{sign}${ax:.4f}"
    if ax > 0:
        return f"{sign}${ax:.6f}".rstrip("0").rstrip(".")
    return f"{sign}$0.00"


def _pct(n: Any) -> str:
    if n is None or n == "":
        return "—"
    try:
        return f"{float(n):.2f}%"
    except (TypeError, ValueError):
        return str(n)


def _short(a: str | None) -> str:
    if not a:
        return "—"
    s = str(a)
    return f"{s[:8]}…{s[-4:]}" if len(s) > 14 else s


def _ts(v: Any) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, (int, float)):
        try:
            n = int(v)
            if n > 10_000_000_000:
                n = n // 1000
            return datetime.fromtimestamp(n, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        except (OSError, ValueError, OverflowError):
            return str(v)
    return str(v)[:16]


def _share(balance: Any, stored: Any, total: Any) -> str:
    try:
        p = float(stored) if stored not in (None, "") else None
    except (TypeError, ValueError):
        p = None
    if p and p > 0:
        return f"{p:.2f}%"
    try:
        b = float(balance)
        t = float(total)
    except (TypeError, ValueError):
        return "—"
    if t > 0 and b > 0:
        pct = 100.0 * b / t
        if pct < 0.01:
            return "<0.01%"
        return f"{pct:.2f}%"
    return "—"


def _role(raw: Any) -> str:
    text = str(raw or "—")
    text = text.replace("anomaly72", "72h").replace(",", " · ")
    return text


def _mod_name(mid: str, cat: dict[str, dict[str, Any]]) -> str:
    m = cat.get(mid) or {}
    n = m.get("n")
    name = m.get("name") or mid
    return f"#{n} {name}" if n else name


class Table:
    def __init__(self, headers: list[str], rows: list[list[str]], caption: str = ""):
        self.headers = headers
        self.rows = rows
        self.caption = caption


class Section:
    def __init__(self, title: str):
        self.title = title
        self.bullets: list[str] = []
        self.tables: list[Table] = []
        self.note = ""


def assemble(result: dict[str, Any]) -> dict[str, Any]:
    cat = _catalog()
    scope = result.get("scope") or {}
    chain = result.get("active_chain") or "bsc"
    addr_base, tx_base = EXPLORER.get(chain, EXPLORER["bsc"])
    sym = scope.get("symbol") or "TOKEN"
    name = scope.get("name") or ""
    total = scope.get("total_supply") or scope.get("chain_total_supply_ui")
    sections: list[Section] = []

    if result.get("_status") != "ok":
        s = Section("Stopped")
        s.bullets.append(f"Reason: {result.get('_reason') or 'unknown'}")
        if result.get("_detail"):
            s.bullets.append(str(result.get("_detail"))[:500])
        return {
            "title": f"{sym} {name}".strip(),
            "kicker": "labs-research",
            "ca": result.get("ca") or "",
            "chain": chain,
            "addr_base": addr_base,
            "tx_base": tx_base,
            "sections": [s],
            "wallets": [],
            "transactions": [],
        }

    snap = Section("1. Snapshot")
    price = scope.get("alpha_price_usd")
    chg = scope.get("alpha_percent_change_24h")
    chg_s = f"{float(chg):+.2f}%" if isinstance(chg, (int, float)) else "—"
    snap.bullets = [
        f"{sym} is on Binance Alpha ({scope.get('alpha_listing_date_utc') or 'date unknown'}) and spot status is {scope.get('spot_status') or 'unknown'}.",
        f"Price {_fmt_usd(price)} · 24h {chg_s} · mcap {_fmt_usd(scope.get('alpha_market_cap_usd'))} · FDV {_fmt_usd(scope.get('alpha_fdv_usd'))}.",
        f"Circulating {_fmt_n(scope.get('circulating_supply'))} of {_fmt_n(total)} total.",
    ]
    snap.tables.append(
        Table(
            ["Field", "Value"],
            [
                ["Symbol", f"{sym} · {name}".strip(" ·")],
                ["Contract", result.get("ca") or "—"],
                ["Chain", str(scope.get("chain_label") or chain)],
                ["Alpha listing (UTC)", str(scope.get("alpha_listing_date_utc") or "—")],
                ["Spot", str(scope.get("spot_status") or "—")],
                ["Price", _fmt_usd(price)],
                ["24h change", chg_s],
                ["Market cap", _fmt_usd(scope.get("alpha_market_cap_usd"))],
                ["FDV", _fmt_usd(scope.get("alpha_fdv_usd"))],
                ["Alpha liquidity", _fmt_usd(scope.get("alpha_liquidity_usd"))],
                ["24h volume", _fmt_usd(scope.get("alpha_vol_24h_usd"))],
                ["Holders (Alpha)", _fmt_n(scope.get("alpha_holders"))],
                ["Circulating / total", f"{_fmt_n(scope.get('circulating_supply'))} / {_fmt_n(total)}"],
            ],
        )
    )
    sections.append(snap)

    ran = Section("2. What ran")
    mods = result.get("modules_requested") or []
    ran.bullets.append("Modules: " + ", ".join(_mod_name(m, cat) for m in mods) + ".")
    skipped = result.get("skipped") or {}
    errors = result.get("errors") or {}
    if skipped:
        ran.bullets.append(
            "Skipped: " + ", ".join(f"{_mod_name(k, cat)} ({v})" for k, v in skipped.items()) + "."
        )
    if errors:
        ran.bullets.append(
            "Errors: " + ", ".join(f"{_mod_name(k, cat)}: {v}" for k, v in errors.items()) + "."
        )
    est = result.get("credit_estimate") or {}
    used = result.get("credits_used")
    rate = float(est.get("usd_per_credit") or 0.006)
    used_usd = rate * float(used or 0)
    ran.tables.append(
        Table(
            ["", "Credits", "USD"],
            [
                ["Full default pack (est)", str(est.get("full_pack_credits_est", "—")), f"${est.get('full_pack_usd_est', '—')}"],
                ["Selection (est)", str(est.get("selected_credits_est", "—")), f"${est.get('selected_usd_est', '—')}"],
                [f"Cut (est, {est.get('cut_pct', '—')}%)", str(est.get("cut_credits_est", "—")), f"${est.get('cut_usd_est', '—')}"],
                ["Scope gate (always, extra)", str(est.get("scope_credits_est", "—")), f"${est.get('scope_usd_est', '—')}"],
                ["Actual used", str(used if used is not None else "—"), f"${used_usd:.2f}"],
                ["Elapsed", f"{result.get('elapsed_s', '—')}s", ""],
            ],
            caption="Credits",
        )
    )
    by_mod = result.get("credits_by_module") or {}
    if by_mod:
        rows = [[str(k), str(v)] for k, v in by_mod.items()]
        ran.tables.append(Table(["Module", "Credits used"], rows, caption="Credits by module"))
    if est.get("resolved_labels"):
        ran.bullets.append("Resolved: " + ", ".join(est["resolved_labels"]) + ".")
    elif est.get("auto_included_labels"):
        ran.bullets.append("Also added: " + ", ".join(est["auto_included_labels"]) + ".")
    sections.append(ran)

    wallets = result.get("wallets") or []
    wsec = Section("3. Wallets")
    if not wallets:
        wsec.bullets.append("No wallets were collected from this module mix.")
    else:
        shown = wallets[:40]
        wsec.bullets.append(
            f"{len(wallets)} wallets. Table shows the top {len(shown)} by balance. Full list: wallets.csv."
        )
        wsec.note = "Share is balance ÷ Alpha total supply when the holder snapshot did not return a percent."
        rows = []
        for i, w in enumerate(shown, start=1):
            rows.append(
                [
                    str(i),
                    _role(w.get("role")),
                    str(w.get("address") or "—"),
                    _fmt_n(w.get("balance")),
                    _share(w.get("balance"), w.get("pct"), total),
                    str(w.get("label") or "—"),
                    str(w.get("why") or "—"),
                ]
            )
        wsec.tables.append(
            Table(["#", "Role", "Address", "Balance", "Share", "Label", "Why"], rows)
        )
    sections.append(wsec)

    txs = result.get("transactions") or []
    tsec = Section("4. Transactions")
    if not txs:
        tsec.bullets.append(
            "No transaction hashes in this module mix. Big transfers (#3) is the module that keeps hashes."
        )
    else:
        ranked = sorted(txs, key=lambda t: float(t.get("amount") or 0), reverse=True)
        top = ranked[0]
        tsec.bullets.append(f"{len(txs)} transactions with hashes.")
        tsec.bullets.append(
            f"Largest: {_fmt_n(top.get('amount'))} ({_fmt_usd(top.get('usd'))}) "
            f"{_short(top.get('from'))} → {_short(top.get('to'))} at {_ts(top.get('ts'))} UTC."
        )
        raw_a = (result.get("raw") or {}).get("anomaly72") or {}
        if raw_a.get("n_recent_events") is not None:
            extra = "truncated at the SQL limit" if raw_a.get("was_truncated") else "not truncated"
            tsec.bullets.append(f"Big-transfer count: {raw_a.get('n_recent_events')} ({extra}).")
        shown_tx = txs[:50]
        if len(txs) > len(shown_tx):
            tsec.bullets.append(f"Table shows {len(shown_tx)} newest. Full list: transactions.csv.")
        rows = []
        for t in shown_tx:
            rows.append(
                [
                    _ts(t.get("ts")),
                    str(t.get("type") or "—"),
                    str(t.get("from") or "—"),
                    str(t.get("to") or "—"),
                    _fmt_n(t.get("amount")),
                    _fmt_usd(t.get("usd")),
                    str(t.get("tx_hash") or "—"),
                ]
            )
        tsec.tables.append(
            Table(["Time (UTC)", "Type", "From", "To", "Amount", "USD", "Tx"], rows)
        )
    sections.append(tsec)

    raw = result.get("raw") or {}
    n = 5

    def add(title: str) -> Section:
        nonlocal n
        s = Section(f"{n}. {title}")
        n += 1
        sections.append(s)
        return s

    if "recent_flow" in raw:
        rf = raw["recent_flow"] or {}
        s = add("Last 3 days: spread vs dump-to-exchange")
        s.bullets.append(
            f"Window {rf.get('window_days', 3)} days. A hub needs at least {rf.get('min_counterparties', 10)} counterparties."
        )
        for key, caption in (("fanout", "Spread out (one wallet → many)"), ("consolidation", "Gather in (many → one wallet)")):
            hubs = rf.get(key) or []
            if not hubs:
                s.bullets.append(f"{caption}: none.")
                continue
            rows = []
            for h in hubs[:12]:
                rows.append(
                    [
                        str(h.get("hub") or "—"),
                        _fmt_n(h.get("n_counterparties")),
                        _fmt_n(h.get("n_tx")),
                        _fmt_n(h.get("total_tokens")),
                        str(h.get("kind") or "—"),
                        "yes" if h.get("is_operator") else "no",
                        "yes" if h.get("is_cex") else "no",
                    ]
                )
            s.tables.append(
                Table(
                    ["Hub", "Counterparties", "Txs", "Tokens", "Kind", "Operator", "CEX"],
                    rows,
                    caption=f"{caption} · top {len(rows)} of {len(hubs)}",
                )
            )

    if "clusters" in raw:
        cl = raw["clusters"] or {}
        sm = cl.get("summary") or {}
        s = add("Hidden wallet groups")
        s.bullets.append(
            f"{sm.get('n_clusters', 0)} clusters · {sm.get('n_edges_total', 0)} edges · "
            f"{sm.get('n_candidates_input', 0)} candidates in, {sm.get('n_candidates_post_l1', 0)} after label filter."
        )
        dbg = cl.get("_debug") or {}
        if dbg.get("min_edge_weight_tokens") is not None:
            s.bullets.append(
                f"Edge floor {_fmt_n(dbg.get('min_edge_weight_tokens'))} tokens. "
                f"Date floor {dbg.get('date_floor_clamped') or '—'}."
            )
        groups = cl.get("clusters") or []
        if groups:
            rows = []
            for i, g in enumerate(groups[:15], start=1):
                addrs = g.get("addrs") or g.get("members") or []
                rows.append(
                    [
                        str(i),
                        str(len(addrs)),
                        ", ".join(_short(a) for a in addrs[:6]),
                        _fmt_n(g.get("weight") or g.get("edge_weight")),
                    ]
                )
            s.tables.append(Table(["#", "Wallets", "Members", "Weight"], rows))

    if "insider" in raw:
        r11 = raw["insider"] or {}
        s = add("Who got tokens before listing")
        s.bullets.append(f"Deployer: {r11.get('deployer') or '—'}")
        rec = r11.get("pre_launch_receivers") or []
        quiet = r11.get("quiet_wallets") or []
        s.bullets.append(f"Pre-listing receivers: {len(rec)}. Quiet (unmoved): {len(quiet)}.")
        if r11.get("summary_text"):
            s.note = str(r11["summary_text"])[:800]
        if rec:
            rows = []
            for r in rec[:20]:
                rows.append(
                    [
                        str(r.get("addr") or "—"),
                        _fmt_n(r.get("current_balance")),
                        _pct(r.get("dumped_pct")),
                        str(r.get("arkham_label") or "—"),
                    ]
                )
            s.tables.append(Table(["Address", "Balance", "Moved out", "Label"], rows, "Top receivers"))

    if "sellout" in raw:
        d = raw["sellout"] or {}
        s = add("Confirmed sells")
        if d.get("buckets_complete") is False:
            s.bullets.append("Sell buckets are incomplete. A zero is not proof of no sells.")
        if d.get("push_airdrop_error"):
            err = " ".join(str(d.get("push_airdrop_error")).split())
            s.bullets.append("Surf error on part of sell-out: " + err[:220])
        s.tables.append(
            Table(
                ["Metric", "Value"],
                [
                    ["Insider wallets", str(d.get("insider_n_wallets") if d.get("insider_n_wallets") is not None else "—")],
                    ["CEX tokens", _fmt_n(d.get("confirmed_cex_tokens"))],
                    ["DEX tokens", _fmt_n(d.get("confirmed_dex_tokens"))],
                    ["Confirmed total", f"{_fmt_n(d.get('confirmed_total_tokens'))} ({d.get('confirmed_total_pct') or '—'})"],
                    ["Est. proceeds", _fmt_usd(d.get("confirmed_est_profit_usd"))],
                    ["Net sell-out USD", _fmt_usd(d.get("confirmed_net_sellout_usd"))],
                ],
            )
        )

    if "liq" in raw:
        q = raw["liq"] or {}
        s = add("Liquidity")
        s.tables.append(
            Table(
                ["Metric", "Value"],
                [
                    ["Pool", str(q.get("dex_pool_addr") or "—")],
                    ["Pool LP", _fmt_usd(q.get("dex_pool_liquidity_usd"))],
                    ["5% depth (entry cap)", _fmt_usd(q.get("alpha_5pct_depth_usd_est"))],
                    ["Price", _fmt_usd(q.get("current_price_usd"))],
                ],
            )
        )

    if "cex" in raw:
        c = raw["cex"] or {}
        s = add("CEX futures")
        s.tables.append(
            Table(
                ["Venue", "Listed", "Pair"],
                [
                    ["Tier", str(c.get("tier") or "—"), ""],
                    ["Binance", str(c.get("has_binance_perp")), str(c.get("binance_perp_pair") or "—")],
                    ["Aster", str(c.get("aster_perp_listed")), "—"],
                    ["Bitget", str(c.get("bitget_perp_listed")), "—"],
                ],
            )
        )

    if "funding" in raw:
        fund = raw["funding"] or {}
        sm = fund.get("summary") or {}
        s = add("How big wallets got tokens")
        s.tables.append(
            Table(
                ["Source", "Wallets"],
                [
                    ["Queried", str(sm.get("n_addrs_queried", "—"))],
                    ["With data", str(sm.get("n_addrs_with_data", "—"))],
                    ["Mint", str(sm.get("n_mining_fed", "—"))],
                    ["DEX buy", str(sm.get("n_dex_fed", "—"))],
                    ["Wallet to wallet", str(sm.get("n_p2p_fed", "—"))],
                    ["CEX withdraw", str(sm.get("n_cex_fed", "—"))],
                ],
            )
        )
        attrs = fund.get("attributions") or {}
        if isinstance(attrs, dict) and attrs:
            ranked_a = sorted(
                attrs.items(),
                key=lambda kv: float((kv[1] or {}).get("total") or 0) if isinstance(kv[1], dict) else 0,
                reverse=True,
            )[:15]
            rows = []
            for addr, info in ranked_a:
                info = info if isinstance(info, dict) else {}
                rows.append(
                    [
                        str(addr),
                        str(info.get("primary_source") or "—"),
                        _fmt_n(info.get("total")),
                        _pct((info.get("mint_pct") or 0) * 100 if info.get("mint_pct") is not None else None),
                    ]
                )
            s.tables.append(Table(["Address", "Main source", "Tokens in", "Mint share"], rows, "Largest looked up"))

    if "mint_auth" in raw:
        auths = ((raw["mint_auth"] or {}).get("authorities") or {}).get("authorities") or []
        s = add("Who can mint")
        if not auths:
            s.bullets.append("None found.")
        else:
            rows = []
            for a in auths[:15]:
                rows.append(
                    [
                        str(a.get("addr") or "—"),
                        _fmt_n(a.get("total_minted")),
                        _pct(a.get("mint_pct_supply")),
                        str(a.get("n_mints") if a.get("n_mints") is not None else "—"),
                    ]
                )
            s.tables.append(Table(["Address", "Minted", "% supply", "Mints"], rows))

    if "ht_dumpers" in raw:
        ds = (raw["ht_dumpers"] or {}).get("dumpers") or []
        s = add("High-volume dumpers")
        keep = [d for d in ds if not d.get("is_excluded") and not d.get("is_infra")]
        s.bullets.append(f"{len(keep)} wallets after exclusions.")
        if keep:
            rows = []
            for d in keep[:15]:
                rows.append(
                    [
                        str(d.get("addr") or "—"),
                        _fmt_n(d.get("total_in")),
                        _fmt_n(d.get("balance")),
                        _fmt_n(d.get("n_tx")),
                    ]
                )
            s.tables.append(Table(["Address", "Received", "Balance left", "Txs"], rows))

    if "cex_fanout" in raw:
        fan = raw["cex_fanout"] or {}
        hubs = fan.get("hubs") or []
        err = fan.get("_error")
        dbg = fan.get("_debug") or {}
        sm = fan.get("summary") or {}
        s = add("Exchange split to many wallets")
        if err:
            s.title = s.title + " (PARTIAL)"
            s.bullets.append("0 hubs in the returned data is a gap, not proof of no CEX split.")
            s.bullets.append("Surf error: " + " ".join(str(err).split())[:240])
        trunc = dbg.get("chunk_truncated_p1")
        nchunks = None
        ch = dbg.get("chunks")
        if isinstance(ch, dict):
            nchunks = ch.get("n") or ch.get("n_chunks")
        if trunc:
            s.bullets.append(
                f"{trunc}"
                + (f"/{nchunks}" if nchunks else "")
                + " query chunks hit the row LIMIT. Coverage is incomplete."
            )
        if sm:
            s.bullets.append(
                f"Confirmed hubs: {sm.get('n_confirmed_hubs', '—')}. "
                f"Candidates: {sm.get('n_candidate_hubs', '—')}."
            )
        if not hubs:
            if not err:
                s.bullets.append("None found.")
        else:
            rows = []
            for h in hubs[:12]:
                rows.append(
                    [
                        str(h.get("addr") or "—"),
                        _fmt_n(h.get("n_recipients")),
                        _fmt_n(h.get("total_out_tokens")),
                        str(h.get("cex_source_label") or h.get("cex_source") or "—"),
                    ]
                )
            s.tables.append(Table(["Hub", "Recipients", "Tokens out", "CEX source"], rows))

    if "recent_mint" in raw:
        rm = raw["recent_mint"] or {}
        s = add("Fresh mints")
        s.bullets.append(
            f"Recent significant mint: {'yes' if rm.get('has_recent_significant_mint') else 'no'}."
        )
        days = rm.get("significant_mints") or rm.get("mint_days") or []
        if days:
            rows = []
            for d in days[:12]:
                rows.append(
                    [
                        str(d.get("date") or "—"),
                        _fmt_n(d.get("minted")),
                        _pct(d.get("pct_circ")),
                        str(d.get("n_tx") if d.get("n_tx") is not None else "—"),
                    ]
                )
            s.tables.append(Table(["Date", "Minted", "% circ", "Txs"], rows))

    if "chips" in raw:
        dist = ((raw["chips"] or {}).get("distribution") or {})
        rows_src = dist.get("rows") or dist.get("role_rows") or []
        s = add("Who holds what role")
        if not rows_src:
            s.bullets.append("No role rows in this run.")
        else:
            rows = []
            for r in rows_src[:12]:
                rows.append(
                    [
                        str(r.get("role_label") or r.get("role") or "—"),
                        str(r.get("n_wallets") if r.get("n_wallets") is not None else "—"),
                        _fmt_n(r.get("total_balance") or r.get("balance") or r.get("tokens")),
                        _pct(r.get("pct_of_total") or r.get("pct") or r.get("pct_of_supply")),
                        _fmt_usd(r.get("usd_value")),
                    ]
                )
            s.tables.append(Table(["Role", "Wallets", "Balance", "Share", "USD"], rows))

    lim = add("Limits")
    req = result.get("modules_requested") or []
    ran_ids = [k for k in (result.get("raw") or {}) if not str(k).startswith("_")]
    lim.bullets.append(
        "Requested: " + (", ".join(_mod_name(m, cat) for m in req) if req else "—") + "."
    )
    lim.bullets.append(
        "Ran: " + (", ".join(_mod_name(m, cat) for m in ran_ids) if ran_ids else "—") + "."
    )
    skipped = result.get("skipped") or {}
    errors = result.get("errors") or {}
    if skipped:
        lim.bullets.append(
            "Skipped: " + ", ".join(f"{_mod_name(k, cat)} ({v})" for k, v in skipped.items()) + "."
        )
    else:
        lim.bullets.append("Skipped rounds: none.")
    if errors:
        lim.bullets.append(
            "Module errors: " + ", ".join(f"{_mod_name(k, cat)}: {v}" for k, v in errors.items()) + "."
        )
    caps = result.get("trace_limits") or {}
    r11 = (result.get("raw") or {}).get("insider") or {}
    if r11:
        mode = r11.get("_step4") or "unknown"
        lim.bullets.append(
            f"Insider trace floor {r11.get('trace_floor') or '—'}. "
            f"Destination trace: {mode}."
        )
        promoted = r11.get("n_sub_dumpers_promoted")
        skipped_sub = r11.get("n_sub_dumpers_skipped")
        hop = caps.get("second_hop")
        if hop == "off" or (promoted == 0 and caps.get("step4_subdumpers_cap") == 0):
            lim.bullets.append(
                "First hop included (up to 5 pre-listing wallets that moved ≥10% and received ≥5M). "
                "Second hop was off."
            )
        else:
            lim.bullets.append(
                f"First hop included (up to 5). Second hop promoted {promoted if promoted is not None else '—'} "
                f"and left out {skipped_sub if skipped_sub is not None else '—'} "
                f"({_fmt_n(r11.get('n_sub_dumpers_skipped_tokens'))} tokens not followed)."
            )
        if r11.get("recursion_truncated"):
            lim.bullets.append("Dumper recursion was truncated. Smaller hops are not in the destination list.")
        failed = r11.get("step4_skipped_dumpers") or []
        if failed:
            lim.bullets.append(
                f"{len(failed)} dumpers were not traced because every history chunk errored."
            )
            rows = []
            for row in failed[:20]:
                rows.append(
                    [
                        str(row.get("addr") or "—"),
                        str(row.get("depth") if row.get("depth") is not None else "—"),
                        f"{row.get('errored_chunks', '—')}/{row.get('total_chunks', '—')}",
                    ]
                )
            lim.tables.append(
                Table(["Address", "Hop", "Chunks errored"], rows, "Dumpers not traced")
            )
    sell = (result.get("raw") or {}).get("sellout") or {}
    if sell.get("buckets_complete") is False or sell.get("push_airdrop_error"):
        lim.bullets.append(
            "Confirmed sells did not finish. Zero CEX/DEX totals are a gap, not a finding of no sells."
        )
    if "anomaly72" in raw and caps.get("anomaly_window_days"):
        lim.bullets.append(
            f"Big transfers window: {caps.get('anomaly_window_days')} days "
            f"(Surf block_date lookback {caps.get('anomaly_sql_days') or '—'} days)."
        )
    if not caps and not r11:
        lim.bullets.append("No insider trace on this run, so dumper hops do not apply.")
    lim.note = "17–19 (wash, same whales, MEV) are not available in this skill."

    foot = Section("Notes")
    foot.bullets.append("Numbers are pipeline output from HertzFlow helpers. This report does not set a price target or a buy/sell.")
    foot.bullets.append("Credit estimates live in references/modules.json. Actual Surf spend is the Actual used row.")
    sections.append(foot)

    return {
        "title": f"{sym} · {name}".strip(" ·"),
        "kicker": "labs-research",
        "ca": result.get("ca") or "",
        "chain": chain,
        "addr_base": addr_base,
        "tx_base": tx_base,
        "sections": sections,
        "wallets": wallets,
        "transactions": txs,
    }


def _md_cell(v: str) -> str:
    return str(v).replace("|", "\\|").replace("\n", " ")


def _md_addr(addr: str, base: str) -> str:
    if not addr or not str(addr).startswith("0x") or len(str(addr)) < 10:
        return _md_cell(addr or "—")
    return f"[{_short(addr)}]({base}{addr})"


def render_markdown(doc: dict[str, Any]) -> str:
    lines = [f"# {doc['kicker']} · {doc['title']}", ""]
    if doc.get("ca"):
        lines.append(f"Contract `{doc['ca']}` · chain `{doc['chain']}`")
        lines.append("")
    addr_base = doc["addr_base"]
    tx_base = doc["tx_base"]
    for sec in doc["sections"]:
        lines.append(f"## {sec.title}")
        lines.append("")
        for b in sec.bullets:
            lines.append(f"- {b}")
        if sec.bullets:
            lines.append("")
        if sec.note:
            lines.append(sec.note)
            lines.append("")
        for table in sec.tables:
            if table.caption:
                lines.append(f"**{table.caption}**")
                lines.append("")
            headers = table.headers
            lines.append("| " + " | ".join(headers) + " |")
            lines.append("|" + "|".join("---" for _ in headers) + "|")
            addr_cols = {i for i, h in enumerate(headers) if h.lower() in ("address", "from", "to", "hub", "pool", "contract")}
            tx_cols = {i for i, h in enumerate(headers) if h.lower() in ("tx", "hash")}
            for row in table.rows:
                cells = []
                for i, cell in enumerate(row):
                    text = str(cell)
                    if i in addr_cols:
                        cells.append(_md_addr(text, addr_base))
                    elif i in tx_cols and text.startswith("0x"):
                        cells.append(f"[{_short(text)}]({tx_base}{text})")
                    else:
                        cells.append(_md_cell(text))
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _html_addr(addr: str, base: str) -> str:
    if not addr or not str(addr).startswith("0x") or len(str(addr)) < 10:
        return html.escape(addr or "—")
    label = html.escape(_short(addr))
    href = html.escape(base + addr, quote=True)
    full = html.escape(addr)
    return f'<a href="{href}" title="{full}">{label}</a>'


def render_html(doc: dict[str, Any]) -> str:
    addr_base = doc["addr_base"]
    tx_base = doc["tx_base"]
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8"/>',
        f"<title>{html.escape(doc['kicker'] + ' · ' + doc['title'])}</title>",
        "<style>",
        HTML_CSS,
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        f"<p class='kicker'>{html.escape(doc['kicker'])}</p>",
        f"<h1>{html.escape(doc['title'])}</h1>",
    ]
    if doc.get("ca"):
        parts.append(f"<p class='sub'><code>{html.escape(doc['ca'])}</code> · {html.escape(doc['chain'])}</p>")
    parts.append("</header>")
    parts.append("<nav><ol>")
    for sec in doc["sections"]:
        anchor = "s" + "".join(ch for ch in sec.title if ch.isalnum())
        parts.append(f"<li><a href='#{anchor}'>{html.escape(sec.title)}</a></li>")
    parts.append("</ol></nav>")
    for sec in doc["sections"]:
        anchor = "s" + "".join(ch for ch in sec.title if ch.isalnum())
        parts.append(f"<section id='{anchor}'>")
        parts.append(f"<h2>{html.escape(sec.title)}</h2>")
        if sec.bullets:
            parts.append("<ul>")
            for b in sec.bullets:
                parts.append(f"<li>{html.escape(b)}</li>")
            parts.append("</ul>")
        if sec.note:
            parts.append(f"<p class='note'>{html.escape(sec.note)}</p>")
        for table in sec.tables:
            if table.caption:
                parts.append(f"<p class='cap'>{html.escape(table.caption)}</p>")
            headers = table.headers
            addr_cols = {i for i, h in enumerate(headers) if h.lower() in ("address", "from", "to", "hub", "pool", "contract")}
            tx_cols = {i for i, h in enumerate(headers) if h.lower() in ("tx", "hash")}
            num_cols = {i for i, h in enumerate(headers) if h.lower() in ("balance", "share", "amount", "usd", "tokens", "txs", "counterparties", "credits", "mints", "wallets", "recipients", "received", "minted", "% supply", "% circ", "moved out")}
            parts.append("<div class='wrap'><table>")
            parts.append("<thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr></thead>")
            parts.append("<tbody>")
            for row in table.rows:
                tds = []
                for i, cell in enumerate(row):
                    text = str(cell)
                    cls = " class='num'" if i in num_cols else ""
                    if i in addr_cols:
                        inner = _html_addr(text, addr_base)
                    elif i in tx_cols and text.startswith("0x"):
                        inner = f"<a href='{html.escape(tx_base + text, quote=True)}'>{html.escape(_short(text))}</a>"
                    else:
                        inner = html.escape(text)
                    tds.append(f"<td{cls}>{inner}</td>")
                parts.append("<tr>" + "".join(tds) + "</tr>")
            parts.append("</tbody></table></div>")
        parts.append("</section>")
    parts.append("<footer>labs-research · HertzFlow helper numbers · no price target</footer>")
    parts.append("</body></html>")
    return "\n".join(parts)


HTML_CSS = """
:root { color-scheme: light; }
body { margin: 0 auto; max-width: 980px; padding: 32px 20px 64px; font: 15px/1.45 "Segoe UI", system-ui, sans-serif; color: #1c2430; background: #f6f7f9; }
header, section, nav { background: #fff; border: 1px solid #e3e7ee; border-radius: 10px; padding: 18px 20px; margin: 0 0 14px; }
h1 { font-size: 28px; letter-spacing: -0.03em; margin: 4px 0 0; }
h2 { font-size: 18px; margin: 0 0 10px; }
.kicker { margin: 0; font-size: 12px; letter-spacing: 0.14em; text-transform: uppercase; color: #5c6b80; }
.sub, .note, footer { color: #5c6b80; }
.note { font-size: 13px; }
code, a { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; }
a { color: #0b5cab; text-decoration: none; }
nav ol { margin: 0; padding-left: 18px; columns: 2; }
ul { margin: 0; padding-left: 18px; }
li { margin: 4px 0; }
.cap { font-size: 13px; font-weight: 650; margin: 12px 0 6px; }
.wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border-bottom: 1px solid #e3e7ee; padding: 6px 8px; text-align: left; vertical-align: top; }
th { background: #1c2430; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #f3f6fa; }
td.num, th:nth-child(n) { font-variant-numeric: tabular-nums; }
footer { border: 0; background: transparent; padding: 8px 4px; font-size: 12px; }
@media print {
  body { background: #fff; max-width: none; }
  header, section, nav { break-inside: avoid; box-shadow: none; }
  a { color: #000; }
}
"""


def _pdf(doc: dict[str, Any], path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table as PdfTable,
        TableStyle,
    )

    page = landscape(letter)
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=16, textColor=colors.HexColor("#1c2430"), spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1c2430"), spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("Body", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=12, textColor=colors.HexColor("#1c2430"))
    small = ParagraphStyle("Small", parent=body, fontName="Helvetica", fontSize=7.5, leading=9.5)
    small_b = ParagraphStyle("SmallB", parent=small, fontName="Helvetica-Bold", textColor=colors.white)
    note = ParagraphStyle("Note", parent=body, fontSize=8, textColor=colors.HexColor("#5c6b80"))

    addr_base = doc["addr_base"]
    tx_base = doc["tx_base"]

    def P(text: str, style=small) -> Paragraph:
        safe = (
            html.escape(str(text))
            .replace("\n", " ")
        )
        return Paragraph(safe, style)

    def link_p(label: str, href: str) -> Paragraph:
        return Paragraph(f'<link href="{html.escape(href, quote=True)}">{html.escape(label)}</link>', small)

    story: list[Any] = [
        Paragraph(html.escape(doc["kicker"]).upper(), note),
        Paragraph(html.escape(doc["title"]), h1),
    ]
    if doc.get("ca"):
        story.append(link_p(doc["ca"], addr_base + doc["ca"]))
        story.append(Paragraph(html.escape(doc["chain"]), note))
    story.append(Spacer(1, 8))

    usable = page[0] - 1.1 * inch

    for sec in doc["sections"]:
        block: list[Any] = [Paragraph(html.escape(sec.title), h2)]
        for b in sec.bullets:
            block.append(Paragraph("- " + html.escape(b), body))
        if sec.note:
            block.append(Paragraph(html.escape(sec.note), note))
        for table in sec.tables:
            if not table.rows:
                continue
            if table.caption:
                block.append(Paragraph(html.escape(table.caption), note))
            headers = table.headers
            addr_cols = {i for i, h in enumerate(headers) if h.lower() in ("address", "from", "to", "hub", "pool", "contract")}
            tx_cols = {i for i, h in enumerate(headers) if h.lower() in ("tx", "hash")}
            head = [Paragraph(html.escape(h), small_b) for h in headers]
            data = [head]
            for row in table.rows[:35]:
                cells = []
                for i, cell in enumerate(row):
                    text = str(cell)
                    if i in addr_cols and text.startswith("0x") and len(text) > 14:
                        cells.append(link_p(_short(text), addr_base + text))
                    elif i in tx_cols and text.startswith("0x"):
                        cells.append(link_p(_short(text), tx_base + text))
                    else:
                        cells.append(P(text))
                data.append(cells)
            # Give address-like columns a bit more room, numbers less.
            weights = []
            for h in headers:
                hl = h.lower()
                if hl in ("address", "from", "to", "hub", "why", "members", "label"):
                    weights.append(1.6)
                elif hl in ("#", "share", "role", "kind", "operator", "cex"):
                    weights.append(0.7)
                else:
                    weights.append(1.0)
            scale = usable / sum(weights)
            widths = [w * scale for w in weights]
            grid = PdfTable(data, colWidths=widths, repeatRows=1)
            grid.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2430")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6fa")]),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d5dbe3")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            block.append(Spacer(1, 4))
            block.append(grid)
        story.extend(block)
        story.append(Spacer(1, 6))

    def _page(canvas, doc_):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#5c6b80"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(0.55 * inch, 0.32 * inch, "labs-research · no price target")
        canvas.drawRightString(page[0] - 0.55 * inch, 0.32 * inch, str(doc_.page))
        canvas.restoreState()

    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(path),
        pagesize=page,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title=f"{doc['kicker']} {doc['title']}",
        author="labs-research",
    ).build(story, onFirstPage=_page, onLaterPages=_page)


def _write_csv(path: Path, headers: list[str], rows: list[list[Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def write_reports(out_dir: Path, result: dict[str, Any], lang: str = "en") -> list[Path]:
    del lang  # layout is English; module names come from the catalog
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = assemble(result)
    written = []
    md_path = out_dir / "report.md"
    html_path = out_dir / "report.html"
    pdf_path = out_dir / "report.pdf"
    md_path.write_text(render_markdown(doc), encoding="utf-8")
    html_path.write_text(render_html(doc), encoding="utf-8")
    written.extend([md_path, html_path])
    try:
        _pdf(doc, pdf_path)
        written.append(pdf_path)
    except Exception as e:
        (out_dir / "report_pdf_error.txt").write_text(str(e), encoding="utf-8")
        print(f"[report] pdf failed: {e}")
    scope = result.get("scope") or {}
    total = scope.get("total_supply") or scope.get("chain_total_supply_ui")
    w_rows = [
        [
            w.get("role") or "",
            w.get("address") or "",
            w.get("balance") if w.get("balance") is not None else "",
            _share(w.get("balance"), w.get("pct"), total),
            w.get("label") or "",
            w.get("why") or "",
        ]
        for w in doc["wallets"]
    ]
    _write_csv(out_dir / "wallets.csv", ["role", "address", "balance", "share", "label", "why"], w_rows)
    t_rows = [
        [
            _ts(t.get("ts")),
            t.get("type") or "",
            t.get("from") or "",
            t.get("to") or "",
            t.get("amount") if t.get("amount") is not None else "",
            t.get("usd") if t.get("usd") is not None else "",
            t.get("tx_hash") or "",
        ]
        for t in doc["transactions"]
    ]
    _write_csv(
        out_dir / "transactions.csv",
        ["time_utc", "type", "from", "to", "amount", "usd", "tx_hash"],
        t_rows,
    )
    written.extend([out_dir / "wallets.csv", out_dir / "transactions.csv"])
    for p in written:
        print(f"wrote {p}")
    return written
