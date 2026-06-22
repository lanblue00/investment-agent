"""
投研大脑 - L1 数据层
获取ETF实时行情、历史K线、技术指标数据
"""

import json
import sys
import os
import requests
from pathlib import Path

# 将 backend 目录加入 path
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    HT_APIKEY, BASE_URL, PAPER_TRADING_SKILL_CODE,
    QUERY_INDICATOR_SKILL_CODE, ETF_POOL, REQUEST_TIMEOUT
)
from etf_manager import get_all_etfs


def _api_headers(skill_code: str) -> dict:
    """构造API请求头"""
    return {
        "Content-Type": "application/json",
        "apiKey": HT_APIKEY,
        "skillCode": skill_code,
    }


def get_realtime_quote(code: str, exchange: str) -> dict:
    """
    获取单只ETF实时行情
    返回: {name, price, prev_close, change_pct, high, low, open, volume, amount, suspended}
    """
    url = f"{BASE_URL}/api/simSkills/getQuote"
    payload = {"stockCode": code, "exchange": exchange}
    try:
        resp = requests.post(
            url, json=payload,
            headers=_api_headers(PAPER_TRADING_SKILL_CODE),
            timeout=REQUEST_TIMEOUT
        )
        data = resp.json()
        if data.get("ok"):
            d = data["data"]
            return {
                "code": code,
                "exchange": exchange,
                "name": d.get("stockName", ""),
                "price": d.get("currentPrice", 0),
                "prev_close": d.get("prevClose", 0),
                "change": d.get("change", 0),
                "limit_up": d.get("limitUp", 0),
                "limit_down": d.get("limitDown", 0),
                "bid": d.get("bidPrice1", 0),
                "ask": d.get("askPrice1", 0),
                "suspended": d.get("isSuspended", False),
            }
        else:
            err = data.get("error", {})
            err_msg = err.get("message", "") if isinstance(err, dict) else ""
            if not err_msg:
                err_msg = data.get("msg", "未知错误")
            return {"code": code, "exchange": exchange, "error": err_msg}
    except Exception as e:
        return {"code": code, "exchange": exchange, "error": str(e)}


def query_indicator(query: str) -> str:
    """
    通过query-indicator API查询行情指标
    返回Markdown格式的分析文本
    """
    url = f"{BASE_URL}/api/finAnalysis/queryIndicator"
    payload = {"query": query}
    try:
        resp = requests.post(
            url, json=payload,
            headers=_api_headers(QUERY_INDICATOR_SKILL_CODE),
            timeout=REQUEST_TIMEOUT
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("data", {}).get("answer", "")
        return ""
    except Exception as e:
        return f"查询失败: {e}"


def market_insight(query: str) -> str:
    """
    通过financial-analysis API获取市场洞察
    返回分析文本
    """
    url = f"{BASE_URL}/api/finAnalysis/marketInsight"
    payload = {"query": query}
    try:
        resp = requests.post(
            url, json=payload,
            headers=_api_headers("mx_1779096185749"),
            timeout=120  # 分析接口超时较长
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("data", {}).get("answer", "")
        return ""
    except Exception as e:
        return f"查询失败: {e}"


def get_account_balance() -> dict:
    """获取模拟盘账户余额"""
    url = f"{BASE_URL}/api/simSkills/getAccountBalance"
    try:
        resp = requests.post(
            url, json={},
            headers=_api_headers(PAPER_TRADING_SKILL_CODE),
            timeout=REQUEST_TIMEOUT
        )
        data = resp.json()
        if data.get("ok"):
            return data["data"]
        # 兼容错误格式
        msg = data.get("msg", data.get("error", {}).get("message", "请求失败"))
        return {"error": msg}
    except Exception as e:
        return {"error": str(e)}


def get_positions() -> list:
    """获取模拟盘当前持仓"""
    url = f"{BASE_URL}/api/simSkills/getPositions"
    try:
        resp = requests.post(
            url, json={},
            headers=_api_headers(PAPER_TRADING_SKILL_CODE),
            timeout=REQUEST_TIMEOUT
        )
        data = resp.json()
        if data.get("ok"):
            return data["data"].get("positions", [])
        return []
    except Exception as e:
        return []


def _get_kline_tencent(code: str, exchange: str, limit: int) -> list:
    """
    从腾讯财经接口获取日K线（主数据源，稳定可靠）
    返回: [{date, open, close, high, low, volume}, ...]
    """
    import json as _json
    prefix = "sh" if exchange == "SH" else "sz"
    symbol = f"{prefix}{code}"
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    params = {
        "param": f"{symbol},day,,,{limit},qfq",
        "_var": "kline_dayqfq",
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    text = resp.text
    # 去除 var 赋值前缀
    if "=" in text and text.startswith("kline_"):
        text = text.split("=", 1)[1]
    data = _json.loads(text)
    stock_data = data.get("data", {}).get(symbol, {})
    bars = stock_data.get("qfqday", []) or stock_data.get("day", [])
    klines = []
    for bar in bars:
        if len(bar) >= 6:
            klines.append({
                "date": bar[0],
                "open": float(bar[1]),
                "close": float(bar[2]),
                "high": float(bar[3]),
                "low": float(bar[4]),
                "volume": int(float(bar[5])),
            })
    return klines


def _get_kline_eastmoney(code: str, exchange: str, limit: int) -> list:
    """
    从东方财富接口获取日K线（备用数据源）
    返回: [{date, open, close, high, low, volume, amount, change_pct}, ...]
    """
    market = "1" if exchange == "SH" else "0"
    secid = f"{market}.{code}"
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": 101,
        "fqt": 0,
        "lmt": limit,
        "end": "20500101",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "http://quote.eastmoney.com",
    }
    resp = requests.get(url, params=params, headers=headers, timeout=15)
    data = resp.json()
    if data.get("data") and data["data"].get("klines"):
        klines = []
        for line in data["data"]["klines"]:
            parts = line.split(",")
            if len(parts) >= 11:
                klines.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": int(parts[5]),
                    "amount": float(parts[6]),
                    "change_pct": float(parts[8]),
                })
        return klines
    return []


def get_kline_history(code: str, exchange: str, limit: int = 30) -> list:
    """
    获取真实日K线数据，优先腾讯财经，备用东方财富
    返回: [{date, open, close, high, low, volume}, ...]
    """
    # 主数据源: 腾讯财经
    try:
        klines = _get_kline_tencent(code, exchange, limit)
        if klines:
            return klines
    except Exception:
        pass

    # 备用数据源: 东方财富
    try:
        klines = _get_kline_eastmoney(code, exchange, limit)
        if klines:
            return klines
    except Exception:
        pass

    return []


def get_trade_date(quotes: list) -> str:
    """
    从行情数据推断最近交易日
    盘前/周末/节假日时，API返回的是上一个交易日数据
    """
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    # 如果有任何K线数据，取最后一条的日期
    # 否则用今天日期
    return today


# ==================== L1 主入口 ====================

def collect_data() -> dict:
    """
    L1 数据层主入口
    获取所有ETF(预设+自定义)实时行情 + K线历史 + 账户信息 + 持仓
    返回结构化数据字典
    """
    print("[L1 数据层] 开始采集行情数据...")

    # 获取完整ETF列表（预设 + 自定义）
    all_etfs = get_all_etfs()
    print(f"[L1 数据层] 共 {len(all_etfs)} 只ETF "
          f"(预设 {len(ETF_POOL)}, 自定义 {len(all_etfs) - len(ETF_POOL)})")

    # 获取所有ETF实时行情
    quotes = []
    for etf in all_etfs:
        exchange = etf.get("exchange", "")
        if exchange == "OTC":
            # 场外基金：无法通过场内API获取实时行情，设置默认值
            q = {
                "code": etf["code"],
                "name": etf["name"],
                "exchange": "OTC",
                "price": 0,
                "change": 0,
                "volume": 0,
                "suspended": False,
                "fund_type": "场外",
                "note": "场外基金，请在券商APP查看净值",
            }
        else:
            q = get_realtime_quote(etf["code"], exchange)
        # 补充ETF元信息
        q["sector"] = etf["sector"]
        q["company"] = etf.get("company", "")
        q["is_custom"] = etf.get("is_custom", False)
        quotes.append(q)
        status = "OK" if "error" not in q else f"ERR: {q.get('error', 'unknown')}"
        if exchange == "OTC":
            status = "SKIP(场外)"
        custom_tag = " [custom]" if etf.get("is_custom") else ""
        print(f"  {etf['code']} {etf['name']}: {status}{custom_tag}")

    # 获取K线历史数据（真实数据，腾讯财经主 + 东方财富备）
    print("[L1 数据层] 获取K线历史数据...")
    trade_date = None
    for i, etf in enumerate(all_etfs):
        exchange = etf.get("exchange", "")
        if exchange == "OTC":
            # 场外基金没有K线数据
            quotes[i]["kline"] = []
            print(f"  {etf['code']} K-line: SKIP(场外)")
            continue
        if i > 0:
            import time as _time
            _time.sleep(0.3)  # 限速，避免被API拒绝
        klines = get_kline_history(etf["code"], etf["exchange"], limit=30)
        quotes[i]["kline"] = klines
        if klines:
            last_date = klines[-1]["date"]
            # 用第一只有K线数据的ETF确定交易日
            if trade_date is None:
                trade_date = last_date
        status = f"{len(klines)} bars" if klines else "no data"
        print(f"  {etf['code']} K-line: {status}")

    # 获取账户信息
    print("[L1 数据层] 获取账户信息...")
    balance = get_account_balance()
    positions = get_positions()

    # 构建持仓映射
    position_map = {}
    for pos in positions:
        key = f"{pos.get('stockCode', '')}_{pos.get('exchange', '')}"
        position_map[key] = pos

    # 合并持仓到行情
    for q in quotes:
        key = f"{q['code']}_{q['exchange']}"
        if key in position_map:
            p = position_map[key]
            q["position"] = {
                "quantity": p.get("quantity", 0),
                "available": p.get("availableQuantity", 0),
                "cost_price": p.get("costPrice", 0),
                "market_value": p.get("marketValue", 0),
                "profit": p.get("profit", 0),
                "profit_pct": p.get("profitPct", 0),
            }
        else:
            q["position"] = None

    # 确定实际交易日（K线最后一天的日期，非当天日期）
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    if trade_date is None:
        trade_date = today

    result = {
        "quotes": quotes,
        "balance": balance,
        "positions": positions,
        "etf_count": len(quotes),
        "success_count": sum(1 for q in quotes if "error" not in q),
        "trade_date": trade_date,
        "is_realtime": (trade_date == today),
    }

    print(f"[L1 数据层] 完成: {result['success_count']}/{result['etf_count']} 只ETF获取成功")
    print(f"[L1 数据层] 交易日: {trade_date} {'(实时)' if trade_date == today else '(非盘中，显示最近交易日数据)'}")
    return result


if __name__ == "__main__":
    result = collect_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
