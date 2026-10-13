# RMSC-04 + EKF Fundamentalist Agents Configuration
#
# Based on rmsc04.py but replaces 5 of the 102 ValueAgents with our
# custom EKF FundamentalistAgent, replaces 5 of the 12 stock MomentumAgents
# with our MomentumEKFAgent, and adds 1 NewsOracleAgent.
#
# Agent lineup:
#   - 1     Exchange Agent
#   - 1000  Noise Agents
#   - 97    Value Agents (stock ABIDES agents)
#   - 5     FundamentalistAgent (our EKF agents)
#   - 2     Adaptive Market Maker Agents
#   - 7     Momentum Agents (stock ABIDES 20/50 MA crossover)
#   - 5     MomentumEKFAgent (our damped-trend Kalman momentum agents)
#   - 1     NewsOracleAgent

import os
from datetime import datetime

import numpy as np
import pandas as pd

from abides_core.utils import get_wake_time, str_to_ns
from abides_markets.agents import (
    ExchangeAgent,
    NoiseAgent,
    ValueAgent,
    AdaptiveMarketMakerAgent,
    MomentumAgent,
)
from abides_markets.agents.fundamental import FundamentalistAgent
from abides_markets.agents.impact_probe_agent import ImpactProbeAgent
from abides_markets.agents.momentum_ekf import MomentumEKFAgent
from abides_markets.agents.news_oracle_agent import NewsOracleAgent
from abides_markets.configs.param_ranges import (
    FUNDAMENTAL_RANGES as FUND,
    INFORMED_DESIGN_KEYS,
    INFORMED_RANGES as INF,
    MOMENTUM_RANGES as MOM,
    PRICE_LEARNING_LEVELS,
    draw,
)
from abides_markets.models import OrderSizeModel
from abides_markets.oracles import PregeneratedOracle
from abides_markets.utils import generate_latency_model
from abides_markets.utils.budget import GrossLimit


def _oracle_events(events, mkt_open, r_bar):
    """Lab events with "HH:MM:SS" offsets from the open and jumps in % of
    r_bar -> the oracle's {t_ns, cents} / {t0_ns, t1_ns, mult} form."""
    out = []
    for ev in events:
        if ev["type"] == "jump":
            out.append({"type": "jump", "t_ns": mkt_open + str_to_ns(ev["at"]),
                        "cents": float(ev["pct"]) / 100.0 * r_bar})
        elif ev["type"] == "vol":
            out.append({"type": "vol", "t0_ns": mkt_open + str_to_ns(ev["start"]),
                        "t1_ns": mkt_open + str_to_ns(ev["end"]), "mult": float(ev["mult"])})
        else:
            raise ValueError(f"unknown oracle event type {ev['type']!r}")
    return out


def build_config(
    seed=int(datetime.now().timestamp() * 1_000_000) % (2**32 - 1),
    date="20210205",
    end_time="10:00:00",
    stdout_log_level="INFO",
    ticker="ABM",
    starting_cash=10_000_000,  # Cash in this simulator is always in CENTS.
    log_orders=True,
    # 1) Exchange Agent
    book_logging=True,
    book_log_depth=10,
    stream_history_length=500,
    exchange_log_orders=None,
    # 2) Noise Agent
    num_noise_agents=1000,
    # 3) Value Agents (reduced from 102 to make room for EKF agents)
    num_value_agents=97,
    r_bar=100_000,  # true mean fundamental value
    kappa=1.67e-15,
    lambda_a=5.7e-12,
    # oracle
    kappa_oracle=1.67e-16,
    sigma_s=0,
    fund_vol=5e-5,
    megashock_lambda_a=2.77778e-18,
    megashock_mean=1000,
    megashock_var=50_000,
    # 4) Market Maker Agents
    num_mm=2,  # 0..2: how many of the two configured market makers to build
    mm_window_size="adaptive",
    mm_pov=0.025,
    mm_num_ticks=10,
    mm_wake_up_freq="60S",
    mm_min_order_size=1,
    mm_skew_beta=0,
    mm_price_skew=4,
    mm_level_spacing=5,
    mm_spread_alpha=0.75,
    mm_backstop_quantity=0,
    mm_cancel_limit_delay=50,
    mm_max_spread=100,  # cents; normal runs: median 1c, max 53c (v1.1 run B)
    # 5) Momentum Agents
    num_momentum_agents=12,  # total momentum slots (stock + EKF momentum)
    # 6) EKF Fundamentalist Agents
    num_ekf_agents=5,
    ekf_initial_exposure=0.5,
    # 6b) EKF Momentum Agents (take num_mom_ekf_agents of the momentum slots)
    num_mom_ekf_agents=5,
    mom_ekf_initial_exposure=0.5,
    # 7) News events: list of (time_offset_str, symbol, sentiment, headline)
    news_events=None,
    # 8) Realism-lab scenario switches (spec v1.3 Part 6). Every default is
    #    inert: the market is bit-identical to v1.2 (invariant I8).
    #    oracle_events: [{"type": "jump", "at": "HH:MM:SS", "pct": float},
    #                    {"type": "vol", "start": "HH:MM:SS", "end": "HH:MM:SS",
    #                     "mult": float}], offsets from the 09:30 open, jumps
    #                   in % of r_bar. None -> path source "synthetic_ou".
    oracle_events=None,
    #    probe: {"side": "BUY"|"SELL", "quantity": int, "start": "HH:MM:SS"
    #            (offset from the open), "duration_s": 300,
    #            "child_interval_s": 10}. None -> no probe agent.
    probe=None,
    #    mm_pause_windows: [("HH:MM:SS", "HH:MM:SS"), ...] CLOCK times
    #            [start, end) in which both market makers pull their orders
    #            and do not quote. None -> no pause.
    mm_pause_windows=None,
    #    mom_capital_mult: our MomentumEKFAgents start with
    #            starting_cash * mom_capital_mult (endowment rule unchanged).
    mom_capital_mult=1.0,
    # 9) spec v1.4 Part 5 (K10): gross budget limit for the stock ABIDES
    #    agents (Noise, Value, ABIDES Momentum; market makers exempt in R3).
    #    None -> no limit (I8). {"L": 2.0} -> GrossLimit(2.0). No RNG draw.
    abides_budget=None,
    # 10) spec v1.4 Part 4: "price_only" (v1.3, I8) or "informed". informed
    #     needs informed_design = {"T_r_range_s": [lo, hi], "sigma_r_range_c":
    #     [lo, hi], "wealth_c": int}. The count stays num_ekf_agents.
    fund_mode="price_only",
    informed_design=None,
):
    np.random.seed(seed)

    mm_wake_up_freq = str_to_ns(mm_wake_up_freq)

    ORDER_SIZE_MODEL = OrderSizeModel()
    MM_PARAMS = [
        (mm_window_size, mm_pov, mm_num_ticks, mm_wake_up_freq, mm_min_order_size),
        (mm_window_size, mm_pov, mm_num_ticks, mm_wake_up_freq, mm_min_order_size),
    ]
    assert 0 <= num_mm <= len(MM_PARAMS), f"num_mm must be in 0..{len(MM_PARAMS)}"
    MM_PARAMS = MM_PARAMS[:num_mm]
    NUM_MM = len(MM_PARAMS)
    SIGMA_N = r_bar / 100

    DATE = int(pd.to_datetime(date).value)
    MKT_OPEN = DATE + str_to_ns("09:30:00")
    MKT_CLOSE = DATE + str_to_ns(end_time)
    NOISE_MKT_OPEN = MKT_OPEN - str_to_ns("00:30:00")
    NOISE_MKT_CLOSE = DATE + str_to_ns("16:00:00")

    symbols = {
        ticker: {
            "r_bar": r_bar,
            "kappa": kappa_oracle,
            "sigma_s": sigma_s,
            "fund_vol": fund_vol,
            "megashock_lambda_a": megashock_lambda_a,
            "megashock_mean": megashock_mean,
            "megashock_var": megashock_var,
            "path_source": "synthetic_ou",
            "random_state": np.random.RandomState(
                seed=np.random.randint(low=0, high=2**31)
            ),
        }
    }
    if oracle_events is not None:
        # spec v1.3 §6.1: same draws, scripted events (no global RNG used)
        symbols[ticker]["path_source"] = "scenario"
        symbols[ticker]["events"] = _oracle_events(oracle_events, MKT_OPEN, r_bar)

    # Spec v1.2 Part 3: the whole true-value path (to 16:00, whatever end_time
    # is) is generated here from the symbol's own RandomState, drawn before any
    # agent, so it is identical across agent counts, news and session length.
    oracle = PregeneratedOracle(MKT_OPEN, NOISE_MKT_CLOSE, symbols, grid_s=1.0)

    agent_count, agents, agent_types = 0, [], []

    # ── 1. Exchange Agent ────────────────────────────────────────────────
    agents.extend(
        [
            ExchangeAgent(
                id=0,
                name="EXCHANGE_AGENT",
                type="ExchangeAgent",
                mkt_open=MKT_OPEN,
                mkt_close=MKT_CLOSE,
                symbols=[ticker],
                book_logging=book_logging,
                book_log_depth=book_log_depth,
                log_orders=exchange_log_orders,
                pipeline_delay=0,
                computation_delay=0,
                stream_history=stream_history_length,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
        ]
    )
    agent_types.extend("ExchangeAgent")
    agent_count += 1

    # ── 2. Noise Agents ──────────────────────────────────────────────────
    agents.extend(
        [
            NoiseAgent(
                id=j,
                name="NoiseAgent {}".format(j),
                type="NoiseAgent",
                symbol=ticker,
                starting_cash=starting_cash,
                wakeup_time=get_wake_time(NOISE_MKT_OPEN, NOISE_MKT_CLOSE),
                log_orders=log_orders,
                order_size_model=ORDER_SIZE_MODEL,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
            for j in range(agent_count, agent_count + num_noise_agents)
        ]
    )
    agent_count += num_noise_agents
    agent_types.extend(["NoiseAgent"])

    # ── 3. Value Agents (stock ABIDES fundamentalists) ───────────────────
    agents.extend(
        [
            ValueAgent(
                id=j,
                name="Value Agent {}".format(j),
                type="ValueAgent",
                symbol=ticker,
                starting_cash=starting_cash,
                sigma_n=SIGMA_N,
                r_bar=r_bar,
                kappa=kappa,
                lambda_a=lambda_a,
                log_orders=log_orders,
                order_size_model=ORDER_SIZE_MODEL,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
            for j in range(agent_count, agent_count + num_value_agents)
        ]
    )
    agent_count += num_value_agents
    agent_types.extend(["ValueAgent"])

    # ── 4. EKF Fundamentalist Agents (OUR custom agents) ─────────────────
    #    Each agent gets randomized hyperparameters for heterogeneity.
    #    This creates agents with genuinely different "personalities":
    #      - different memory lengths (er_window)
    #      - different noise sensitivity (delta)
    #      - different trust in the market (lambda_er)
    #      - different oracle noise (sigma_n)
    #      - different emotional memory (gamma)
    #      - different safety margins (mu)
    assert fund_mode in ("price_only", "informed"), f"unknown fund_mode {fund_mode!r}"
    if fund_mode == "informed":
        assert informed_design is not None and set(INFORMED_DESIGN_KEYS) <= set(informed_design), \
            f"fund_mode='informed' needs informed_design with {INFORMED_DESIGN_KEYS}"
        _T = (*informed_design["T_r_range_s"], "log")
        _S = (*informed_design["sigma_r_range_c"], "log")
        _PL = informed_design.get("price_learning", "off")  # spec v1.4.1 §2.3
        assert _PL in PRICE_LEARNING_LEVELS, f"unknown price_learning {_PL!r}"
    ekf_start_id = agent_count
    for j in range(agent_count, agent_count + num_ekf_agents):
        # ── Randomized EKF Hyperparameters ──────────────────
        # (ranges in param_ranges.py; the dict is built in this order, which
        #  fixes the draw order: keep it unchanged)
        fkw = dict(
            er_window=draw(FUND, "er_window"),
            delta=draw(FUND, "delta"),
            lambda_er=draw(FUND, "lambda_er"),
            sigma_n=draw(FUND, "sigma_n"),
            initial_uncertainty=draw(FUND, "initial_uncertainty"),
            # ── Randomized Caution Parameters ───────────────────
            gamma=draw(FUND, "gamma"),
            k=draw(FUND, "k"),
            # ── Randomized Limit Price Parameters ───────────────
            mu=draw(FUND, "mu"),
            # ── spec v1.1: process noise, sizing, news ──────────
            q=draw(FUND, "q"),
            a_max=draw(FUND, "a_max"),
            z0=draw(FUND, "z0"),
            s_max=draw(FUND, "s_max"),
            b_f=draw(FUND, "b_f"),
            k_news=draw(FUND, "k_news"),
        )
        cash_j = starting_cash
        if fund_mode == "informed":
            # spec v1.4 §4.6: after the agent's FUNDAMENTAL_RANGES draws,
            # before its RandomState seed; then the design's T_r and sigma_r
            fkw.update(
                mode="informed",
                wake_mean=draw(INF, "wake_mean"),
                rho=draw(INF, "rho"),
                m0=draw(INF, "m0"),
                kappa_m=draw(INF, "kappa_m"),
                h0=draw(INF, "h0"),
                theta_q=draw(INF, "theta_q"),
                T_r=draw({"T_r": _T}, "T_r"),
                sigma_r=draw({"sigma_r": _S}, "sigma_r"),
            )
            if _PL != "off":  # spec v1.4.1 §2.3: after all other informed draws
                lv = PRICE_LEARNING_LEVELS[_PL]
                fkw.update(price_learning=_PL, n_pl=lv["n_pl"],
                           eps_thr=draw(lv, "eps_thr"), a_pl=draw(lv, "a_pl"))
            cash_j = int(informed_design["wealth_c"])
        agents.append(
            FundamentalistAgent(
                id=j,
                name="EKF_Fund_{}".format(j),
                type="EKF_Fundamentalist",
                symbol=ticker,
                starting_cash=cash_j,
                log_orders=True,  # Always log our agents
                wake_up_freq=str_to_ns("10S"),
                **fkw,
                # ── Initial share endowment ─────────────────────────
                initial_exposure=ekf_initial_exposure,
                reference_price=r_bar,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
        )
    agent_count += num_ekf_agents
    agent_types.extend(["EKF_Fundamentalist"])

    # ── 5. Market Maker Agents ───────────────────────────────────────────
    agents.extend(
        [
            AdaptiveMarketMakerAgent(
                id=j,
                name="ADAPTIVE_POV_MARKET_MAKER_AGENT_{}".format(j),
                type="AdaptivePOVMarketMakerAgent",
                symbol=ticker,
                starting_cash=starting_cash,
                pov=MM_PARAMS[idx][1],
                min_order_size=MM_PARAMS[idx][4],
                window_size=MM_PARAMS[idx][0],
                num_ticks=MM_PARAMS[idx][2],
                wake_up_freq=MM_PARAMS[idx][3],
                poisson_arrival=True,
                cancel_limit_delay=mm_cancel_limit_delay,
                skew_beta=mm_skew_beta,
                price_skew_param=mm_price_skew,
                level_spacing=mm_level_spacing,
                spread_alpha=mm_spread_alpha,
                backstop_quantity=mm_backstop_quantity,
                # spec v1.2 Part 4: quote around r_bar until a book exists
                cold_start_price=r_bar,
                # v1.2: stop the self-referential spread runaway (see agent)
                max_spread=mm_max_spread,
                # spec v1.3 §6.3 (lab scenario S6); None = no pause
                pause_windows=(
                    [(DATE + str_to_ns(s), DATE + str_to_ns(e)) for s, e in mm_pause_windows]
                    if mm_pause_windows else None
                ),
                log_orders=log_orders,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
            for idx, j in enumerate(range(agent_count, agent_count + NUM_MM))
        ]
    )
    agent_count += NUM_MM
    agent_types.extend("POVMarketMakerAgent")

    # ── 6. Momentum Agents ───────────────────────────────────────────────
    #    num_mom_ekf_agents of the momentum slots go to MomentumEKFAgents
    #    (6b), so the total agent count is unchanged.
    num_stock_momentum = num_momentum_agents - num_mom_ekf_agents
    assert num_stock_momentum >= 0, "num_mom_ekf_agents > num_momentum_agents"
    agents.extend(
        [
            MomentumAgent(
                id=j,
                name="MOMENTUM_AGENT_{}".format(j),
                type="MomentumAgent",
                symbol=ticker,
                starting_cash=starting_cash,
                min_size=1,
                max_size=10,
                wake_up_freq=str_to_ns("37s"),
                poisson_arrival=True,
                log_orders=log_orders,
                order_size_model=ORDER_SIZE_MODEL,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
            for j in range(agent_count, agent_count + num_stock_momentum)
        ]
    )
    agent_count += num_stock_momentum
    agent_types.extend("MomentumAgent")

    # ── 6b. EKF Momentum Agents (OUR custom agents) ──────────────────────
    #    Hyperparameters drawn per agent from the spec's Part G ranges
    #    (herding guard: thresholds, tau and wake times all differ).
    mom_ekf_start_id = agent_count
    for j in range(agent_count, agent_count + num_mom_ekf_agents):
        # Ranges in param_ranges.py; keyword-argument evaluation order fixes
        # the draw order, keep it unchanged so seeded runs reproduce.
        # Spec v1.1 M3: wake_mean is drawn FIRST and tau = tau_ratio * wake_mean.
        wake_mean = draw(MOM, "wake_mean")
        n_er = draw(MOM, "n_er")
        agents.append(
            MomentumEKFAgent(
                id=j,
                name="EKF_Mom_{}".format(j),
                type="EKF_Momentum",
                symbol=ticker,
                # spec v1.3 §6.4 (lab scenarios S7a-c); 1.0 = unchanged
                starting_cash=int(round(starting_cash * mom_capital_mult)),
                log_orders=True,  # Always log our agents
                initial_exposure=mom_ekf_initial_exposure,
                reference_price=r_bar,
                # ── Layer 1 ─────────────────────────────────────────
                n_er=n_er,
                N_w=draw(MOM, "N_w", low=max(n_er + 1, MOM["N_w"][0])),
                lambda_er=draw(MOM, "lambda_er"),
                kappa_R=draw(MOM, "kappa_R"),
                c_P=draw(MOM, "c_P"),
                tau_ratio=(tau_ratio := draw(MOM, "tau_ratio")),
                tau=tau_ratio * wake_mean,
                kappa_l=draw(MOM, "kappa_l"),
                kappa_v=draw(MOM, "kappa_v"),
                a_eps=draw(MOM, "a_eps"),
                eps_thr=draw(MOM, "eps_thr"),
                g_max=draw(MOM, "g_max"),
                # ── Layer 2 ─────────────────────────────────────────
                gamma=draw(MOM, "gamma"),
                k_c=draw(MOM, "k_c"),
                # ── State machine ───────────────────────────────────
                theta_in=draw(MOM, "theta_in"),
                theta_out=draw(MOM, "theta_out"),
                ER_min=draw(MOM, "ER_min"),
                k_stop=draw(MOM, "k_stop"),
                k_re=draw(MOM, "k_re"),
                # ── Layer 3 ─────────────────────────────────────────
                T_0=draw(MOM, "T_0"),
                lambda_v=draw(MOM, "lambda_v"),
                e_max=draw(MOM, "e_max"),
                e_min=draw(MOM, "e_min"),
                b=draw(MOM, "b"),
                n_min=int(draw(MOM, "n_min")),
                k_add=draw(MOM, "k_add"),
                mu_m=draw(MOM, "mu_m"),
                # ── News / scheduling ───────────────────────────────
                eta_news=draw(MOM, "eta_news"),
                rho_news=draw(MOM, "rho_news"),
                wake_mean=wake_mean,
                random_state=np.random.RandomState(
                    seed=np.random.randint(low=0, high=2**31, dtype="uint32")
                ),
            )
        )
    agent_count += num_mom_ekf_agents
    agent_types.extend(["EKF_Momentum"])

    # ── 7. News Oracle Agent ─────────────────────────────────────────────
    news_oracle_id = agent_count
    news_oracle = NewsOracleAgent(
        id=news_oracle_id,
        name="NewsOracle",
        type="NewsOracleAgent",
        random_state=np.random.RandomState(
            seed=np.random.randint(low=0, high=2**31, dtype="uint32")
        ),
    )

    # Enqueue any pre-defined news events
    if news_events:
        for time_offset, symbol, sentiment, headline in news_events:
            delivery_time = MKT_OPEN + str_to_ns(time_offset)
            news_oracle.enqueue_news(symbol, sentiment, headline, delivery_time)

    agents.append(news_oracle)
    agent_count += 1
    agent_types.extend(["NewsOracleAgent"])

    # ── 8. Impact probe (spec v1.3 §6.2; realism lab only) ────────────────
    #    The LAST agent, appended before the kernel RNG and the latency model
    #    are drawn. Its RandomState is a constant, NOT drawn from the global
    #    stream, and the latency model places one more coordinate after all
    #    existing agents' ones, so every other agent is unchanged.
    probe_id = None
    if probe is not None:
        probe_id = agent_count
        side = str(probe["side"]).upper()
        qty = int(probe["quantity"])
        agents.append(
            ImpactProbeAgent(
                id=probe_id,
                name="IMPACT_PROBE",
                type="ImpactProbeAgent",
                symbol=ticker,
                side=side,
                quantity=qty,
                start_time=MKT_OPEN + str_to_ns(probe["start"]),
                duration_s=int(probe.get("duration_s", 300)),
                child_interval_s=int(probe.get("child_interval_s", 10)),
                starting_cash=10**12 if side == "BUY" else 0,
                starting_shares=qty if side == "SELL" else 0,
                random_state=np.random.RandomState(0),
            )
        )
        agent_count += 1
        agent_types.extend(["ImpactProbeAgent"])

    # ── spec v1.4 Part 5: budget limits (set after construction, no RNG) ──
    if abides_budget is not None:
        for a in agents:
            if type(a) in (NoiseAgent, ValueAgent, MomentumAgent):
                a.budget = GrossLimit(abides_budget.get("L", 2.0))

    # ── Kernel configuration ─────────────────────────────────────────────
    random_state_kernel = np.random.RandomState(
        seed=np.random.randint(low=0, high=2**31, dtype="uint32")
    )
    latency_model = generate_latency_model(agent_count)
    default_computation_delay = 50

    kernelStartTime = DATE
    kernelStopTime = MKT_CLOSE + str_to_ns("1s")

    return {
        "seed": seed,
        "start_time": kernelStartTime,
        "stop_time": kernelStopTime,
        "agents": agents,
        "agent_latency_model": latency_model,
        "default_computation_delay": default_computation_delay,
        "custom_properties": {"oracle": oracle},
        "random_state_kernel": random_state_kernel,
        "stdout_log_level": stdout_log_level,
        # Extra metadata for dashboard extraction
        "_ekf_agent_ids": list(range(ekf_start_id, ekf_start_id + num_ekf_agents)),
        "_mom_ekf_agent_ids": list(
            range(mom_ekf_start_id, mom_ekf_start_id + num_mom_ekf_agents)
        ),
        "_news_oracle_id": news_oracle_id,
        # spec v1.4 §6.3: the export shows the informed design's ranges
        "_fund_mode": fund_mode,
        "_informed_design": informed_design if fund_mode == "informed" else None,
        "_probe_id": probe_id,
        "_mkt_open_ns": MKT_OPEN,
        "_mkt_close_ns": MKT_CLOSE,
    }
