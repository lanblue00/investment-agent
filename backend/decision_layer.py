"""
投研大脑 - L3 决策层
综合数据层和信息层，进行量化分析，生成交易信号
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    MA_PERIODS, VOLUME_SURGE_THRESHOLD, VOLUME_SHRINK_THRESHOLD,
    MAX_BUY_RATIO_PER_DAY, MAX_SELL_RATIO_PER_DAY, SECTORS
)


def analyze_trend(quote: dict) -> dict:
    """
    基于行情数据分析趋势
    返回: {trend: "up"/"down"/"sideways", strength: 0-100, details: str}
    """
    price = quote.get("price", 0)
    prev_close = quote.get("prev_close", 0)
    change = quote.get("change", 0)

    if price <= 0 or prev_close <= 0:
        return {"trend": "unknown", "strength": 0, "details": "数据不足"}

    # 日内涨跌幅
    change_pct = change if change else ((price - prev_close) / prev_close * 100)

    # 基于日内涨跌判断短期动量
    if change_pct > 3:
        trend = "up"
        strength = min(90, 50 + int(change_pct * 5))
        details = f"强势上涨 {change_pct:.2f}%"
    elif change_pct > 0.5:
        trend = "up"
        strength = min(70, 40 + int(change_pct * 5))
        details = f"温和上涨 {change_pct:.2f}%"
    elif change_pct > -0.5:
        trend = "sideways"
        strength = 30
        details = f"横盘整理 {change_pct:.2f}%"
    elif change_pct > -3:
        trend = "down"
        strength = min(70, 40 + int(abs(change_pct) * 5))
        details = f"温和下跌 {change_pct:.2f}%"
    else:
        trend = "down"
        strength = min(90, 50 + int(abs(change_pct) * 5))
        details = f"明显下跌 {change_pct:.2f}%"

    return {"trend": trend, "strength": strength, "details": details}


def analyze_momentum(quote: dict) -> dict:
    """
    分析动量指标
    """
    change = quote.get("change", 0)
    price = quote.get("price", 0)
    prev_close = quote.get("prev_close", 0)

    if price <= 0 or prev_close <= 0:
        return {"momentum": "neutral", "score": 0}

    change_pct = change if change else ((price - prev_close) / prev_close * 100)

    # 涨跌停判断
    limit_up = quote.get("limit_up", 0)
    limit_down = quote.get("limit_down", 0)
    at_limit_up = limit_up > 0 and price >= limit_up * 0.998
    at_limit_down = limit_down > 0 and price <= limit_down * 1.002

    if at_limit_up:
        return {"momentum": "极强势", "score": 100, "note": "接近涨停"}
    elif at_limit_down:
        return {"momentum": "极弱势", "score": -100, "note": "接近跌停"}
    elif change_pct > 5:
        return {"momentum": "强势", "score": 80, "note": f"涨{change_pct:.1f}%"}
    elif change_pct > 2:
        return {"momentum": "偏强", "score": 60, "note": f"涨{change_pct:.1f}%"}
    elif change_pct > -2:
        return {"momentum": "中性", "score": 0, "note": f"震荡{change_pct:.1f}%"}
    elif change_pct > -5:
        return {"momentum": "偏弱", "score": -60, "note": f"跌{change_pct:.1f}%"}
    else:
        return {"momentum": "弱势", "score": -80, "note": f"跌{change_pct:.1f}%"}


def generate_signal(quote: dict, trend: dict, momentum: dict, sector_score: int) -> dict:
    """
    综合各维度分析，生成交易信号

    信号类型:
    - buy: 加仓买入
    - dca: 定投加仓
    - hold: 持仓观望
    - reduce: 减仓
    - take_profit: 止盈
    - wait: 等待观望（未持仓）
    """
    has_position = quote.get("position") is not None
    price = quote.get("price", 0)
    change = quote.get("change", 0)
    prev_close = quote.get("prev_close", 0)
    change_pct = change if change else ((price - prev_close) / max(prev_close, 0.01) * 100) if prev_close > 0 else 0

    t = trend["trend"]
    t_strength = trend["strength"]
    m_score = momentum["score"]
    info_score = sector_score  # 信息层板块情绪分

    reasons = []
    signal = "hold"
    confidence = "中"

    # ===== 已持仓的决策逻辑 =====
    if has_position:
        pos = quote["position"]
        profit_pct = pos.get("profit_pct", 0)

        # 强势上涨 + 信息利好 → 继续持有或加仓
        if t == "up" and t_strength >= 60 and info_score >= 20:
            signal = "buy"
            confidence = "高"
            reasons.append(f"趋势向上({trend['details']})")
            reasons.append(f"板块情绪偏多(+{info_score})")

        # 温和上涨 + 信息中性 → 持有
        elif t == "up" and t_strength < 60:
            signal = "hold"
            confidence = "中"
            reasons.append(f"温和上涨({trend['details']}), 持有观望")

        # 大涨 + 盈利较多 → 考虑止盈
        if change_pct > 5 and profit_pct > 15:
            signal = "take_profit"
            confidence = "高"
            reasons.append(f"单日涨{change_pct:.1f}%+盈利{profit_pct:.1f}%, 建议部分止盈")

        # 下跌 + 信息利空 → 减仓
        elif t == "down" and t_strength >= 60 and info_score <= -20:
            signal = "reduce"
            confidence = "高"
            reasons.append(f"下跌趋势({trend['details']})")
            reasons.append(f"板块情绪偏空({info_score})")

        # 下跌但信息利好 → 持有观望
        elif t == "down" and info_score >= 20:
            signal = "hold"
            confidence = "低"
            reasons.append(f"短期回调({trend['details']}), 但板块情绪偏多, 暂持")

        # 横盘
        elif t == "sideways":
            signal = "hold"
            confidence = "中"
            reasons.append("横盘整理, 等待方向")

    # ===== 未持仓的决策逻辑 =====
    else:
        # 趋势向上 + 板块利好 → 买入
        if t == "up" and t_strength >= 50 and info_score >= 10:
            signal = "buy"
            confidence = "高" if t_strength >= 70 else "中"
            reasons.append(f"趋势向好({trend['details']})")
            reasons.append(f"板块情绪支撑(+{info_score})")

        # 趋势向上但信息中性 → 定投
        elif t == "up" and info_score < 10:
            signal = "dca"
            confidence = "中"
            reasons.append("趋势偏强但缺乏催化, 建议小额定投")

        # 下跌 + 板块利好 → 定投（抄底）
        elif t == "down" and info_score >= 30:
            signal = "dca"
            confidence = "中"
            reasons.append(f"短期回调({trend['details']}), 板块情绪强, 可逢低定投")

        # 下跌 + 利空 → 等待
        elif t == "down" and info_score <= -10:
            signal = "wait"
            confidence = "高"
            reasons.append(f"下跌趋势+板块情绪弱, 等待企稳")

        # 横盘 → 等待或定投
        elif t == "sideways":
            if info_score >= 30:
                signal = "dca"
                confidence = "中"
                reasons.append("横盘但板块情绪强, 可小额定投")
            else:
                signal = "wait"
                confidence = "中"
                reasons.append("横盘整理中, 等待突破方向")

    return {
        "signal": signal,
        "confidence": confidence,
        "reasons": reasons,
        "trend": trend,
        "momentum": momentum,
        "has_position": has_position,
    }


# ==================== L3 主入口 ====================

def make_decisions(data_result: dict, info_result: dict) -> dict:
    """
    L3 决策层主入口

    参数:
        data_result: L1数据层输出
        info_result: L2信息层输出

    返回: 每只ETF的交易信号列表
    """
    print("[L3 决策层] 开始生成交易信号...")

    sector_scores = info_result.get("sector_scores", {})
    decisions = []

    for quote in data_result.get("quotes", []):
        if "error" in quote:
            continue

        sector = quote.get("sector", "")
        sector_score = sector_scores.get(sector, 0)

        trend = analyze_trend(quote)
        momentum = analyze_momentum(quote)
        signal = generate_signal(quote, trend, momentum, sector_score)

        decision = {
            "code": quote["code"],
            "exchange": quote["exchange"],
            "name": quote.get("name", ""),
            "sector": sector,
            "price": quote.get("price", 0),
            "change": quote.get("change", 0),
            "signal": signal["signal"],
            "confidence": signal["confidence"],
            "reasons": signal["reasons"],
            "trend_direction": signal["trend"]["trend"],
            "trend_strength": signal["trend"]["strength"],
            "momentum": signal["momentum"]["momentum"],
            "has_position": signal["has_position"],
            "position": quote.get("position"),
        }
        decisions.append(decision)

    # 按信号优先级排序: buy > dca > hold > reduce > take_profit > wait
    signal_order = {"buy": 0, "dca": 1, "hold": 2, "take_profit": 3, "reduce": 4, "wait": 5}
    decisions.sort(key=lambda d: signal_order.get(d["signal"], 99))

    # 统计
    signal_counts = {}
    for d in decisions:
        s = d["signal"]
        signal_counts[s] = signal_counts.get(s, 0) + 1

    result = {
        "decisions": decisions,
        "signal_counts": signal_counts,
        "total": len(decisions),
    }

    print(f"[L3 决策层] 完成: {len(decisions)}只ETF, 信号分布={signal_counts}")
    return result
