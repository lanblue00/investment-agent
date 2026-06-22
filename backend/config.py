"""
投研大脑 - 配置文件
定义ETF池、API参数、板块分类
"""

import os
from pathlib import Path

# ==================== API 配置 ====================

HT_APIKEY = os.environ.get("HT_APIKEY", "")
if not HT_APIKEY:
    _config_path = Path.home() / ".htsc-skills" / "config"
    if _config_path.exists():
        for line in _config_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("HT_APIKEY="):
                HT_APIKEY = line.split("=", 1)[1].strip()
                break

# API 基础地址
BASE_URL = "https://ai.zhangle.com/edge/entry/gate"
QUERY_INDICATOR_SKILL_CODE = "mx_1779108020995"
PAPER_TRADING_SKILL_CODE = "mx_1778741794549"
FINANCIAL_ANALYSIS_SKILL_CODE = "mx_1779096185749"

# 请求超时（秒）
REQUEST_TIMEOUT = 30
ANALYSIS_TIMEOUT = 120

# ==================== ETF 池定义 ====================

ETF_POOL = [
    # --- 半导体 & 芯片 ---
    {"code": "512480", "exchange": "SH", "name": "半导体ETF", "sector": "半导体", "company": "国联安"},
    {"code": "159995", "exchange": "SZ", "name": "芯片ETF", "sector": "芯片", "company": "华夏"},
    {"code": "516640", "exchange": "SH", "name": "芯片ETF", "sector": "存储芯片", "company": "景顺"},

    # --- CPO/通信 & 电子 ---
    {"code": "516880", "exchange": "SH", "name": "通信ETF", "sector": "CPO通信", "company": ""},
    {"code": "159997", "exchange": "SZ", "name": "电子ETF", "sector": "PCB电子", "company": ""},

    # --- AI 算力 ---
    {"code": "159819", "exchange": "SZ", "name": "人工智能ETF", "sector": "AI算力", "company": ""},
    {"code": "515070", "exchange": "SH", "name": "人工智能ETF", "sector": "AI算力", "company": "华宝"},

    # --- 有色金属 ---
    {"code": "512400", "exchange": "SH", "name": "有色金属ETF", "sector": "有色金属", "company": "南方"},

    # --- 黄金 ---
    {"code": "518880", "exchange": "SH", "name": "黄金ETF", "sector": "黄金", "company": "华安"},

    # --- 券商 ---
    {"code": "512000", "exchange": "SH", "name": "券商ETF", "sector": "券商", "company": "华宝"},

    # --- 新能源 ---
    {"code": "159755", "exchange": "SZ", "name": "电池ETF", "sector": "新能源电池", "company": ""},
    {"code": "515790", "exchange": "SH", "name": "光伏ETF", "sector": "光伏", "company": ""},
    {"code": "515030", "exchange": "SH", "name": "新能车ETF", "sector": "新能源车", "company": ""},

    # --- 宽基指数（基准参考） ---
    {"code": "159915", "exchange": "SZ", "name": "创业板ETF", "sector": "宽基", "company": ""},
    {"code": "588000", "exchange": "SH", "name": "科创50ETF", "sector": "宽基", "company": ""},
    {"code": "510300", "exchange": "SH", "name": "沪深300ETF", "sector": "宽基", "company": ""},
]

# 板块分类
SECTORS = list(set(etf["sector"] for etf in ETF_POOL))

# 板块分组（用于看板展示）
SECTOR_GROUPS = {
    "科技": ["半导体", "芯片", "存储芯片", "CPO通信", "PCB电子", "AI算力"],
    "资源": ["有色金属", "黄金"],
    "金融": ["券商"],
    "新能源": ["新能源电池", "光伏", "新能源车"],
    "宽基": ["宽基"],
}

# ==================== 决策层参数 ====================

# 均线周期
MA_PERIODS = [5, 10, 20, 30]

# 放量判断阈值（成交量 > 5日均量 * 此系数 = 放量）
VOLUME_SURGE_THRESHOLD = 1.5
# 缩量判断阈值（成交量 < 5日均量 * 此系数 = 缩量）
VOLUME_SHRINK_THRESHOLD = 0.7

# 单日最大建议买入比例（占总可用资金）
MAX_BUY_RATIO_PER_DAY = 0.10
# 单日最大建议卖出比例（占该ETF持仓）
MAX_SELL_RATIO_PER_DAY = 0.20
# 单一板块最大仓位比例
MAX_SECTOR_POSITION_RATIO = 0.30

# ==================== 信息层参数 ====================

# 新闻搜索关键词（按板块）
NEWS_KEYWORDS = {
    "半导体": ["半导体", "芯片", "硅片", "晶圆", "光刻"],
    "AI算力": ["AI", "人工智能", "算力", "大模型", "数据中心", "GPU"],
    "有色金属": ["有色金属", "铜", "铝", "锂", "稀土", "大宗商品"],
    "黄金": ["黄金", "金价", "避险", "美联储"],
    "券商": ["券商", "成交量", "两融", "牛市", "IPO"],
    "新能源": ["新能源", "电池", "光伏", "储能", "电动车"],
    "通信": ["光模块", "CPO", "5G", "通信", "数据中心"],
    "宏观": ["央行", "降准", "降息", "GDP", "PMI", "经济数据"],
}

# ==================== 输出路径 ====================

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUTPUT_DIR / "latest_report.json"

# ==================== 自定义ETF存储 ====================

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CUSTOM_ETFS_FILE = DATA_DIR / "custom_etfs.json"
HIDDEN_ETFS_FILE = DATA_DIR / "hidden_etfs.json"
