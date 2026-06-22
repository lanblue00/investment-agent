"""
投研大脑 - Pipeline 主编排脚本
串联 L1→L2→L3→L4→L5 五层，输出完整分析报告JSON
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime

# 设置路径
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR))

from config import OUTPUT_DIR, REPORT_FILE
from data_layer import collect_data
from info_layer import process_news, SAMPLE_NEWS, fetch_live_news
from decision_layer import make_decisions
from risk_layer import validate_decisions
from execution_layer import generate_execution_plan


def run_pipeline(news_items: list = None) -> dict:
    """
    运行完整的五层分析Pipeline

    参数:
        news_items: 新闻列表（可选，如不提供则使用内置样本数据）

    返回: 完整分析报告
    """
    start_time = datetime.now()
    print(f"{'='*60}")
    print(f"投研大脑 Pipeline 启动 - {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    report = {
        "meta": {
            "generated_at": start_time.isoformat(),
            "version": "1.0.0",
            "pipeline": "L1→L2→L3→L4→L5",
        },
    }

    # ===== L1: 数据层 =====
    print(f"\n{'─'*40}")
    print("Phase 1/5: 数据采集")
    print(f"{'─'*40}")
    try:
        from etf_manager import get_custom_etfs
        custom_etfs = get_custom_etfs()
        report["meta"]["custom_etf_count"] = len(custom_etfs)
        report["meta"]["custom_etf_codes"] = [e["code"] for e in custom_etfs]
        data_result = collect_data()
        report["data"] = data_result
        # 将交易日信息写入meta
        report["meta"]["trade_date"] = data_result.get("trade_date", "")
        report["meta"]["is_realtime"] = data_result.get("is_realtime", False)
    except Exception as e:
        print(f"[L1] 数据采集失败: {e}")
        data_result = {"quotes": [], "balance": {}, "positions": []}
        report["data"] = data_result

    # ===== L2: 信息层 =====
    print(f"\n{'─'*40}")
    print("Phase 2/5: 信息分析")
    print(f"{'─'*40}")
    if news_items is None:
        # 优先抓取实时新闻，失败则回退到样本数据
        try:
            live_news = fetch_live_news(page_size=20)
            if live_news:
                news_items = live_news
                print(f"[L2] 使用实时新闻数据 ({len(live_news)} 条)")
            else:
                news_items = SAMPLE_NEWS
                print("[L2] 实时新闻为空，回退到内置样本数据")
        except Exception as e:
            news_items = SAMPLE_NEWS
            print(f"[L2] 实时新闻抓取失败({e})，回退到内置样本数据")
    try:
        info_result = process_news(news_items)
        report["info"] = info_result
    except Exception as e:
        print(f"[L2] 信息分析失败: {e}")
        info_result = {"market_score": 0, "market_mood": "中性", "sector_scores": {}, "analyzed_news": []}
        report["info"] = info_result

    # ===== L3: 决策层 =====
    print(f"\n{'─'*40}")
    print("Phase 3/5: 决策生成")
    print(f"{'─'*40}")
    try:
        decision_result = make_decisions(data_result, info_result)
        report["decisions"] = decision_result
    except Exception as e:
        print(f"[L3] 决策生成失败: {e}")
        decision_result = {"decisions": [], "signal_counts": {}}
        report["decisions"] = decision_result

    # ===== L4: 风险层 =====
    print(f"\n{'─'*40}")
    print("Phase 4/5: 风控验证")
    print(f"{'─'*40}")
    try:
        risk_result = validate_decisions(decision_result, data_result, info_result)
        report["risk"] = risk_result
    except Exception as e:
        print(f"[L4] 风控验证失败: {e}")
        risk_result = {"final_decisions": [], "total_warnings": 0, "risk_level": "未知"}
        report["risk"] = risk_result

    # ===== L5: 执行层 =====
    print(f"\n{'─'*40}")
    print("Phase 5/5: 执行计划")
    print(f"{'─'*40}")
    balance = data_result.get("balance", {})
    try:
        execution_result = generate_execution_plan(risk_result, balance)
        report["execution"] = execution_result
    except Exception as e:
        print(f"[L5] 执行计划生成失败: {e}")
        execution_result = {"instructions": [], "actionable_count": 0}
        report["execution"] = execution_result

    # ===== 汇总 =====
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    report["meta"]["completed_at"] = end_time.isoformat()
    report["meta"]["elapsed_seconds"] = round(elapsed, 1)

    # 生成摘要
    summary = generate_summary(report)
    report["summary"] = summary

    # 保存JSON
    output_path = REPORT_FILE
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Pipeline 完成! 耗时 {elapsed:.1f}s")
    print(f"报告已保存: {output_path}")

    # 生成内嵌数据的Dashboard
    try:
        from build_dashboard import embed_data
        embed_data()
    except Exception as e:
        print(f"[Dashboard生成] 跳过: {e}")

    print(f"{'='*60}")

    # 打印摘要
    print(f"\n--- Summary ---")
    print(f"   ETF count: {summary['etf_count']}")
    print(f"   Market mood: {summary['market_mood']} ({summary['market_score']})")
    print(f"   Risk level: {summary['risk_level']}")
    print(f"   Actionable: {summary['actionable_count']}")
    print(f"   Buy: {summary['buy_count']} / Sell: {summary['sell_count']}")
    print(f"   Warnings: {summary['warning_count']}")

    return report


def generate_summary(report: dict) -> dict:
    """生成报告摘要"""
    data = report.get("data", {})
    info = report.get("info", {})
    decisions = report.get("decisions", {})
    risk = report.get("risk", {})
    execution = report.get("execution", {})

    return {
        "etf_count": data.get("etf_count", 0),
        "success_count": data.get("success_count", 0),
        "market_score": info.get("market_score", 0),
        "market_mood": info.get("market_mood", "中性"),
        "bullish_count": info.get("bullish_count", 0),
        "bearish_count": info.get("bearish_count", 0),
        "signal_counts": decisions.get("signal_counts", {}),
        "risk_level": risk.get("risk_level", "低"),
        "actionable_count": execution.get("actionable_count", 0),
        "buy_count": execution.get("buy_count", 0),
        "sell_count": execution.get("sell_count", 0),
        "total_buy_amount": execution.get("total_buy_amount", 0),
        "total_sell_amount": execution.get("total_sell_amount", 0),
        "warning_count": risk.get("total_warnings", 0),
        "hot_sectors": info.get("hot_sectors", []),
        "calendar_warnings": [w["message"] for w in risk.get("calendar_warnings", [])],
    }


if __name__ == "__main__":
    report = run_pipeline()
    print(f"\n完整报告: {REPORT_FILE}")
