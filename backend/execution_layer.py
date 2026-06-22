"""
投研大脑 - L5 执行层
将风控后的决策建议转为结构化的可执行交易指令
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import MAX_BUY_RATIO_PER_DAY


# 信号→中文操作名称
SIGNAL_LABELS = {
    "buy": "买入加仓",
    "dca": "定投加仓",
    "hold": "持仓观望",
    "reduce": "减仓卖出",
    "take_profit": "止盈离场",
    "wait": "等待观望",
}

# 信号→颜色（前端用）
SIGNAL_COLORS = {
    "buy": "#e74c3c",
    "dca": "#e67e22",
    "hold": "#3498db",
    "reduce": "#2ecc71",
    "take_profit": "#f39c12",
    "wait": "#95a5a6",
}

# 信心等级→颜色
CONFIDENCE_COLORS = {
    "高": "#e74c3c",
    "中": "#f39c12",
    "低": "#95a5a6",
}


def calculate_suggested_quantity(decision: dict, balance: dict) -> int:
    """
    计算建议交易数量（ETF最小单位100份）

    买入: 根据可用资金和建议比例计算
    卖出: 根据持仓可卖数量和建议比例计算
    """
    signal = decision["signal"]
    price = decision.get("price", 0)
    available_balance = balance.get("availableBalance", 0)
    position = decision.get("position")

    if price <= 0:
        return 0

    if signal in ("buy", "dca"):
        if signal == "dca":
            # 定投金额较小（每次500-1000元）
            target_amount = min(1000, available_balance * 0.02)
        else:
            # 正常买入
            target_amount = available_balance * MAX_BUY_RATIO_PER_DAY
            target_amount = min(target_amount, 5000)  # 单笔上限5000

        quantity = int(target_amount / price / 100) * 100
        return max(quantity, 100)

    elif signal in ("reduce", "take_profit"):
        if not position:
            return 0
        available = position.get("available", 0)
        if signal == "take_profit":
            ratio = 0.5  # 止盈卖一半
        else:
            ratio = 0.2  # 减仓卖20%
        quantity = int(available * ratio / 100) * 100
        return max(quantity, 0)

    return 0


def generate_trade_instruction(decision: dict, balance: dict) -> dict:
    """
    为单个决策生成交易指令
    """
    signal = decision["signal"]
    quantity = calculate_suggested_quantity(decision, balance)
    price = decision.get("price", 0)
    amount = round(quantity * price, 2) if quantity > 0 else 0

    instruction = {
        "code": decision["code"],
        "exchange": decision["exchange"],
        "name": decision.get("name", ""),
        "sector": decision.get("sector", ""),
        "signal": signal,
        "signal_label": SIGNAL_LABELS.get(signal, signal),
        "signal_color": SIGNAL_COLORS.get(signal, "#95a5a6"),
        "confidence": decision.get("final_confidence", decision.get("confidence", "中")),
        "confidence_color": CONFIDENCE_COLORS.get(decision.get("final_confidence", "中"), "#95a5a6"),
        "price": price,
        "change": decision.get("change", 0),
        "quantity": quantity,
        "amount": amount,
        "reasons": decision.get("reasons", []),
        "warnings": decision.get("warnings", []),
        "has_position": decision.get("has_position", False),
        "position": decision.get("position"),
        "trend": decision.get("trend_direction", ""),
        "momentum": decision.get("momentum", ""),
        "actionable": signal in ("buy", "dca", "reduce", "take_profit") and quantity > 0,
    }

    return instruction


# ==================== L5 主入口 ====================

def generate_execution_plan(risk_result: dict, balance: dict) -> dict:
    """
    L5 执行层主入口

    参数:
        risk_result: L4风险层输出
        balance: 账户余额信息

    返回: 结构化交易指令列表
    """
    print("[L5 执行层] 生成交易指令...")

    final_decisions = risk_result.get("final_decisions", [])
    instructions = []

    for decision in final_decisions:
        inst = generate_trade_instruction(decision, balance)
        instructions.append(inst)

    # 分类统计
    actionable = [i for i in instructions if i["actionable"]]
    buy_instructions = [i for i in actionable if i["signal"] in ("buy", "dca")]
    sell_instructions = [i for i in actionable if i["signal"] in ("reduce", "take_profit")]
    watch_instructions = [i for i in instructions if not i["actionable"]]

    total_buy_amount = sum(i["amount"] for i in buy_instructions)
    total_sell_amount = sum(i["amount"] for i in sell_instructions)

    result = {
        "instructions": instructions,
        "actionable_count": len(actionable),
        "buy_count": len(buy_instructions),
        "sell_count": len(sell_instructions),
        "watch_count": len(watch_instructions),
        "total_buy_amount": round(total_buy_amount, 2),
        "total_sell_amount": round(total_sell_amount, 2),
        "net_amount": round(total_buy_amount - total_sell_amount, 2),
        "risk_level": risk_result.get("risk_level", "低"),
        "total_warnings": risk_result.get("total_warnings", 0),
    }

    print(f"[L5 执行层] 完成: {len(actionable)}条可执行指令, "
          f"买入{len(buy_instructions)}笔({total_buy_amount:.0f}元) / "
          f"卖出{len(sell_instructions)}笔({total_sell_amount:.0f}元)")
    return result
