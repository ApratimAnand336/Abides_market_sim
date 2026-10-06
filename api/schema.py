"""Pydantic mirror of the dashboard data contract (web/src/types/payload.ts).

The exporter validates its own output against SimPayload before writing, so
any drift between Python and TypeScript shows up as a failed run, not as a
silently broken chart.

Deviation from the written spec (recorded here and in payload.ts):
NewsRecord.price_after "1m" and "5m" are nullable as well as "30m". A news
item inside the last minute of the session has no 1-minute-after price, and
the dashboard must never invent one.
"""

import re
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator

END_TIMES = ("10:00:00", "11:00:00", "12:00:00", "14:00:00", "16:00:00")
_HMS = re.compile(r"^\d{2}:\d{2}:\d{2}$")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ── Request ───────────────────────────────────────────────────────────────


class NewsItem(Strict):
    offset: str
    headline: str = Field(min_length=1, max_length=200)
    sentiment: float = Field(ge=-1.0, le=1.0)

    @field_validator("offset")
    @classmethod
    def _hms(cls, v: str) -> str:
        if not _HMS.match(v):
            raise ValueError("offset must be HH:MM:SS")
        h, m, s = (int(x) for x in v.split(":"))
        if m > 59 or s > 59:
            raise ValueError("offset must be HH:MM:SS")
        return v


class RunParams(Strict):
    seed: int = Field(ge=0, le=2**31 - 1)
    end_time: Literal["10:00:00", "11:00:00", "12:00:00", "14:00:00", "16:00:00"]
    num_fund: int = Field(ge=0, le=20)
    # the config takes momentum agents from the 12 momentum slots
    num_mom: int = Field(ge=0, le=12)
    news: List[NewsItem] = []

    def session_seconds(self) -> int:
        h, m, s = (int(x) for x in self.end_time.split(":"))
        return (h * 3600 + m * 60 + s) - (9 * 3600 + 30 * 60)

    def check_news_in_session(self) -> None:
        dur = self.session_seconds()
        for n in self.news:
            h, m, s = (int(x) for x in n.offset.split(":"))
            off = h * 3600 + m * 60 + s
            if not 0 < off < dur:
                raise ValueError(
                    f"news offset {n.offset} is outside the session "
                    f"(must be strictly between 00:00:00 and {_fmt_hms(dur)})"
                )

    def normalised(self) -> Dict:
        """Canonical form used for the cache key (news sorted by time)."""
        d = self.model_dump()
        d["news"] = sorted(d["news"], key=lambda n: (n["offset"], n["headline"], n["sentiment"]))
        return d


def _fmt_hms(sec: int) -> str:
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


# ── Payload ───────────────────────────────────────────────────────────────


class Session(Strict):
    open: Literal["09:30:00"]
    close: str
    duration_s: float


class Meta(Strict):
    run_id: str
    params: RunParams
    engine_version: str
    created_at: str
    wall_time_s: float
    ticker: str
    session: Session
    agent_counts: Dict[str, int]


class Quotes(Strict):
    t: List[float]
    bid: List[float]
    ask: List[float]
    mid: List[float]


class Candles(Strict):
    t: List[float]
    o: List[float]
    h: List[float]
    l: List[float]
    c: List[float]
    volume: List[int]
    trades: List[int]


class Series(Strict):
    t: List[float]
    v: List[float]


class Depth(Strict):
    t: List[float]
    bids: List[List[Tuple[float, int]]]
    asks: List[List[Tuple[float, int]]]


class Totals(Strict):
    price_points: int
    trades: int
    volume_shares: int


class Market(Strict):
    quotes: Quotes
    candles_1m: Candles
    oracle: Series
    depth: Depth
    totals: Totals


class SpreadStats(Strict):
    mean: float
    median: float
    p95: float
    max: float


class SpreadTicks(Strict):
    ticks: List[int]
    share: List[float]


class Hist(Strict):
    edges: List[float]
    counts: List[int]


class XY(Strict):
    x: List[float]
    y: List[float]


class Returns1m(Strict):
    n: int
    mean: float
    std: float
    skew: float
    excess_kurtosis: float
    hist: Hist
    normal: XY
    acf: List[float]
    acf_abs: List[float]
    acf_band: float


class ReturnsTick(Strict):
    std: float
    excess_kurtosis: float


class Tracking(Strict):
    rms: float
    mean_abs: float
    corr: float


class MarketStats(Strict):
    open: float
    close: float
    change: float
    change_pct: float
    low: float
    high: float
    spread: SpreadStats
    spread_ticks: SpreadTicks
    returns_1m: Returns1m
    returns_tick: ReturnsTick
    tracking: Tracking
    trades: int
    volume_shares: int


class PriceAfter(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    m1: Optional[float] = Field(alias="1m")
    m5: Optional[float] = Field(alias="5m")
    m30: Optional[float] = Field(alias="30m")


class Reaction(Strict):
    agent_id: int
    kind: Literal["fundamental", "momentum"]
    before: Optional[float]
    after: float
    change_pct: Optional[float]


class EventWindow(Strict):
    t_rel: List[float]
    mid_rel_bps: List[float]


class NewsRecord(Strict):
    t: float
    headline: str
    sentiment: float
    price_before: Optional[float]
    price_after: PriceAfter
    reactions: List[Reaction]
    event_window: EventWindow


class Wealth(Strict):
    cash: float
    shares: int
    value: float


class FinalWealth(Wealth):
    pnl: float
    pnl_pct: float
    exposure_pct: float
    n_orders: int
    n_fills: int


class Holdings(Strict):
    t: List[float]
    cash: List[float]
    shares: List[int]


class Fills(Strict):
    t: List[float]
    side: List[Literal["BUY", "SELL"]]
    qty: List[int]
    price: List[float]


class AgentBase(Strict):
    id: int
    name: str
    hyperparams: Dict[str, float]
    start: Wealth
    final: FinalWealth
    holdings: Holdings
    value_1m: Series
    fills: Fills


class FundEkf(Strict):
    t: List[float]
    mid: List[float]
    x_hat: List[float]
    P: List[float]
    R: List[float]
    K: List[float]
    ER: List[float]
    ER_smooth: List[float]


class FundCaution(Strict):
    t: List[float]
    D: List[float]
    E: List[float]
    C: List[float]


class FundNews(Strict):
    t: float
    headline: str
    sentiment: float
    shift: float
    x_hat_before: float
    x_hat_after: float


class FundamentalAgent(AgentBase):
    kind: Literal["fundamental"]
    ekf: FundEkf
    caution: FundCaution
    news: List[FundNews]


class Thresholds(Strict):
    theta_in: float
    theta_out: float


class MomKf(Strict):
    t: List[float]
    mid: List[float]
    level: List[float]
    band_lo: List[float]
    band_hi: List[float]
    v_hat: List[float]
    T: List[float]
    K0: List[float]
    K1: List[float]
    ER: List[float]
    ER_smooth: List[float]
    epsbar: List[float]
    g_Q: List[float]


class MomCaution(Strict):
    t: List[float]
    C: List[float]
    E: List[float]


class MomState(Strict):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    t: float
    from_: Optional[str] = Field(alias="from")
    to: Literal["NEUTRAL", "BULL", "BEAR", "WATCH"]
    reason: str
    L: Optional[float]
    extreme: Optional[float]


class DecisionCounts(Strict):
    order: int
    dead_band: int
    anti_chase: int
    no_cash: int
    no_shares: int


class DecisionSeries(Strict):
    t: List[float]
    a: List[float]
    s: List[float]
    m: List[float]
    g: List[float]
    e_target: List[float]
    exposure: List[float]
    # optional fields from momentum agent spec v1.1 (exported when present)
    added: Optional[List[Optional[float]]] = None
    exit_pending: Optional[List[Optional[float]]] = None
    sigma_hat2: Optional[List[Optional[float]]] = None
    sigma_tau: Optional[List[Optional[float]]] = None


class Decisions(Strict):
    counts: DecisionCounts
    series: DecisionSeries


class MomNews(Strict):
    t: float
    headline: str
    sentiment: float
    v_hat_after: float


class MomentumAgent(AgentBase):
    kind: Literal["momentum"]
    warmup_end_t: Optional[float]
    thresholds: Thresholds
    kf: MomKf
    caution: MomCaution
    states: List[MomState]
    decisions: Decisions
    news: List[MomNews]


class Agents(Strict):
    fundamental: List[FundamentalAgent]
    momentum: List[MomentumAgent]


class Range(Strict):
    min: float
    max: float
    scale: Optional[Literal["log"]] = None


class SimPayload(Strict):
    schema_version: Literal["1.0"]
    meta: Meta
    market: Market
    stats: MarketStats
    news: List[NewsRecord]
    agents: Agents
    hyperparam_ranges: Dict[Literal["fundamental", "momentum"], Dict[str, Range]]
