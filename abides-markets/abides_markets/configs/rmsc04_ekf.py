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
from abides_markets.agents.momentum_ekf import MomentumEKFAgent
from abides_markets.agents.news_oracle_agent import NewsOracleAgent
from abides_markets.configs.param_ranges import (
    FUNDAMENTAL_RANGES as FUND,
    MOMENTUM_RANGES as MOM,
    draw,
)
from abides_markets.models import OrderSizeModel
from abides_markets.oracles import PregeneratedOracle
from abides_markets.utils import generate_latency_model


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
    ekf_start_id = agent_count
    for j in range(agent_count, agent_count + num_ekf_agents):
        agents.append(
            FundamentalistAgent(
                id=j,
                name="EKF_Fund_{}".format(j),
                type="EKF_Fundamentalist",
                symbol=ticker,
                starting_cash=starting_cash,
                log_orders=True,  # Always log our agents
                wake_up_freq=str_to_ns("10S"),
                # ── Randomized EKF Hyperparameters ──────────────────
                # (ranges in param_ranges.py; keyword-argument evaluation
                #  order fixes the draw order, keep it unchanged)
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
                starting_cash=starting_cash,
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
        "_mkt_open_ns": MKT_OPEN,
        "_mkt_close_ns": MKT_CLOSE,
    }
