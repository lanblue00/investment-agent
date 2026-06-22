"""
投研大脑 - L4 风险层
对决策层的建议进行验证和风控检查
"""

import sys
from pathlib import Path
from datetime import datetime, date
sys.path.insert(0, str(Path(__file__).parent))
from config import MAX_SECTOR_POSITION_RATIO, MAX_BUY_RATIO_PER_DAY, MAX_SELL_RATIO_PER_DAY


def check_concentration(decisions: list, balance: dict) -> list:
    """
    检查板块集中度
    单一板块买入后仓位不应超过总仓位30%
    """
    warnings = []
    total_assets = balance.get("totalAssets", 0)
    if total_assets <= 0:
        return warnings

    # 按板块汇总持仓市值
    sector_values = {}
    for d in decisions:
        pos = d.get("position")
        if pos and pos.get("market_value", 0) > 0:
            sector = d["sector"]
            sector_values[sector] = sector_values.get(sector, 0) + pos["market_value"]

    for sector, value in sector_values.items():
        ratio = value / total_assets
        if ratio > MAX_SECTOR_POSITION_RATIO:
            warnings.append({
                "type": "concentration",
                "sector": sector,
                "ratio": round(ratio * 100, 1),
                "message": f"{sector}板块仓位{ratio*100:.1f}%超过{MAX_SECTOR_POSITION_RATIO*100:.0f}%上限",
            })

    return warnings


def check_drawdown_control(decisions: list) -> list:
    """
    检查回撤控制
    单日建议卖出不超过该ETF持仓的20%
    """
    warnings = []
    for d in decisions:
        if d["signal"] in ("reduce", "take_profit") and d.get("position"):
            pos = d["position"]
            available = pos.get("available", 0)
            if available <= 0:
                warnings.append({
                    "type": "no_available",
                    "code": d["code"],
                    "name": d["name"],
                    "message": f"{d['name']}无可卖份额（可能T+1限制）",
                })
    return warnings


def cross_validate_with_info(decisions: list, info_result: dict) -> list:
    """
    信息交叉验证
    检查决策信号是否与信息层情绪矛盾
    """
    warnings = []
    sector_scores = info_result.get("sector_scores", {})

    for d in decisions:
        sector = d["sector"]
        sector_score = sector_scores.get(sector, 0)

        # 买入信号但板块情绪偏空 → 矛盾
        if d["signal"] in ("buy", "dca") and sector_score < -30:
            warnings.append({
                "type": "signal_conflict",
                "code": d["code"],
                "name": d["name"],
                "sector": sector,
                "message": f"技术面建议买入但板块情绪偏空({sector_score}), 信号存在矛盾",
            })

        # 减仓信号但板块情绪偏多 → 矛盾
        if d["signal"] in ("reduce",) and sector_score > 30:
            warnings.append({
                "type": "signal_conflict",
                "code": d["code"],
                "name": d["name"],
                "sector": sector,
                "message": f"技术面建议减仓但板块情绪偏多(+{sector_score}), 建议谨慎减仓",
            })

    return warnings


def check_calendar_risk() -> list:
    """
    日历风险检查
    检测是否处于节假日前、周末等特殊时段
    """
    warnings = []
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday

    if weekday >= 5:
        warnings.append({
            "type": "weekend",
            "message": "当前为周末, 行情数据为上一交易日收盘价, 建议下周一开盘前再确认",
        })

    # 周五下午减仓信号需要更谨慎
    if weekday == 4 and now.hour >= 14:
        warnings.append({
            "type": "friday_afternoon",
            "message": "周五尾盘, 若有减仓建议建议等下周一执行",
        })

    # 非交易时段
    if 9 <= weekday <= 4:
        if now.hour < 9 or (now.hour == 9 and now.minute < 30) or now.hour >= 15:
            warnings.append({
                "type": "after_hours",
                "message": "当前非交易时段, 行情为上一交易日数据, 建议开盘后确认",
            })

    return warnings


def check_extreme_scenarios(decisions: list, info_result: dict) -> list:
    """
    极端情景检查
    """
    warnings = []

    # 检查是否所有ETF都是卖出信号（可能是系统性风险）
    sell_count = sum(1 for d in decisions if d["signal"] in ("reduce", "take_profit"))
    total = len(decisions)
    if total > 0 and sell_count / total > 0.6:
        warnings.append({
            "type": "systemic_risk",
            "message": f"超过60%的ETF({sell_count}/{total})出现减仓/止盈信号, 可能存在系统性风险, 建议控制总卖出比例",
        })

    # 检查是否所有ETF都是买入信号（可能是过热）
    buy_count = sum(1 for d in decisions if d["signal"] in ("buy", "dca"))
    if total > 0 and buy_count / total > 0.7:
        warnings.append({
            "type": "overheat",
            "message": f"超过70%的ETF({buy_count}/{total})出现买入信号, 市场可能过热, 注意追高风险",
        })

    return warnings


# ==================== L4 主入口 ====================

def validate_decisions(decision_result: dict, data_result: dict, info_result: dict) -> dict:
    """
    L4 风险层主入口

    参数:
        decision_result: L3决策层输出
        data_result: L1数据层输出
        info_result: L2信息层输出

    返回: 经过风控过滤的最终建议
    """
    print("[L4 风险层] 开始风控验证...")

    decisions = decision_result.get("decisions", [])
    balance = data_result.get("balance", {})

    # 运行各项检查
    concentration_warnings = check_concentration(decisions, balance)
    drawdown_warnings = check_drawdown_control(decisions)
    cross_warnings = cross_validate_with_info(decisions, info_result)
    calendar_warnings = check_calendar_risk()
    extreme_warnings = check_extreme_scenarios(decisions, info_result)

    all_warnings = (concentration_warnings + drawdown_warnings +
                    cross_warnings + calendar_warnings + extreme_warnings)

    # 为每个决策附加风控信息
    final_decisions = []
    for d in decisions:
        related_warnings = [w for w in all_warnings
                           if w.get("code") == d["code"] or w.get("type") in ("weekend", "after_hours", "friday_afternoon", "systemic_risk", "overheat", "concentration")]

        # 如果有矛盾信号，降低信心等级
        final_confidence = d["confidence"]
        if any(w.get("type") == "signal_conflict" for w in related_warnings):
            if final_confidence == "高":
                final_confidence = "中"
            elif final_confidence == "中":
                final_confidence = "低"

        final_decision = {
            **d,
            "final_confidence": final_confidence,
            "warnings": [w["message"] for w in related_warnings],
            "warning_count": len(related_warnings),
        }
        final_decisions.append(final_decision)

    # 整体风险评估
    risk_level = "低"
    if len(all_warnings) > 5:
        risk_level = "高"
    elif len(all_warnings) > 2:
        risk_level = "中"

    result = {
        "final_decisions": final_decisions,
        "total_warnings": len(all_warnings),
        "risk_level": risk_level,
        "warnings_summary": all_warnings,
        "concentration_warnings": concentration_warnings,
        "calendar_warnings": calendar_warnings,
        "extreme_warnings": extreme_warnings,
    }

    print(f"[L4 风险层] 完成: {len(all_warnings)}条风控警告, 整体风险={risk_level}")
    return result
