"""
Quick-start script to run an ABIDES simulation and visualize the results.

Usage:
    python run_simulation.py

This runs the RMSC03 config (5000 noise + 100 value + 25 momentum + 2 MM + 1 exchange)
for a short window (30 min by default), then plots key market health indicators.

Adjust `end_time` to run longer (e.g., "16:00:00" for a full day — takes ~2-5 min).
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from abides_core import abides
from abides_markets.configs.rmsc04 import build_config


# ══════════════════════════════════════════════════════════════════════
# 1.  RUN THE SIMULATION
# ══════════════════════════════════════════════════════════════════════

print("Building config...")
config = build_config(
    seed=42,
    end_time="16:00:00",        # Full day window (09:30 → 16:00)
    book_logging=True,           # Log order book snapshots at every trade/enter
    log_orders=False,            # Don't log every agent's orders (saves memory)
    exchange_log_orders=True,    # DO log exchange-level activity
    stdout_log_level="WARNING",  # Quieter output
)

print("Running simulation...")
end_state = abides.run(config)
print("Done!\n")


# ══════════════════════════════════════════════════════════════════════
# 2.  EXTRACT DATA FROM THE SIMULATION
# ══════════════════════════════════════════════════════════════════════

# The exchange agent is always index 0
exchange = end_state["agents"][0]
# The order book for our symbol
order_book = exchange.order_books["ABM"]
# The oracle (true fundamental value series)
oracle = exchange.kernel.oracle

# --- 2a. Order Book Log (bid/ask snapshots at every change) ---
book_log = order_book.book_log2  # List of dicts: {QuoteTime, bids, asks}

if not book_log:
    print("WARNING: book_log is empty. Set book_logging=True in config.")
else:
    print(f"Order book snapshots: {len(book_log)}")

# Extract time series from book log
times = []
best_bids = []
best_asks = []
mids = []
spreads = []

for entry in book_log:
    t = entry["QuoteTime"]
    bids = entry["bids"]
    asks = entry["asks"]

    if len(bids) > 0 and len(asks) > 0:
        bb = bids[0][0]   # best bid price (cents)
        ba = asks[0][0]   # best ask price (cents)
        times.append(t)
        best_bids.append(bb / 100)   # convert cents → dollars
        best_asks.append(ba / 100)   # convert cents → dollars
        mids.append((bb + ba) / 200) # mid in dollars
        spreads.append((ba - bb) / 100)  # spread in dollars

# Convert times to seconds from market open for readable x-axis
mkt_open_ns = times[0] if times else 0
times_sec = [(t - mkt_open_ns) / 1e9 for t in times]  # nanoseconds → seconds

# --- 2b. Trade History ---
trade_history = order_book.history
trades = [h for h in trade_history if h["type"] == "EXEC"]
print(f"Total trades executed: {len(trades)}")

# --- 2c. Oracle Fundamental Value Log ---
fund_log = oracle.f_log.get("ABM", [])
print(f"Oracle fundamental value observations: {len(fund_log)}")

fund_times = []
fund_values = []
for entry in fund_log:
    ft = entry["FundamentalTime"]
    fv = entry["FundamentalValue"]
    if ft >= mkt_open_ns:
        fund_times.append((ft - mkt_open_ns) / 1e9)
        fund_values.append(fv / 100)  # cents → dollars


# ══════════════════════════════════════════════════════════════════════
# 3.  PLOT THE RESULTS
# ══════════════════════════════════════════════════════════════════════

fig, axes = plt.subplots(2, 2, figsize=(16, 10))
fig.suptitle("ABIDES Market Simulation — Realism Check", fontsize=16, fontweight="bold")

# ────────────────────────────────────────────────────────────────────
# Plot 1:  Mid-Price vs Fundamental Value
# ────────────────────────────────────────────────────────────────────
ax1 = axes[0, 0]
ax1.plot(times_sec, mids, linewidth=0.5, alpha=0.8, label="Market Mid-Price", color="steelblue")
if fund_values:
    ax1.plot(fund_times, fund_values, linewidth=1.5, alpha=0.7, label="Oracle Fundamental", color="orangered", linestyle="--")
ax1.set_xlabel("Time (seconds from open)")
ax1.set_ylabel("Price ($)")
ax1.set_title("① Price Discovery — Does the market track the fundamental?")
ax1.legend()
ax1.grid(True, alpha=0.3)

# ────────────────────────────────────────────────────────────────────
# Plot 2:  Bid-Ask Spread Over Time
# ────────────────────────────────────────────────────────────────────
ax2 = axes[0, 1]
ax2.plot(times_sec, spreads, linewidth=0.5, alpha=0.7, color="purple")
ax2.set_xlabel("Time (seconds from open)")
ax2.set_ylabel("Spread ($)")
ax2.set_title("② Bid-Ask Spread — Is liquidity healthy?")
ax2.grid(True, alpha=0.3)
# Add mean line
if spreads:
    mean_spread = np.mean(spreads)
    ax2.axhline(y=mean_spread, color="red", linestyle="--", linewidth=1, label=f"Mean: ${mean_spread:.2f}")
    ax2.legend()

# ────────────────────────────────────────────────────────────────────
# Plot 3:  Returns Distribution (should be roughly normal-ish)
# ────────────────────────────────────────────────────────────────────
ax3 = axes[1, 0]
if len(mids) > 1:
    returns = np.diff(np.log(np.array(mids)))  # log returns
    returns = returns[np.isfinite(returns)]      # remove any inf/nan
    ax3.hist(returns, bins=100, density=True, alpha=0.7, color="teal", edgecolor="white")
    ax3.set_xlabel("Log Return")
    ax3.set_ylabel("Density")
    ax3.set_title(f"③ Return Distribution — Fat tails? (Kurtosis: {pd.Series(returns).kurtosis():.2f})")
    ax3.axvline(x=0, color="red", linestyle="--", linewidth=1)
    ax3.grid(True, alpha=0.3)

# ────────────────────────────────────────────────────────────────────
# Plot 4:  Best Bid and Ask with Spread Band
# ────────────────────────────────────────────────────────────────────
ax4 = axes[1, 1]
ax4.fill_between(times_sec, best_bids, best_asks, alpha=0.3, color="skyblue", label="Spread")
ax4.plot(times_sec, best_bids, linewidth=0.5, color="green", alpha=0.6, label="Best Bid")
ax4.plot(times_sec, best_asks, linewidth=0.5, color="red", alpha=0.6, label="Best Ask")
ax4.set_xlabel("Time (seconds from open)")
ax4.set_ylabel("Price ($)")
ax4.set_title("④ Order Book Spread Band — Continuous quoting?")
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.3)

plt.savefig("simulation_results.png", dpi=150, bbox_inches="tight")
print("\nPlot saved to: simulation_results.png")



# ══════════════════════════════════════════════════════════════════════
# 4.  PRINT SUMMARY STATISTICS
# ══════════════════════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("MARKET HEALTH SUMMARY")
print("=" * 60)

if mids:
    print(f"  Price range:          ${min(mids):.2f} — ${max(mids):.2f}")
    print(f"  Opening mid-price:    ${mids[0]:.2f}")
    print(f"  Closing mid-price:    ${mids[-1]:.2f}")

if spreads:
    print(f"  Mean spread:          ${np.mean(spreads):.4f}")
    print(f"  Median spread:        ${np.median(spreads):.4f}")
    print(f"  Max spread:           ${max(spreads):.4f}")
    print(f"  Spread < $0.05 pct:   {100*np.mean(np.array(spreads) < 0.05):.1f}%")

if len(mids) > 1:
    log_returns = np.diff(np.log(np.array(mids)))
    log_returns = log_returns[np.isfinite(log_returns)]
    print(f"  Return mean:          {np.mean(log_returns):.6f}")
    print(f"  Return std:           {np.std(log_returns):.6f}")
    print(f"  Return kurtosis:      {pd.Series(log_returns).kurtosis():.2f}  (normal=0, fat tails>0)")
    print(f"  Return skewness:      {pd.Series(log_returns).skew():.4f}")

print(f"  Total trades:         {len(trades)}")
print(f"  Book snapshots:       {len(book_log)}")

if fund_values:
    # Tracking error: how well does the market track the fundamental?
    # Interpolate fundamental to book log timestamps
    fund_at_book_times = np.interp(
        times_sec,
        fund_times,
        fund_values,
    )
    tracking_error = np.array(mids) - fund_at_book_times
    print(f"  Mean tracking error:  ${np.mean(tracking_error):.4f}")
    print(f"  RMS tracking error:   ${np.sqrt(np.mean(tracking_error**2)):.4f}")

print("=" * 60)
print("\nWhat to look for:")
print("  [OK] Mid-price should loosely follow the oracle fundamental (Plot 1)")
print("  [OK] Spread should be tight and stable (Plot 2) — not widening over time")
print("  [OK] Returns should have slightly fat tails (kurtosis > 0, Plot 3)")
print("  [OK] Bid/ask should be continuously quoted with no large gaps (Plot 4)")
print("  [BAD] signs: spread blowing up, price stuck, no trades, liquidity dropout")
