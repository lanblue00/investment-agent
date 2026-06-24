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
            return {"code": code, "exchange": exchange, "name": code, "price": 0, "change": 0, "error": err_msg}
    except Exception as e:
        return {"code": code, "exchange": exchange, "name": code, "price": 0, "change": 0, "error": str(e)}


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


DEFAULT_BALANCE = {
    "totalAssets": 0,
    "availableBalance": 0,
    "frozenAmount": 0,
    "dayProfit": 0,
    "dayProfitPct": 0,
    "totalProfit": 0,
    "totalProfitPct": 0,
}


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
            bal = data["data"]
            # 确保所有必需字段存在
            for k, v in DEFAULT_BALANCE.items():
                bal.setdefault(k, v)
            return bal
        # 兼容错误格式
        msg = data.get("msg", data.get("error", {}).get("message", "请求失败"))
        return {**DEFAULT_BALANCE, "error": msg}
    except Exception as e:
        return {**DEFAULT_BALANCE, "error": str(e)}


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


# ==================== 场外基金净值获取 ====================

def _get_otc_nav(code: str) -> dict:
    """
    从东方财富获取场外基金最新净值和估算净值
    返回: {nav, nav_date, estimated_nav, estimated_change_pct, name}
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fund.eastmoney.com/",
    }

    # 接口1: 基金实时估值API（盘中返回估算值，盘后返回最新确认净值）
    url = f"https://fundgz.1234567.com.cn/js/{code}.js"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        text = resp.text.strip()
        # 格式: jsonpgz({...});
        if text.startswith("jsonpgz(") and text.endswith(");"):
            import json as _json
            data = _json.loads(text[8:-2])
            gsz = float(data.get("gsz", 0))
            gszzl = float(data.get("gszzl", 0))
            jzrq = data.get("jzrq", "")
            name = data.get("name", "")
            if gsz > 0:
                return {
                    "nav": gsz,
                    "nav_date": jzrq,
                    "estimated_nav": gsz,
                    "estimated_change_pct": gszzl,
                    "name": name,
                    "source": "estimated",
                }
    except Exception:
        pass

    # 接口2: 历史净值API取最新一条作为确认净值
    try:
        history = _get_otc_history_nav(code, limit=1)
        if history:
            latest = history[0]
            return {
                "nav": latest["nav"],
                "nav_date": latest["date"],
                "estimated_nav": latest["nav"],
                "estimated_change_pct": latest.get("change_pct", 0),
                "name": "",
                "source": "confirmed",
            }
    except Exception:
        pass

    return {"nav": 0, "nav_date": "", "estimated_nav": 0, "estimated_change_pct": 0, "name": "", "source": "none"}


def _get_otc_history_nav(code: str, limit: int = 30) -> list:
    """
    从东方财富获取场外基金历史净值（替代K线数据）
    返回: [{date, nav, change_pct}, ...]
    """
    url = "http://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "fundCode": code,
        "pageIndex": 1,
        "pageSize": limit,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://fundf10.eastmoney.com/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        history = data.get("Data", {}).get("LSJZList", [])
        klines = []
        for item in history:
            nav = item.get("DWJZ", "")
            change_pct = item.get("JZZZL", "")
            date = item.get("FSRQ", "")
            if nav and date:
                klines.append({
                    "date": date,
                    "open": float(nav),
                    "close": float(nav),
                    "high": float(nav),
                    "low": float(nav),
                    "volume": 0,
                    "nav": float(nav),
                    "change_pct": float(change_pct) if change_pct else 0,
                })
        return klines
    except Exception:
        return []


def get_otc_fund_data(code: str) -> dict:
    """
    获取场外基金完整数据（净值 + 历史净值）
    返回: {price, prev_close, change, nav, nav_date, kline, ...}
    """
    nav_data = _get_otc_nav(code)
    history = _get_otc_history_nav(code, limit=30)

    price = nav_data.get("estimated_nav", 0) or nav_data.get("nav", 0)
    change_pct = nav_data.get("estimated_change_pct", 0)

    # 从历史数据计算 prev_close（前一天的净值）
    prev_close = 0
    if history and len(history) >= 2:
        prev_close = history[1].get("nav", history[1].get("close", 0))

    # 计算 change 绝对值
    change = 0
    if prev_close > 0 and price > 0:
        change = round(price - prev_close, 4)

    return {
        "price": price,
        "prev_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "nav": nav_data.get("nav", 0),
        "nav_date": nav_data.get("nav_date", ""),
        "nav_source": nav_data.get("source", "none"),
        "kline": history,
        "fund_type": "场外",
    }


# ==================== L1 主入口 ====================

def collect_data() -> dict:
    """
    L1 数据层主入口
    获取所有ETF/场外基金行情 + 历史净值/K线 + 账户信息 + 持仓
    返回结构化数据字典
    """
    print("[L1 数据层] 开始采集行情数据...")

    # 获取完整ETF列表（预设 + 自定义）
    all_etfs = get_all_etfs()
    print(f"[L1 数据层] 共 {len(all_etfs)} 只基金 "
          f"(预设 {len(ETF_POOL)}, 自定义 {len(all_etfs) - len(ETF_POOL)})")

    # 获取所有基金行情（场内ETF实时行情 + 场外基金净值）
    quotes = []
    import time as _time
    for idx, etf in enumerate(all_etfs):
        exchange = etf.get("exchange", "")
        if exchange == "OTC":
            # 场外基金：获取净值数据（限速0.5s避免被封）
            if idx > 0:
                _time.sleep(0.5)
            otc_data = get_otc_fund_data(etf["code"])
            q = {
                "code": etf["code"],
                "exchange": "OTC",
                "name": etf["name"],
                "price": otc_data["price"],
                "prev_close": otc_data["prev_close"],
                "change": otc_data["change"],
                "change_pct": otc_data["change_pct"],
                "nav": otc_data["nav"],
                "nav_date": otc_data["nav_date"],
                "nav_source": otc_data["nav_source"],
                "volume": 0,
                "suspended": False,
                "fund_type": "场外",
                "kline": otc_data["kline"],
            }
            status = "OK" if otc_data["price"] > 0 else "NO_DATA"
        else:
            q = get_realtime_quote(etf["code"], exchange)
            status = "OK" if "error" not in q else f"ERR: {q.get('error', 'unknown')}"
        # 补充ETF元信息（name 优先用API返回的，失败时用预设名称）
        if not q.get("name") or q["name"] == q["code"]:
            q["name"] = etf["name"]
        q["sector"] = etf["sector"]
        q["company"] = etf.get("company", "")
        q["is_custom"] = etf.get("is_custom", False)
        quotes.append(q)
        custom_tag = " [custom]" if etf.get("is_custom") else ""
        print(f"  {etf['code']} {etf['name']}: {status}{custom_tag}")

    # 获取K线/历史净值数据
    print("[L1 数据层] 获取历史数据...")
    trade_date = None
    for i, etf in enumerate(all_etfs):
        exchange = etf.get("exchange", "")
        if exchange == "OTC":
            # 场外基金：使用已获取的历史净值数据
            klines = quotes[i].get("kline", [])
            quotes[i]["kline"] = klines
            if klines:
                last_date = klines[0]["date"]
                if trade_date is None:
                    trade_date = last_date
            status = f"{len(klines)} bars" if klines else "no data"
            print(f"  {etf['code']} 历史净值: {status}")
            continue
        # 场内ETF：获取K线数据
        if i > 0:
            import time as _time
            _time.sleep(0.3)  # 限速，避免被API拒绝
        klines = get_kline_history(etf["code"], etf["exchange"], limit=30)
        quotes[i]["kline"] = klines
        if klines:
            last_date = klines[-1]["date"]
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
        "success_count": sum(1 for q in quotes if "error" not in q and q.get("price", 0) > 0),
        "trade_date": trade_date,
        "is_realtime": (trade_date == today),
    }

    print(f"[L1 数据层] 完成: {result['success_count']}/{result['etf_count']} 只ETF获取成功")
    print(f"[L1 数据层] 交易日: {trade_date} {'(实时)' if trade_date == today else '(非盘中，显示最近交易日数据)'}")
    return result


if __name__ == "__main__":
    result = collect_data()
    print(json.dumps(result, ensure_ascii=False, indent=2))
