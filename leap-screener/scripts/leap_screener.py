#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LEAP Call 潜力股发掘工具

功能：
1) 基于 yfinance 拉取基本面、技术面、期权链数据
2) 通过 3 层漏斗筛选候选标的
3) 按评分模型（0-100）输出中文 Top N 排名报告

用法示例：
- 默认股票池（S&P500 + Nasdaq100 去重）
  python leap_screener.py
- 指定股票池
  python leap_screener.py --tickers AAPL,NVDA,AMD
- 指定输出数量
  python leap_screener.py --top 15
- 启用成交量放大硬过滤
  python leap_screener.py --require-volume-spike
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator


# ----------------------------
# 参数阈值（可按需调整）
# ----------------------------
REV_GROWTH_MIN = 0.10           # 收入增速 > 10%
EPS_GROWTH_MIN = 0.15           # EPS 增速 > 15%
PEG_MAX = 2.0                   # PEG < 2.0
MARKET_CAP_MIN = 5_000_000_000  # 市值 > 50 亿美元
UPSIDE_MIN = 0.15               # 分析师目标价 upside > 15%
RSI_MAX = 60                    # RSI(14) < 60
DRAWDOWN_MIN = -35.0            # 距 52 周高 > -35%（百分比）
LONG_DTE_MONTHS = 9             # LEAP：> 9 个月

# 异常值/一次性因素检查阈值
EPS_GROWTH_CAP = 4.0            # EPS 增速 > 400% 视为可疑（并购/一次性）
REV_GROWTH_CAP = 2.0            # 收入增速 > 200% 视为可疑
SHARES_CHANGE_THRESHOLD = 0.15  # 股份数变化 > 15% 视为并购信号
EPS_VOLATILITY_MAX = 5.0        # 季度 EPS 波动系数 > 5 视为不稳定

# yfinance 速率控制（秒）
REQUEST_SLEEP = 0.45


@dataclass
class StockResult:
    ticker: str
    score: float
    layer1_pass: bool
    layer2_pass: bool
    layer3_pass: bool
    reason: str
    current_price: Optional[float] = None
    revenue_growth: Optional[float] = None
    eps_growth: Optional[float] = None
    eps_growth_forward: Optional[float] = None
    trailing_eps: Optional[float] = None
    forward_eps: Optional[float] = None
    peg: Optional[float] = None
    market_cap: Optional[float] = None
    upside: Optional[float] = None
    rsi14: Optional[float] = None
    drawdown_52w_pct: Optional[float] = None
    vol_spike: Optional[bool] = None
    vol_ratio: Optional[float] = None
    leap_expiry: Optional[str] = None
    leap_strike: Optional[float] = None
    call_bid: Optional[float] = None
    call_ask: Optional[float] = None
    call_spread_pct: Optional[float] = None
    iv_rank: Optional[float] = None
    required_move_for_2x_pct: Optional[float] = None
    sanity_flags: Optional[List[str]] = None  # 异常标记列表


def clamp(v: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, v))


def safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        fv = float(v)
        if math.isnan(fv) or math.isinf(fv):
            return None
        return fv
    except Exception:
        return None


def pct_or_none(v: Optional[float]) -> str:
    return "N/A" if v is None else f"{v * 100:.1f}%"


def num_or_none(v: Optional[float], nd: int = 2) -> str:
    return "N/A" if v is None else f"{v:.{nd}f}"


def money_or_none(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    return f"${v:.2f}"


def get_default_universe() -> List[str]:
    """默认股票池：S&P500（CSV） + Nasdaq100（硬编码） 去重"""
    sp_list: List[str] = []
    try:
        sp500 = pd.read_csv("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv")
        sp_list = sp500["Symbol"].astype(str).str.replace(".", "-", regex=False).str.upper().tolist()
    except Exception:
        sp_list = []

    # Nasdaq 100 硬编码（2026年初）
    ndq_list = [
        "AAPL", "ABNB", "ADBE", "ADI", "ADP", "ADSK", "AEP", "AMAT", "AMD", "AMGN",
        "AMZN", "ANSS", "APP", "ARM", "ASML", "AVGO", "AZN", "BIIB", "BKNG", "BKR",
        "CCEP", "CDNS", "CDW", "CEG", "CHTR", "CMCSA", "COST", "CPRT", "CRWD", "CSCO",
        "CSGP", "CSX", "CTAS", "CTSH", "DASH", "DDOG", "DLTR", "DXCM", "EA", "EXC",
        "FANG", "FAST", "FTNT", "GEHC", "GFS", "GILD", "GOOG", "GOOGL", "HON", "IDXX",
        "ILMN", "INTC", "INTU", "ISRG", "KDP", "KHC", "KLAC", "LIN", "LRCX", "LULU",
        "MAR", "MCHP", "MDB", "MDLZ", "MELI", "META", "MNST", "MRVL", "MSFT", "MU",
        "NFLX", "NVDA", "NXPI", "ODFL", "ON", "ORLY", "PANW", "PAYX", "PCAR", "PDD",
        "PEP", "PYPL", "QCOM", "REGN", "ROP", "ROST", "SBUX", "SMCI", "SNPS", "TEAM",
        "TMUS", "TSLA", "TTD", "TTWO", "TXN", "VRSK", "VRTX", "WBD", "WDAY", "XEL",
        "ZS",
    ]

    tickers = sorted(set([x for x in (sp_list + ndq_list) if x and x != "N/A"]))
    if not tickers:
        # 兜底
        tickers = [
            "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX",
            "COST", "ADBE", "INTC", "QCOM", "CRM", "ORCL", "CSCO", "TXN", "AMAT", "MU",
        ]
    return tickers


def get_technical_metrics(hist: pd.DataFrame) -> Dict[str, Optional[float]]:
    if hist is None or hist.empty or len(hist) < 30:
        return {
            "price": None,
            "rsi14": None,
            "drawdown_52w_pct": None,
            "vol_ratio": None,
            "vol_spike": None,
        }

    close = hist["Close"].astype(float)
    volume = hist["Volume"].astype(float)
    price = safe_float(close.iloc[-1])

    rsi_series = RSIIndicator(close=close, window=14).rsi()
    rsi14 = safe_float(rsi_series.iloc[-1])

    high_52w = safe_float(close.max())
    drawdown_52w_pct = None
    if price is not None and high_52w and high_52w > 0:
        drawdown_52w_pct = (price / high_52w - 1.0) * 100.0

    vol20 = volume.rolling(20).mean()
    vol_ratio = None
    vol_spike = None
    if not vol20.empty:
        v20 = safe_float(vol20.iloc[-1])
        v0 = safe_float(volume.iloc[-1])
        if v20 and v20 > 0 and v0 is not None:
            vol_ratio = v0 / v20
            vol_spike = vol_ratio > 1.5

    return {
        "price": price,
        "rsi14": rsi14,
        "drawdown_52w_pct": drawdown_52w_pct,
        "vol_ratio": vol_ratio,
        "vol_spike": vol_spike,
    }


def pick_atm_call(calls: pd.DataFrame, spot: float) -> Optional[pd.Series]:
    if calls is None or calls.empty or spot is None:
        return None
    calls = calls.copy()
    calls["dist"] = (calls["strike"] - spot).abs()
    calls = calls.sort_values(["dist", "openInterest"], ascending=[True, False])
    if calls.empty:
        return None
    return calls.iloc[0]


def get_option_metrics(tk: yf.Ticker, spot: float, min_months: int = LONG_DTE_MONTHS) -> Dict[str, Optional[float]]:
    """
    期权层数据：
    - 是否存在 >9个月到期日
    - 推荐 ATM 附近 LEAP call
    - bid/ask spread
    - IV Rank（代理值：基于可用到期 ATM IV 区间）
    - 翻倍所需涨幅
    """
    options = tk.options or []
    if not options:
        return {
            "layer3_pass": False,
            "reason": "无可用期权链",
            "expiry": None,
            "strike": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "iv_rank": None,
            "required_move_for_2x_pct": None,
        }

    cutoff = datetime.now().date() + timedelta(days=int(min_months * 30))

    valid_expiries = []
    for d in options:
        try:
            dd = datetime.strptime(d, "%Y-%m-%d").date()
            if dd > cutoff:
                valid_expiries.append((d, dd))
        except Exception:
            continue

    if not valid_expiries:
        return {
            "layer3_pass": False,
            "reason": f"无>{min_months}个月到期期权",
            "expiry": None,
            "strike": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "iv_rank": None,
            "required_move_for_2x_pct": None,
        }

    valid_expiries.sort(key=lambda x: x[1])
    preferred_expiry = valid_expiries[0][0]

    atm_ivs = []
    chosen_call = None

    for expiry, _ in valid_expiries:
        try:
            chain = tk.option_chain(expiry)
            calls = chain.calls
            atm = pick_atm_call(calls, spot)
            if atm is not None:
                iv = safe_float(atm.get("impliedVolatility"))
                if iv is not None and iv > 0:
                    atm_ivs.append(iv)
                if expiry == preferred_expiry:
                    chosen_call = atm
            time.sleep(REQUEST_SLEEP)
        except Exception:
            continue

    # 若 preferred 到期日没拿到可用 ATM，尝试从其他到期日选一个
    if chosen_call is None:
        for expiry, _ in valid_expiries:
            try:
                chain = tk.option_chain(expiry)
                atm = pick_atm_call(chain.calls, spot)
                if atm is not None:
                    preferred_expiry = expiry
                    chosen_call = atm
                    break
            except Exception:
                continue

    if chosen_call is None:
        return {
            "layer3_pass": False,
            "reason": "长期期权存在但无可用ATM Call",
            "expiry": None,
            "strike": None,
            "bid": None,
            "ask": None,
            "spread_pct": None,
            "iv_rank": None,
            "required_move_for_2x_pct": None,
        }

    strike = safe_float(chosen_call.get("strike"))
    bid = safe_float(chosen_call.get("bid"))
    ask = safe_float(chosen_call.get("ask"))
    iv_now = safe_float(chosen_call.get("impliedVolatility"))

    spread_pct = None
    premium = None
    if bid is not None and ask is not None and ask > 0:
        mid = (bid + ask) / 2
        premium = mid
        if mid > 0:
            spread_pct = (ask - bid) / mid * 100

    # IV Rank（代理）：当前 ATM IV 在可用长期到期 ATM IV 区间中的位置
    iv_rank = None
    if iv_now is not None and len(atm_ivs) >= 2:
        iv_min = min(atm_ivs)
        iv_max = max(atm_ivs)
        if iv_max > iv_min:
            iv_rank = (iv_now - iv_min) / (iv_max - iv_min) * 100
            iv_rank = clamp(iv_rank)

    required_move_for_2x_pct = None
    if strike is not None and premium is not None and spot and spot > 0:
        spot_for_2x = strike + 2 * premium
        required_move_for_2x_pct = (spot_for_2x / spot - 1.0) * 100

    return {
        "layer3_pass": True,
        "reason": "OK",
        "expiry": preferred_expiry,
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "spread_pct": spread_pct,
        "iv_rank": iv_rank,
        "required_move_for_2x_pct": required_move_for_2x_pct,
    }


def score_stock(metrics: Dict[str, Optional[float]]) -> float:
    """
    评分模型（0-100）
    - 基本面强度 25%
    - 估值折价 20%
    - 技术面窗口 15%
    - 催化剂（分析师 upside）20%
    - 期权性价比 20%
    """
    rev = metrics.get("revenue_growth")
    eps = metrics.get("eps_growth")
    peg = metrics.get("peg")
    mcap = metrics.get("market_cap")
    upside = metrics.get("upside")
    rsi = metrics.get("rsi14")
    drawdown = metrics.get("drawdown_52w_pct")
    vol_ratio = metrics.get("vol_ratio")
    spread = metrics.get("call_spread_pct")
    iv_rank = metrics.get("iv_rank")
    req_move = metrics.get("required_move_for_2x_pct")

    # 基本面强度（四项均衡）
    s_rev = clamp(((rev or 0) - 0.05) / 0.30 * 100)
    s_eps = clamp(((eps or 0) - 0.05) / 0.40 * 100)
    s_peg = clamp((2.0 - (peg if peg is not None else 2.0)) / 1.5 * 100)
    s_mcap = clamp((math.log10(max(mcap or 1, 1)) - 9.0) / 3.0 * 100)
    s_fund = np.mean([s_rev, s_eps, s_peg, s_mcap])

    # 估值折价（PEG 越低越好）
    s_val = clamp((2.0 - (peg if peg is not None else 2.0)) / 2.0 * 100)

    # 技术面窗口（低 RSI + 适度回撤 + 量能）
    s_rsi = clamp((55 - (rsi if rsi is not None else 60)) / 25 * 100)
    # drawdown 在 [-15, -5] 视为较优窗口
    dd = drawdown if drawdown is not None else 0
    if dd < -40:
        s_dd = 5
    elif -25 <= dd <= -5:
        s_dd = 90
    elif dd < -25:
        s_dd = 50
    else:
        s_dd = 40
    s_vol = clamp(((vol_ratio or 1.0) - 0.8) / 1.2 * 100)
    s_tech = np.mean([s_rsi, s_dd, s_vol])

    # 催化剂（分析师 upside）
    s_cat = clamp(((upside or 0) - 0.10) / 0.50 * 100)

    # 期权性价比：点差越小越好、翻倍所需涨幅越低越好、IV Rank 中低位更友好
    s_spread = clamp((20 - (spread if spread is not None else 20)) / 20 * 100)
    s_move = clamp((80 - (req_move if req_move is not None else 80)) / 80 * 100)
    if iv_rank is None:
        s_iv = 50
    else:
        # 做多期权通常偏好中低 IV，目标区间约 20~50
        s_iv = clamp(100 - abs(iv_rank - 35) * 2.2)
    s_opt = np.mean([s_spread, s_move, s_iv])

    final = (
        s_fund * 0.25
        + s_val * 0.20
        + s_tech * 0.15
        + s_cat * 0.20
        + s_opt * 0.20
    )
    return round(float(clamp(final)), 2)


def analyze_ticker(ticker: str, require_volume_spike: bool = False) -> StockResult:
    ticker = ticker.upper().strip()

    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        # 速率控制，避免请求过快
        time.sleep(REQUEST_SLEEP)

        hist = tk.history(period="1y", interval="1d", auto_adjust=False)
        tech = get_technical_metrics(hist)

        price = tech["price"]
        rev_growth = safe_float(info.get("revenueGrowth"))
        eps_growth = safe_float(info.get("earningsGrowth"))  # 单季度同比
        trailing_eps = safe_float(info.get("trailingEps"))    # 过去12个月 EPS
        forward_eps = safe_float(info.get("forwardEps"))      # 明年预期 EPS
        # Forward EPS 增速 = (forwardEps - trailingEps) / |trailingEps|
        eps_growth_forward = None
        if trailing_eps is not None and forward_eps is not None and abs(trailing_eps) > 0.01:
            eps_growth_forward = (forward_eps - trailing_eps) / abs(trailing_eps)
        peg = safe_float(info.get("pegRatio"))

        # ===== 异常值/一次性因素检查 =====
        sanity_flags: List[str] = []

        # 检查1: 股份数大幅变化（并购/增发信号）
        shares_outstanding = safe_float(info.get("sharesOutstanding"))
        float_shares = safe_float(info.get("floatShares"))
        if shares_outstanding and float_shares:
            # 如果流通股远小于总股本，可能有大比例增发/并购
            if float_shares > 0 and (shares_outstanding / float_shares) > 1.3:
                sanity_flags.append("股份结构异常（总股本远大于流通股）")

        # 检查2: 收入增速异常高（>200%，可能是并购合并报表）
        if rev_growth is not None and rev_growth > REV_GROWTH_CAP:
            sanity_flags.append(f"收入增速异常高({rev_growth*100:.0f}%)，疑似并购/一次性")
            rev_growth = None  # 标记为不可靠，不参与筛选

        # 检查3: EPS 增速异常高（>300%）
        if eps_growth is not None and abs(eps_growth) > EPS_GROWTH_CAP:
            sanity_flags.append(f"季度EPS增速异常({eps_growth*100:.0f}%)，疑似一次性因素")
            eps_growth = None

        if eps_growth_forward is not None and abs(eps_growth_forward) > EPS_GROWTH_CAP:
            sanity_flags.append(f"Forward EPS增速异常({eps_growth_forward*100:.0f}%)，疑似并购/口径不一致")
            eps_growth_forward = None

        # 检查4: TTM EPS 极低或为负（可能是低基数效应）
        if trailing_eps is not None and abs(trailing_eps) < 0.50 and forward_eps is not None and forward_eps > 5.0:
            sanity_flags.append(f"TTM EPS极低(${trailing_eps:.2f})而Forward高(${forward_eps:.2f})，低基数效应")
            eps_growth_forward = None

        # 检查5: PEG 异常低（<0.2），通常是 EPS 增速失真导致
        if peg is not None and peg < 0.2:
            sanity_flags.append(f"PEG异常低({peg:.2f})，可能是增速数据失真")

        # 检查6: 季度 EPS 历史波动检查（用 quarterly earnings）
        try:
            qe = tk.quarterly_earnings
            if qe is not None and len(qe) >= 4:
                eps_vals = qe["Reported EPS"].dropna().values[-4:]
                if len(eps_vals) >= 4:
                    eps_std = float(np.std(eps_vals))
                    eps_mean = float(np.mean(np.abs(eps_vals)))
                    if eps_mean > 0 and eps_std / eps_mean > EPS_VOLATILITY_MAX:
                        sanity_flags.append(f"季度EPS波动极大(CV={eps_std/eps_mean:.1f})，盈利不稳定")
        except Exception:
            pass
        if peg is None:
            peg = safe_float(info.get("trailingPegRatio"))
        market_cap = safe_float(info.get("marketCap"))

        target_price = safe_float(info.get("targetMeanPrice"))
        if target_price is None:
            target_price = safe_float(info.get("targetMedianPrice"))
        upside = None
        if target_price is not None and price is not None and price > 0:
            upside = target_price / price - 1.0

        # Layer 1：基本面
        # EPS 增速：单季度同比 或 forward 增速 任一满足即可
        eps_pass = (
            (eps_growth is not None and eps_growth > EPS_GROWTH_MIN)
            or (eps_growth_forward is not None and eps_growth_forward > EPS_GROWTH_MIN)
        )
        l1 = all([
            rev_growth is not None and rev_growth > REV_GROWTH_MIN,
            eps_pass,
            peg is not None and peg < PEG_MAX,
            market_cap is not None and market_cap > MARKET_CAP_MIN,
            upside is not None and upside > UPSIDE_MIN,
        ])
        if not l1:
            result = StockResult(
                ticker=ticker,
                score=0.0,
                layer1_pass=False,
                layer2_pass=False,
                layer3_pass=False,
                reason="未通过 Layer 1 基本面筛选",
                current_price=price,
                revenue_growth=rev_growth,
                eps_growth=eps_growth,
                eps_growth_forward=eps_growth_forward,
                trailing_eps=trailing_eps,
                forward_eps=forward_eps,
                peg=peg,
                market_cap=market_cap,
                upside=upside,
                rsi14=tech.get("rsi14"),
                drawdown_52w_pct=tech.get("drawdown_52w_pct"),
                vol_spike=tech.get("vol_spike"),
                vol_ratio=tech.get("vol_ratio"),
                sanity_flags=sanity_flags if sanity_flags else None,
            )
            return result

        # Layer 2：技术面
        rsi14 = tech.get("rsi14")
        dd52 = tech.get("drawdown_52w_pct")
        vol_spike = tech.get("vol_spike")

        l2 = (
            rsi14 is not None and rsi14 < RSI_MAX
            and dd52 is not None and dd52 > DRAWDOWN_MIN
        )
        if require_volume_spike:
            l2 = l2 and bool(vol_spike)

        if not l2:
            result = StockResult(
                ticker=ticker,
                score=0.0,
                layer1_pass=True,
                layer2_pass=False,
                layer3_pass=False,
                reason="未通过 Layer 2 技术面筛选",
                current_price=price,
                revenue_growth=rev_growth,
                eps_growth=eps_growth,
                eps_growth_forward=eps_growth_forward,
                trailing_eps=trailing_eps,
                forward_eps=forward_eps,
                peg=peg,
                market_cap=market_cap,
                upside=upside,
                rsi14=rsi14,
                drawdown_52w_pct=dd52,
                vol_spike=vol_spike,
                vol_ratio=tech.get("vol_ratio"),
                sanity_flags=sanity_flags if sanity_flags else None,
            )
            return result

        # Layer 3：期权评估
        opt = get_option_metrics(tk, spot=price if price else 0.0, min_months=LONG_DTE_MONTHS)
        l3 = bool(opt.get("layer3_pass"))
        if not l3:
            result = StockResult(
                ticker=ticker,
                score=0.0,
                layer1_pass=True,
                layer2_pass=True,
                layer3_pass=False,
                reason=f"未通过 Layer 3 期权筛选：{opt.get('reason')}",
                current_price=price,
                revenue_growth=rev_growth,
                eps_growth=eps_growth,
                eps_growth_forward=eps_growth_forward,
                trailing_eps=trailing_eps,
                forward_eps=forward_eps,
                peg=peg,
                market_cap=market_cap,
                upside=upside,
                sanity_flags=sanity_flags if sanity_flags else None,
                rsi14=rsi14,
                drawdown_52w_pct=dd52,
                vol_spike=vol_spike,
                vol_ratio=tech.get("vol_ratio"),
            )
            return result

        # 评分用更优的 EPS 增速
        best_eps_growth = eps_growth
        if eps_growth_forward is not None:
            if best_eps_growth is None or eps_growth_forward > best_eps_growth:
                best_eps_growth = eps_growth_forward

        metrics = {
            "revenue_growth": rev_growth,
            "eps_growth": best_eps_growth,
            "peg": peg,
            "market_cap": market_cap,
            "upside": upside,
            "rsi14": rsi14,
            "drawdown_52w_pct": dd52,
            "vol_ratio": tech.get("vol_ratio"),
            "call_spread_pct": opt.get("spread_pct"),
            "iv_rank": opt.get("iv_rank"),
            "required_move_for_2x_pct": opt.get("required_move_for_2x_pct"),
        }
        score = score_stock(metrics)

        return StockResult(
            ticker=ticker,
            score=score,
            layer1_pass=True,
            layer2_pass=True,
            layer3_pass=True,
            reason="通过全部筛选",
            current_price=price,
            revenue_growth=rev_growth,
            eps_growth=eps_growth,
            eps_growth_forward=eps_growth_forward,
            trailing_eps=trailing_eps,
            forward_eps=forward_eps,
            peg=peg,
            sanity_flags=sanity_flags if sanity_flags else None,
            market_cap=market_cap,
            upside=upside,
            rsi14=rsi14,
            drawdown_52w_pct=dd52,
            vol_spike=vol_spike,
            vol_ratio=tech.get("vol_ratio"),
            leap_expiry=opt.get("expiry"),
            leap_strike=opt.get("strike"),
            call_bid=opt.get("bid"),
            call_ask=opt.get("ask"),
            call_spread_pct=opt.get("spread_pct"),
            iv_rank=opt.get("iv_rank"),
            required_move_for_2x_pct=opt.get("required_move_for_2x_pct"),
        )

    except Exception as e:
        return StockResult(
            ticker=ticker,
            score=0.0,
            layer1_pass=False,
            layer2_pass=False,
            layer3_pass=False,
            reason=f"处理失败：{e}",
        )


def _format_stock_entry(i: int, r: StockResult) -> List[str]:
    """格式化单只股票的报告条目"""
    lines: List[str] = []
    lines.append(f"### #{i} {r.ticker} | 综合评分：**{r.score:.2f}**")
    lines.append(f"- 当前价格：{money_or_none(r.current_price)}")
    lines.append(
        f"- 基本面：收入YoY {pct_or_none(r.revenue_growth)}，"
        f"EPS增速(季度同比) {pct_or_none(r.eps_growth)}，"
        f"EPS增速(Forward) {pct_or_none(r.eps_growth_forward)}，"
        f"TTM EPS {num_or_none(r.trailing_eps)}，Forward EPS {num_or_none(r.forward_eps)}"
    )
    lines.append(
        f"- 估值：PEG {num_or_none(r.peg)}，市值 {money_or_none(r.market_cap)}，Upside {pct_or_none(r.upside)}"
    )
    lines.append(
        f"- 技术面：RSI(14) {num_or_none(r.rsi14)}，距52周高 {num_or_none(r.drawdown_52w_pct)}%，"
        f"量比(当日/20日均量) {num_or_none(r.vol_ratio)}"
    )
    lines.append(
        f"- LEAP建议：到期日 **{r.leap_expiry or 'N/A'}**，"
        f"Strike **{money_or_none(r.leap_strike)}**，Bid/Ask {num_or_none(r.call_bid)}/{num_or_none(r.call_ask)}，"
        f"点差 {num_or_none(r.call_spread_pct)}%"
    )
    ivr = "N/A" if r.iv_rank is None else f"{r.iv_rank:.1f}"
    move2x = "N/A" if r.required_move_for_2x_pct is None else f"{r.required_move_for_2x_pct:.1f}%"
    lines.append(f"- 期权评估：IV Rank(代理) {ivr}，翻倍所需涨幅 {move2x}")
    if r.sanity_flags:
        lines.append(f"- ⚠️ 异常标记：{'；'.join(r.sanity_flags)}")
    lines.append("")
    return lines


def build_report(results: List[StockResult], top_n: int, total_cnt: int, elapsed: float, require_volume_spike: bool) -> str:
    passed = [r for r in results if r.layer1_pass and r.layer2_pass and r.layer3_pass]
    # 分离：有 flag vs 无 flag
    clean = [r for r in passed if not r.sanity_flags]
    flagged = [r for r in passed if r.sanity_flags]
    clean_sorted = sorted(clean, key=lambda x: x.score, reverse=True)
    flagged_sorted = sorted(flagged, key=lambda x: x.score, reverse=True)
    top_clean = clean_sorted[:top_n]

    lines: List[str] = []
    lines.append("# LEAP Call 潜力股筛选报告")
    lines.append("")
    lines.append(f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 扫描股票数：{total_cnt}")
    lines.append(f"- 全部通过三层筛选：{len(passed)}（无flag {len(clean)}，有flag {len(flagged)}）")
    lines.append(f"- 输出 Top：{top_n}")
    lines.append(f"- 成交量放大硬过滤：{'开启' if require_volume_spike else '关闭（仅作为参考）'}")
    lines.append(f"- 用时：{elapsed:.1f} 秒")
    lines.append("")

    lines.append("## 筛选条件")
    lines.append("")
    lines.append(f"- Layer 1（基本面）：收入增速>{REV_GROWTH_MIN*100:.0f}%，EPS增速>{EPS_GROWTH_MIN*100:.0f}%，PEG<{PEG_MAX}，市值>${MARKET_CAP_MIN/1e9:.0f}B，目标价Upside>{UPSIDE_MIN*100:.0f}%")
    lines.append(f"- Layer 2（技术面）：RSI(14)<{RSI_MAX}，距52周高回撤>{DRAWDOWN_MIN:.0f}%，近期放量可选")
    lines.append("- Layer 3（期权）：存在>9个月到期链，评估ATM Call点差/IV Rank/翻倍所需涨幅")
    lines.append("")

    if not top_clean and not flagged_sorted:
        lines.append("## 结果")
        lines.append("")
        lines.append("未找到同时通过三层筛选的标的。")
        failed = [r for r in results if not (r.layer1_pass and r.layer2_pass and r.layer3_pass)]
        if failed:
            lines.append("")
            lines.append("### 失败样本（前10）")
            for r in failed[:10]:
                lines.append(f"- {r.ticker}: {r.reason}")
        return "\n".join(lines)

    # ===== 主列表：Top N 无 flag =====
    lines.append(f"## 🏆 Top {top_n} 无异常标记")
    lines.append("")
    if top_clean:
        for i, r in enumerate(top_clean, 1):
            lines.extend(_format_stock_entry(i, r))
    else:
        lines.append("_无候选股通过筛选且无异常标记。_")
        lines.append("")

    # ===== 次列表：有 flag 但有潜力 =====
    if flagged_sorted:
        lines.append(f"## ⚠️ 有潜力但存在异常标记（{len(flagged_sorted)} 只）")
        lines.append("")
        for i, r in enumerate(flagged_sorted, 1):
            lines.extend(_format_stock_entry(i, r))

    # 追加失败统计
    l1_fail = sum(1 for r in results if not r.layer1_pass)
    l2_fail = sum(1 for r in results if r.layer1_pass and not r.layer2_pass)
    l3_fail = sum(1 for r in results if r.layer1_pass and r.layer2_pass and not r.layer3_pass)
    err_cnt = sum(1 for r in results if "处理失败" in r.reason)

    lines.append("## 漏斗统计")
    lines.append("")
    lines.append(f"- Layer 1 淘汰：{l1_fail}")
    lines.append(f"- Layer 2 淘汰：{l2_fail}")
    lines.append(f"- Layer 3 淘汰：{l3_fail}")
    lines.append(f"- 数据异常/处理失败：{err_cnt}")
    lines.append("")
    lines.append("---")
    lines.append("注：IV Rank 为基于当前可用长期到期 ATM IV 区间的代理值（yfinance 免费数据限制下的近似）。")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LEAP Call 潜力股筛选器")
    parser.add_argument("--top", type=int, default=10, help="输出前 N 名（默认 10）")
    parser.add_argument(
        "--tickers",
        type=str,
        default="",
        help="指定股票池，如 AAPL,NVDA,AMD（不填则默认 S&P500 + Nasdaq100）",
    )
    parser.add_argument(
        "--require-volume-spike",
        action="store_true",
        help="Layer 2 强制要求放量（成交量 > 20日均量 * 1.5）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.tickers.strip():
        universe = [x.strip().upper() for x in args.tickers.split(",") if x.strip()]
        universe = sorted(set(universe))
    else:
        universe = get_default_universe()

    if not universe:
        print("未获得可用股票池，请检查网络或参数。")
        return 1

    print(f"开始扫描：{len(universe)} 只股票...", file=sys.stderr)
    start = time.time()

    results: List[StockResult] = []
    for i, t in enumerate(universe, 1):
        r = analyze_ticker(t, require_volume_spike=args.require_volume_spike)
        results.append(r)
        print(f"[{i}/{len(universe)}] {t}: {r.reason}", file=sys.stderr)
        time.sleep(REQUEST_SLEEP)

    elapsed = time.time() - start
    report = build_report(
        results=results,
        top_n=max(1, args.top),
        total_cnt=len(universe),
        elapsed=elapsed,
        require_volume_spike=args.require_volume_spike,
    )

    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
