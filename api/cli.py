"""Command-line export without the server.

    python -m api.cli export --seed 42 --end-time 16:00:00 --num-fund 5 --num-mom 5
    python -m api.cli export --news "01:00:00|0.85|Company beats earnings"

Writes runs/<run_id>.json (reusing the cache when possible) and prints a
summary, including the exchange's EXEC count.
"""

import argparse
import sys
import time

from .jobs import engine_version, execute, make_run_id, payload_path
from .schema import RunParams


def _parse_news(items):
    news = []
    for raw in items:
        parts = raw.split("|", 2)
        if len(parts) != 3:
            raise SystemExit(f"bad --news {raw!r}: expected 'HH:MM:SS|sentiment|headline'")
        news.append({"offset": parts[0], "sentiment": float(parts[1]), "headline": parts[2]})
    return news


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="run a simulation and write its dashboard payload")
    ex.add_argument("--seed", type=int, default=42)
    ex.add_argument("--end-time", default="16:00:00")
    ex.add_argument("--num-fund", type=int, default=5)
    ex.add_argument("--num-mom", type=int, default=5)
    ex.add_argument("--news", action="append", default=[], help="'HH:MM:SS|sentiment|headline'")
    ex.add_argument("--force", action="store_true", help="re-run even if cached")
    args = parser.parse_args(argv)

    params = RunParams(
        seed=args.seed, end_time=args.end_time, num_fund=args.num_fund,
        num_mom=args.num_mom, news=_parse_news(args.news),
    )
    params.check_news_in_session()
    engine = engine_version()
    run_id = make_run_id(params, engine)
    path = payload_path(run_id)
    if path.exists() and not args.force:
        print(f"cached: {path}")
        return 0

    t0 = time.time()
    payload = execute(params, run_id, engine)
    size_mb = path.stat().st_size / 1e6
    print(f"run_id:        {run_id}")
    print(f"engine:        {engine}")
    print(f"written:       {path} ({size_mb:.2f} MB)")
    print(f"wall time:     {time.time() - t0:.1f} s (simulation {payload['meta']['wall_time_s']} s)")
    print(f"EXEC count:    {payload['market']['totals']['trades']}")
    print(f"price points:  {payload['market']['totals']['price_points']}")
    print(f"close:         ${payload['stats']['close']:.2f} ({payload['stats']['change_pct']:+.3f}%)")
    print(f"agents:        {len(payload['agents']['fundamental'])} fundamental, "
          f"{len(payload['agents']['momentum'])} momentum")
    return 0


if __name__ == "__main__":
    sys.exit(main())
