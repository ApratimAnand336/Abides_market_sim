"""Write docs/v1.5/PROFILE.md tables (spec v1.5 A1.1, A1.4) from a cProfile stats file
and the timing log (JSON lines: level, rep, out{wall_time_s, execs, holdings}).

    python scripts/profile_report.py runs/_logs/profile_p0_before.pstats \
        runs/_logs/profile_p0_after.pstats runs/_logs/a1_timing.jsonl
Prints markdown to stdout.
"""

import json
import pstats
import statistics
import sys

LEVELS = [
    "v1.4 engine (20465e2)",
    "+ kernel message heap (no locking)",
    "+ logEvent: fast exact copy of plain events",
    "+ debug/info logging guarded (no eager formatting)",
    "+ fmt_ts without pandas",
    "+ get_time_dropout without DataFrame.iterrows",
    "+ no agent-side order deepcopy (A1.2a)",
    "+ sparse depth rows in the lab (A1.2c, 1 s)",
]


def short(k):
    f = k[0].replace("\\", "/")
    for cut in ("abides-jpmc-public/", "Lib/"):
        if cut in f:
            f = f.split(cut, 1)[1]
    return f"{f}:{k[1]}({k[2]})"


def top(path, key, n=15):
    st = pstats.Stats(path)
    total = st.total_tt
    rows = sorted(st.stats.items(), key=lambda kv: -(kv[1][2] if key == "tottime" else kv[1][3]))[:n]
    out = [f"| # | function | calls | own s | cum s | own % |", "|---|---|---|---|---|---|"]
    for i, (k, (cc, nc, tt, ct, _)) in enumerate(rows, 1):
        out.append(f"| {i} | `{short(k)}` | {nc:,} | {tt:.2f} | {ct:.2f} | {100 * tt / total:.1f} |")
    return f"Total profiled time {total:.1f} s.\n\n" + "\n".join(out)


def timing(path):
    by = {}
    hashes = set()
    for line in open(path, encoding="utf-8"):
        d = json.loads(line)
        by.setdefault(d["level"], []).append(d["out"]["wall_time_s"])
        hashes.add((d["out"]["execs"], d["out"]["holdings"], d["out"]["n_execs"]))
    base = statistics.median(by[0])
    out = ["| level | change | runs (s) | median s | vs v1.4 | step |", "|---|---|---|---|---|---|"]
    prev = base
    for lv in sorted(by):
        m = statistics.median(by[lv])
        out.append(f"| {lv} | {LEVELS[lv]} | {', '.join(f'{x:.1f}' for x in by[lv])} | {m:.2f} | "
                   f"{100 * (m - base) / base:+.0f}% | {100 * (m - prev) / prev:+.0f}% |")
        prev = m
    out.append("")
    out.append(f"Distinct (execs, holdings, n_execs) fingerprints over all {sum(len(v) for v in by.values())} runs: "
               f"{len(hashes)} " + ("(all identical)" if len(hashes) == 1 else "(MISMATCH)"))
    return "\n".join(out)


if __name__ == "__main__":
    before, after, tlog = sys.argv[1:4]
    for name, p in (("before (v1.4 engine)", before), ("after (A1)", after)):
        print(f"### Top 15 by own time, {name}\n\n{top(p, 'tottime')}\n")
        print(f"### Top 15 by cumulative time, {name}\n\n{top(p, 'cumulative')}\n")
    print("### Wall time per change\n\n" + timing(tlog))
