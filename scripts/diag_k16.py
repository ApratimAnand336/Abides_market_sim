"""K16 cause classification (spec v1.5 A6.1). For every informed fill outside the bounds
(one-share tolerance, the lab flag's rule): side, |position| increased or not, fill vs limit
price, ratio at the fill and at the limit, own open orders (incl. cancel-pending) at the
order's placement, age of the order. V2=1 runs with informed_budget_v2 on.

    python scripts/diag_k16.py P0-S2 7 13 14 18 19
    V2=1 python scripts/diag_k16.py P0-S2n 3 8 11 14
"""
import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run(cid, seed):
    from abides_core import abides
    from abides_markets.agents.fundamental import INFORMED_W_MAX as WX, INFORMED_W_MIN as WN
    from api import lab
    cfg = lab.lab_config(cid, seed)
    rows, cyc = [], {"n": 0, "stale": 0}
    for a in cfg["agents"]:
        if type(a).__name__ != "FundamentalistAgent" or a.mode != "informed":
            continue
        a.budget_v2 = os.environ.get("V2") == "1"
        a._placed = {}  # order_id -> (time placed, side, limit, qty, stale-open-same-side-at-placement)
        oc = a.informed_cycle

        def cyc_w(_a=a, _oc=oc):
            before = set(_a.orders)
            stale = {True: sum(o.quantity for o in _a.orders.values() if o.side.is_bid()),
                     False: sum(o.quantity for o in _a.orders.values() if not o.side.is_bid())}
            cyc["n"] += 1
            cyc["stale"] += bool(before)
            _oc()
            for oid, o in _a.orders.items():
                if oid not in before:
                    _a._placed[oid] = (_a.current_time, o.side.is_bid(), o.limit_price, o.quantity,
                                       stale[o.side.is_bid()])
        a.informed_cycle = cyc_w
        oe = a.order_executed

        def oe_w(order, _a=a, _oe=oe):
            n0, c0 = _a.holdings.get("ABM", 0), _a.holdings["CASH"]
            _oe(order)
            p = float(order.fill_price)
            n, c = _a.holdings.get("ABM", 0), _a.holdings["CASH"]
            W = c + n * p
            if n * p > WX * W + p + 1e-6 or n * p < WN * W - p - 1e-6:
                pl = _a._placed.get(order.order_id)
                lim = pl[2] if pl else None
                # ratio of the post-fill position valued at the LIMIT price (what §4.5 checked)
                r_lim = None
                if lim:
                    c_lim = c0 - (order.quantity if order.side.is_bid() else -order.quantity) * lim
                    W_l = c_lim + n * lim
                    r_lim = round(n * lim / W_l, 4) if W_l else None
                rows.append(dict(t=round((_a.current_time - cfg["_mkt_open_ns"]) / 1e9), id=_a.id,
                                 buy=order.side.is_bid(), n0=n0, n=n, inc=abs(n) > abs(n0),
                                 r=round(n * p / W,4), p=int(p), lim=lim, r_lim=r_lim,
                                 stale_at_place=pl[4] if pl else None,
                                 age=round((_a.current_time - pl[0]) / 1e9, 1) if pl else None,
                                 known=pl is not None))
        a.order_executed = oe_w
    cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
    try:
        abides.run(cfg)
    finally:
        os.chdir(cwd)
    print(f"== {cid} seed {seed}: {len(rows)} breach fills; cycles {cyc['n']}, with stale open orders {cyc['stale']}")
    for r in rows:
        print("  ", r)


if __name__ == "__main__":
    for s in sys.argv[2:]:
        run(sys.argv[1], int(s))
