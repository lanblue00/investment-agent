"""
投研大脑 - ETF 管理器
搜索、添加、删除自定义ETF，合并预设+自定义ETF池
"""

import json
import re
import sys
import time
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ETF_POOL, CUSTOM_ETFS_FILE, HIDDEN_ETFS_FILE


# ==================== 板块自动识别 ====================

# 关键词 → 板块 映射（用于从ETF名称推断板块）
NAME_SECTOR_MAP = {
    "半导体": "半导体",
    "芯片": "芯片",
    "存储": "存储芯片",
    "DRAM": "存储芯片",
    "NAND": "存储芯片",
    "通信": "CPO通信",
    "光模块": "CPO通信",
    "5G": "CPO通信",
    "电子": "PCB电子",
    "PCB": "PCB电子",
    "消费电子": "PCB电子",
    "人工智能": "AI算力",
    "AI": "AI算力",
    "算力": "AI算力",
    "机器人": "AI算力",
    "计算机": "AI算力",
    "软件": "AI算力",
    "有色": "有色金属",
    "铜": "有色金属",
    "铝": "有色金属",
    "稀土": "有色金属",
    "黄金": "黄金",
    "券商": "券商",
    "证券": "券商",
    "电池": "新能源电池",
    "锂电": "新能源电池",
    "储能": "新能源电池",
    "光伏": "光伏",
    "太阳能": "光伏",
    "新能源车": "新能源车",
    "电动车": "新能源车",
    "汽车": "新能源车",
    "创业板": "宽基",
    "科创": "宽基",
    "300": "宽基",
    "50": "宽基",
    "100": "宽基",
    "医药": "医药",
    "医疗": "医药",
    "生物": "医药",
    "消费": "消费",
    "食品": "消费",
    "白酒": "消费",
    "银行": "银行",
    "保险": "保险",
    "地产": "地产",
    "房地产": "地产",
    "军工": "军工",
    "国防": "军工",
    "农业": "农业",
    "养殖": "农业",
    "旅游": "旅游",
    "传媒": "传媒",
    "游戏": "传媒",
    "影视": "传媒",
    "环保": "环保",
    "碳中和": "环保",
    "红利": "红利",
    "高股息": "红利",
    "港股": "港股",
    "恒生": "港股",
    "纳斯达克": "美股",
    "标普": "美股",
    "豆粕": "商品",
    "原油": "商品",
    "有色": "有色金属",
}


def auto_detect_sector(name: str) -> str:
    """根据ETF名称关键词自动推断板块"""
    for keyword, sector in NAME_SECTOR_MAP.items():
        if keyword in name:
            return sector
    return "其他"


# ==================== 搜索 ====================


def _detect_exchange(code: str, classify: str = "") -> tuple:
    """
    识别A股全品种交易所归属
    返回: (exchange, product_type)
      exchange: SH / SZ / OTC / ""
      product_type: 股票/场内基金/场外基金/可转债/债券/""

    参数:
      code: 6位数字代码
      classify: suggest API的Classify字段（AStock/Fund/OTCFUND/Bond等）
                有值时优先使用，避免代码前歧义
    """
    if len(code) != 6 or not code.isdigit():
        return ("", "")

    p2 = code[:2]
    p3 = code[:3]

    # ===== 优先使用 Classify（来自 suggest API，最权威） =====
    if classify == "OTCFUND":
        return ("OTC", "场外基金")
    if classify == "AStock":
        if code.startswith("6") or code.startswith("5"):
            return ("SH", "股票")
        return ("SZ", "股票")
    if classify == "Fund":
        if p2 in ("51", "56", "58", "50", "52", "55"):
            return ("SH", "场内基金")
        if p2 in ("15", "16"):
            return ("SZ", "场内基金")
        # 其他代码 + Fund → 默认场内
        return ("SH" if code.startswith("5") else "SZ", "场内基金")
    if classify == "Bond":
        if code.startswith("11"):
            return ("SH", "可转债")
        if code.startswith("12"):
            return ("SZ", "可转债")
        return ("SH", "债券")

    # ===== 无 Classify 时，按代码前缀判断（fundsuggest API / 本地调用） =====

    # --- 上海交易所 (SH) ---
    if code.startswith("60"):
        return ("SH", "股票")
    if p3 in ("688", "689"):
        return ("SH", "股票")
    if p2 in ("51", "56", "58", "50", "52", "55"):
        return ("SH", "场内基金")
    if p2 == "11":
        return ("SH", "可转债")

    # --- 深圳交易所 (SZ) ---
    if p3 in ("000", "001", "002", "003"):
        return ("SZ", "股票")
    if p3 in ("300", "301"):
        return ("SZ", "股票")
    if p2 in ("15", "16"):
        return ("SZ", "场内基金")
    if p2 == "12":
        return ("SZ", "可转债")

    # --- 场外基金 (OTC) ---
    if p2 == "00":
        return ("OTC", "场外基金")
    if p2 in ("01", "02", "20"):
        return ("OTC", "场外基金")
    if p2 in ("10", "18", "19", "21", "22"):
        return ("OTC", "场外基金")

    return ("", "")


def _fetch_suggest_items(keyword: str, count: int = 50) -> list:
    """东方财富suggest API（自动补全）"""
    url = "https://searchapi.eastmoney.com/api/suggest/get"
    params = {
        "input": keyword,
        "type": 14,
        "token": "D43BF722C8E33BDC906FB84D85E326E8",
        "count": count,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        items = data.get("QuotationCodeTable", {}).get("Data", [])
        return items if items else []
    except Exception:
        return []


def _fetch_fundsearch_items(keyword: str, pagesize: int = 30) -> list:
    """东方财富基金搜索API（更全面，返回所有基金类型）"""
    url = "https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchPageAPI.ashx"
    params = {
        "m": 1,
        "key": keyword,
        "pageindex": 1,
        "pagesize": pagesize,
        "_": str(int(time.time() * 1000)),
    }
    headers = {
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        data = resp.json()
        return data.get("Datas", [])
    except Exception:
        return []


def search_etf(keyword: str, limit: int = 15) -> list:
    """
    搜索A股全品种金融产品（股票/ETF/LOF/场外基金/可转债等）
    双引擎: fundsuggest API(全面) + suggest API(精确+分类信息)
    """
    try:
        existing_codes = set(
            e["code"] for e in ETF_POOL
        ) | set(
            e["code"] for e in get_custom_etfs()
        )
        seen_codes = set()
        results = []

        def _add_result(code, name, classify=""):
            """校验并添加到结果 — 无品种限制"""
            if code in existing_codes or code in seen_codes:
                return False
            exchange, product_type = _detect_exchange(code, classify)
            if not exchange:
                return False
            seen_codes.add(code)
            sector = auto_detect_sector(name)
            results.append({
                "code": code,
                "name": name,
                "exchange": exchange,
                "sector": sector,
                "fund_type": product_type,
            })
            return True

        # --- 引擎1: fundsuggest API (关键词搜索，更全面) ---
        fs_items = _fetch_fundsearch_items(keyword)
        for item in fs_items:
            code = str(item.get("CODE", ""))
            name = str(item.get("NAME", ""))
            _add_result(code, name)
            if len(results) >= limit:
                break

        # --- 引擎2: suggest API (自动补全 + Classify 分类信息) ---
        # 不设任何品种过滤，所有返回的金融品种都接受
        if len(results) < limit:
            sg_items = _fetch_suggest_items(keyword)
            for item in sg_items:
                code = item.get("Code", "")
                name = item.get("Name", "")
                classify = item.get("Classify", "")
                # 跳过板块(BK)、指数(Index)、美股(UsStock)等非A股交易品种
                if classify in ("BK", "Index", "UsStock", "24"):
                    continue
                _add_result(code, name, classify)
                if len(results) >= limit:
                    break

        # 排序：场内优先，场外/股票在后
        results.sort(key=lambda r: (
            0 if r["fund_type"] in ("场内基金",) else
            1 if r["fund_type"] in ("股票", "可转债", "债券") else
            2,
            r["code"]
        ))
        return results

    except Exception as e:
        return [{"error": str(e)}]


# ==================== 持久化 ====================

def get_custom_etfs() -> list:
    """从JSON文件加载自定义ETF列表"""
    if not CUSTOM_ETFS_FILE.exists():
        return []
    try:
        with open(CUSTOM_ETFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_custom_etfs(etfs: list):
    """保存自定义ETF列表到JSON文件"""
    CUSTOM_ETFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CUSTOM_ETFS_FILE, "w", encoding="utf-8") as f:
        json.dump(etfs, f, ensure_ascii=False, indent=2)


def add_custom_etf(code: str, exchange: str, name: str, sector: str = "") -> dict:
    """
    添加自定义ETF
    返回: {ok: bool, message: str}
    """
    if not sector:
        sector = auto_detect_sector(name)

    # 校验去重
    all_codes = set(e["code"] for e in ETF_POOL)
    custom = get_custom_etfs()
    for e in custom:
        all_codes.add(e["code"])

    if code in all_codes:
        return {"ok": False, "message": f"ETF {code} 已存在"}

    custom.append({
        "code": code,
        "exchange": exchange,
        "name": name,
        "sector": sector,
        "company": "",
        "is_custom": True,
    })
    _save_custom_etfs(custom)
    return {"ok": True, "message": f"已添加 {name}({code})"}


def remove_custom_etf(code: str) -> dict:
    """删除自定义ETF"""
    custom = get_custom_etfs()
    new_custom = [e for e in custom if e["code"] != code]
    if len(new_custom) == len(custom):
        return {"ok": False, "message": f"未找到自定义ETF {code}"}
    _save_custom_etfs(new_custom)
    return {"ok": True, "message": f"已移除 {code}"}


# ==================== 隐藏预设ETF ====================

def get_hidden_etfs() -> list:
    """获取被隐藏的预设ETF代码列表"""
    if not HIDDEN_ETFS_FILE.exists():
        return []
    try:
        with open(HIDDEN_ETFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_hidden_etfs(codes: list):
    """保存隐藏列表"""
    HIDDEN_ETFS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HIDDEN_ETFS_FILE, "w", encoding="utf-8") as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)


def hide_etf(code: str) -> dict:
    """隐藏预设ETF（不移除，只是不显示）"""
    hidden = get_hidden_etfs()
    if code in hidden:
        return {"ok": False, "message": f"ETF {code} 已被隐藏"}
    hidden.append(code)
    _save_hidden_etfs(hidden)
    return {"ok": True, "message": f"已隐藏 {code}"}


def unhide_etf(code: str) -> dict:
    """取消隐藏预设ETF"""
    hidden = get_hidden_etfs()
    new_hidden = [c for c in hidden if c != code]
    if len(new_hidden) == len(hidden):
        return {"ok": False, "message": f"ETF {code} 不在隐藏列表中"}
    _save_hidden_etfs(new_hidden)
    return {"ok": True, "message": f"已恢复 {code}"}


# ==================== 合并 ====================

def get_all_etfs() -> list:
    """合并预设ETF池 + 自定义ETF，排除被隐藏的预设ETF"""
    hidden = set(get_hidden_etfs())
    all_etfs = []
    # 预设（排除隐藏的）
    for etf in ETF_POOL:
        if etf["code"] in hidden:
            continue
        entry = dict(etf)
        entry["is_custom"] = False
        all_etfs.append(entry)
    # 自定义
    for etf in get_custom_etfs():
        entry = dict(etf)
        entry["is_custom"] = True
        all_etfs.append(entry)
    return all_etfs


def get_all_sectors() -> list:
    """获取所有板块（含自定义ETF引入的新板块）"""
    sectors = set()
    for etf in get_all_etfs():
        sectors.add(etf.get("sector", "其他"))
    return list(sectors)


if __name__ == "__main__":
    # 测试搜索
    print("=== 搜索 '医药' ===")
    results = search_etf("医药")
    for r in results:
        print(f"  {r['code']}.{r['exchange']} {r['name']} -> {r['sector']}")

    print(f"\n=== 当前自定义ETF: {len(get_custom_etfs())} 只 ===")
    for e in get_custom_etfs():
        print(f"  {e['code']} {e['name']} ({e['sector']})")

    print(f"\n=== 全部ETF: {len(get_all_etfs())} 只 ===")
