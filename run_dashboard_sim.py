"""
ABIDES Simulation Runner for Dashboard
───────────────────────────────────────
Runs the RMSC04+EKF config, extracts ALL available market data from every
agent's event log, and saves to a pickle for the Streamlit dashboard.

Usage:
    python run_dashboard_sim.py
    python run_dashboard_sim.py --end-time 16:00:00 --seed 42
    python run_dashboard_sim.py --news "00:05:00,ABM,0.85,Company beats earnings"
"""

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from abides_core import abides
from abides_markets.configs.rmsc04_ekf import build_config


# ═══════════════════════════════════════════════════════════════════════
# DATA EXTRACTION
# ═══════════════════════════════════════════════════════════════════════

def extract_comprehensive_price_data(end_state, ticker):
    """
    Extract price data from ALL available sources in the simulation.
    
    Sources:
    1. Exchange order book log (book_log2)
    2. ALL agents' BID_DEPTH / ASK_DEPTH event logs
    3. Order book trade history
    
    Returns a sorted, deduplicated price series.
    """
    price_points = []  # List of (timestamp_ns, bid_cents, ask_cents)
    
    # ── Source 1: Exchange book_log2 ─────────────────────────────────
    exchange = end_state["agents"][0]
    ob = exchange.order_books[ticker]
    for entry in ob.book_log2:
        t = entry["QuoteTime"]
        bids = entry["bids"]
        asks = entry["asks"]
        if len(bids) > 0 and len(asks) > 0:
            bb = bids[0][0]
            ba = asks[0][0]
            if bb > 0 and ba > 0:
                price_points.append((int(t), int(bb), int(ba)))

    source1_count = len(price_points)
    
    # ── Source 2: All agents' spread observations ────────────────────
    for agent in end_state["agents"]:
        agent_bids = []
        agent_asks = []
        for event_time, event_type, event in agent.log:
            if event_type == "BID_DEPTH" and isinstance(event, list) and len(event) > 0:
                price = event[0][0] if isinstance(event[0], (list, tuple)) else event[0]
                if price and price > 0:
                    agent_bids.append((event_time, price))
            elif event_type == "ASK_DEPTH" and isinstance(event, list) and len(event) > 0:
                price = event[0][0] if isinstance(event[0], (list, tuple)) else event[0]
                if price and price > 0:
                    agent_asks.append((event_time, price))
        
        # Pair bids and asks (they always come in pairs from spread responses)
        for i in range(min(len(agent_bids), len(agent_asks))):
            bt, bb = agent_bids[i]
            at, ba = agent_asks[i]
            if bb > 0 and ba > 0:
                price_points.append((int(bt), int(bb), int(ba)))

    source2_count = len(price_points) - source1_count
    
    # ── Source 3: Trade history ──────────────────────────────────────
    trades_extracted = []
    for h in ob.history:
        price = h.get("price")
        qty = h.get("quantity")
        t = h.get("time", 0)
        if price and price > 0 and qty and qty > 0:
            trades_extracted.append({
                "time_ns": t,
                "price": price / 100,
                "quantity": qty,
            })
    
    # ── Deduplicate & Sort ───────────────────────────────────────────
    price_points = list(set(price_points))
    price_points.sort(key=lambda x: x[0])
    
    # Convert to arrays
    if not price_points:
        return {
            "times_ns": [], "best_bids": [], "best_asks": [],
            "mids": [], "spreads": [],
        }, trades_extracted
    
    times_ns = [p[0] for p in price_points]
    best_bids = [p[1] / 100 for p in price_points]
    best_asks = [p[2] / 100 for p in price_points]
    mids = [(p[1] + p[2]) / 200 for p in price_points]
    spreads = [(p[2] - p[1]) / 100 for p in price_points]
    
    print(f"  Source 1 (book_log2):   {source1_count} entries")
    print(f"  Source 2 (agent logs):  {source2_count} entries")
    print(f"  Source 3 (trades):      {len(trades_extracted)} entries")
    print(f"  After dedup:            {len(price_points)} price points")
    
    time_span_sec = (times_ns[-1] - times_ns[0]) / 1e9
    print(f"  Time span:              {time_span_sec:.1f} seconds ({time_span_sec/60:.1f} min)")
    print(f"  Price range:            ${min(mids):.2f} — ${max(mids):.2f}")
    
    return {
        "times_ns": times_ns,
        "best_bids": best_bids,
        "best_asks": best_asks,
        "mids": mids,
        "spreads": spreads,
    }, trades_extracted


def build_ohlcv(times_ns, mids, target_num_candles=80):
    """
    Build OHLCV candles with auto-detected interval.
    
    Instead of a fixed candle interval, we calculate the interval that
    gives roughly `target_num_candles` candles from the available data.
    """
    if not times_ns or not mids or len(times_ns) < 2:
        return pd.DataFrame(), 0
    
    t0 = times_ns[0]
    time_span_ns = times_ns[-1] - t0
    time_span_sec = time_span_ns / 1e9
    
    if time_span_sec <= 0:
        return pd.DataFrame(), 0
    
    # Auto-detect candle interval to get ~target_num_candles candles
    # But ensure at least 2 data points per candle on average
    max_candles = max(1, len(times_ns) // 2)
    num_candles = min(target_num_candles, max_candles)
    interval_ns = max(1, time_span_ns // num_candles)
    interval_sec = interval_ns / 1e9
    
    # Build candles using nanosecond buckets for precision
    df = pd.DataFrame({
        "time_ns": times_ns,
        "price": mids,
    })
    df["bucket"] = ((df["time_ns"] - t0) // interval_ns).astype(int)
    
    ohlcv = df.groupby("bucket").agg(
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("price", "count"),
    )
    
    # Time axis: offset from first data point, in the most readable unit
    if time_span_sec < 120:
        # Sub-2-minute: show seconds
        ohlcv["time_display"] = ohlcv.index * interval_sec
        time_unit = "seconds"
    elif time_span_sec < 7200:
        # Sub-2-hour: show minutes
        ohlcv["time_display"] = ohlcv.index * interval_sec / 60
        time_unit = "minutes"
    else:
        # Longer: show hours
        ohlcv["time_display"] = ohlcv.index * interval_sec / 3600
        time_unit = "hours"
    
    ohlcv = ohlcv.reset_index(drop=True)
    
    print(f"  Candle interval:        {interval_sec:.4f} seconds")
    print(f"  Number of candles:      {len(ohlcv)}")
    print(f"  Time unit:              {time_unit}")
    
    return ohlcv, time_unit


def extract_agent_logs(end_state, ekf_agent_ids):
    """Extract EKF agent event logs with all available internal state."""
    agents_data = {}

    for agent_id in ekf_agent_ids:
        agent = end_state["agents"][agent_id]

        ekf_updates = []
        caution_updates = []
        news_events = []
        holdings_timeline = []

        for event_time, event_type, event in agent.log:
            if event_type == "EKF_UPDATE" and isinstance(event, dict):
                ekf_updates.append({"time_ns": event_time, **event})
            elif event_type == "CAUTION_UPDATE" and isinstance(event, dict):
                caution_updates.append({"time_ns": event_time, **event})
            elif event_type == "NEWS_RECEIVED" and isinstance(event, dict):
                news_events.append({"time_ns": event_time, **event})
            elif event_type == "HOLDINGS_UPDATED" and isinstance(event, dict):
                holdings_timeline.append({
                    "time_ns": event_time,
                    "cash_cents": event.get("CASH", 0),
                    "shares": event.get(agent.symbol if hasattr(agent, 'symbol') else "ABM", 0),
                })

        agents_data[agent_id] = {
            "name": agent.name,
            "ekf_updates": pd.DataFrame(ekf_updates) if ekf_updates else pd.DataFrame(),
            "caution_updates": pd.DataFrame(caution_updates) if caution_updates else pd.DataFrame(),
            "news_events": pd.DataFrame(news_events) if news_events else pd.DataFrame(),
            "holdings_timeline": pd.DataFrame(holdings_timeline) if holdings_timeline else pd.DataFrame(),
            "holdings": dict(agent.holdings) if hasattr(agent, "holdings") else {},
            "price_log": list(agent.price_log) if hasattr(agent, "price_log") else [],
            "time_log": list(agent.time_log) if hasattr(agent, "time_log") else [],
            "x_hat_final": agent.x_hat if hasattr(agent, "x_hat") else None,
            "P_final": agent.P if hasattr(agent, "P") else None,
            "C_t_final": agent.C_t if hasattr(agent, "C_t") else None,
            # Agent hyperparameters (for dashboard display)
            "hyperparams": {
                "beta": round(agent.beta, 2) if hasattr(agent, "beta") else None,
                "er_window": agent.er_window if hasattr(agent, "er_window") else None,
                "delta": round(agent.delta, 4) if hasattr(agent, "delta") else None,
                "lambda_er": round(agent.lambda_er, 2) if hasattr(agent, "lambda_er") else None,
                "sigma_n": round(agent.sigma_n, 1) if hasattr(agent, "sigma_n") else None,
                "gamma": round(agent.gamma, 3) if hasattr(agent, "gamma") else None,
                "k": round(agent.k, 3) if hasattr(agent, "k") else None,
                "mu": round(agent.mu, 4) if hasattr(agent, "mu") else None,
                "news_sensitivity": round(agent.news_sensitivity, 4) if hasattr(agent, "news_sensitivity") else None,
            },
        }

    return agents_data


def extract_oracle_data(oracle, ticker):
    """Extract oracle fundamental value series (all entries)."""
    fund_log = oracle.f_log.get(ticker, [])
    fund_times = [entry["FundamentalTime"] for entry in fund_log]
    fund_values = [entry["FundamentalValue"] / 100 for entry in fund_log]
    return {"times_ns": fund_times, "values": fund_values}


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Run ABIDES simulation for dashboard")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--end-time", type=str, default="16:00:00")
    parser.add_argument("--ticker", type=str, default="ABM")
    parser.add_argument("--num-ekf", type=int, default=5)
    parser.add_argument("--news", type=str, action="append", default=[],
                        help="'time_offset,symbol,sentiment,headline'")
    parser.add_argument("--output", type=str, default="sim_data.pkl")
    args = parser.parse_args()

    # Parse news events
    news_events = []
    for n in args.news:
        parts = n.split(",", 3)
        if len(parts) == 4:
            news_events.append((parts[0], parts[1], float(parts[2]), parts[3]))

    print(f"{'='*60}")
    print(f"ABIDES Dashboard Simulation Runner")
    print(f"{'='*60}")
    print(f"  Seed:       {args.seed}")
    print(f"  End time:   {args.end_time}")
    print(f"  EKF agents: {args.num_ekf}")
    print(f"  News:       {len(news_events)} events")
    print()

    config = build_config(
        seed=args.seed,
        end_time=args.end_time,
        ticker=args.ticker,
        num_ekf_agents=args.num_ekf,
        book_logging=True,
        log_orders=True,
        exchange_log_orders=True,
        stdout_log_level="WARNING",
        news_events=news_events if news_events else None,
    )

    ekf_agent_ids = config["_ekf_agent_ids"]
    print(f"Running simulation ({len(config['agents'])} agents)...")
    end_state = abides.run(config)
    print("Simulation complete!\n")

    # ── Extract ALL data ─────────────────────────────────────────────
    exchange = end_state["agents"][0]
    oracle = exchange.kernel.oracle
    
    # Use the first data point's timestamp as baseline (not market open)
    # This ensures all times are relative and positive
    
    print("Extracting comprehensive price data...")
    book_data, trades = extract_comprehensive_price_data(end_state, args.ticker)
    
    # Determine baseline timestamp
    if book_data["times_ns"]:
        baseline_ns = book_data["times_ns"][0]
    else:
        baseline_ns = int(pd.to_datetime("20210205").value)
    
    print("\nBuilding OHLCV candles...")
    ohlcv, time_unit = build_ohlcv(book_data["times_ns"], book_data["mids"])

    print("\nExtracting agent logs...")
    agents_data = extract_agent_logs(end_state, ekf_agent_ids)

    print("Extracting oracle data...")
    oracle_data = extract_oracle_data(oracle, args.ticker)

    # ── Package ──────────────────────────────────────────────────────
    sim_data = {
        "book": book_data,
        "ohlcv": ohlcv,
        "time_unit": time_unit,
        "agents": agents_data,
        "oracle": oracle_data,
        "trades": trades,
        "baseline_ns": baseline_ns,
        "ticker": args.ticker,
        "seed": args.seed,
        "end_time": args.end_time,
        "ekf_agent_ids": ekf_agent_ids,
        "news_events_input": news_events,
    }

    output_path = Path(args.output)
    with open(output_path, "wb") as f:
        pickle.dump(sim_data, f)

    # ── Summary ──────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DATA SAVED: {output_path.resolve()}")
    print(f"{'='*60}")
    print(f"  Price observations: {len(book_data['times_ns'])}")
    print(f"  OHLCV candles:      {len(ohlcv)}")
    print(f"  Trades:             {len(trades)}")
    print(f"  Oracle points:      {len(oracle_data['times_ns'])}")
    for aid, adata in agents_data.items():
        print(f"  {adata['name']}: {len(adata['ekf_updates'])} EKF, "
              f"{len(adata['caution_updates'])} caution, "
              f"{len(adata['news_events'])} news")
    print(f"\nRun:  streamlit run dashboard.py")


if __name__ == "__main__":
    main()
