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
    {"code": "588170", "exchange": "SH", "name": "科创半导体ETF", "sector": "半导体", "company": "华夏"},   # ← 024418 华夏科创半导体ETF联接C
    {"code": "159995", "exchange": "SZ", "name": "芯片ETF", "sector": "芯片", "company": "华夏"},          # ← 006502 财通集成电路(半导体方向)

    # --- 红利 ---
    {"code": "562060", "exchange": "SH", "name": "红利ETF", "sector": "红利", "company": "华宝"},          # ← 005125 华宝红利机会ETF联接C

    # --- 创新药 ---
    {"code": "159992", "exchange": "SZ", "name": "创新药ETF", "sector": "创新药", "company": "广发"},       # ← 012738 广发创新药ETF联接C

    # --- 通信 ---
    {"code": "515880", "exchange": "SH", "name": "通信ETF", "sector": "5G通信", "company": "国泰"},         # ← 008087 华夏中证5G通信ETF联接C

    # --- AI 科技 ---
    {"code": "159819", "exchange": "SZ", "name": "人工智能ETF", "sector": "AI算力", "company": ""},         # ← 026211 平安科技精选混合C(科技方向)

    # --- 宽基指数 ---
    {"code": "588000", "exchange": "SH", "name": "科创50ETF", "sector": "宽基", "company": ""},             # ← 018177 华夏科创50指数增强A
    {"code": "512500", "exchange": "SH", "name": "中证500ETF", "sector": "宽基", "company": "华夏"},        # ← 001052 华夏中证500ETF联接A
    {"code": "510300", "exchange": "SH", "name": "沪深300ETF", "sector": "宽基", "company": ""},            # ← 110020 易方达沪深300ETF联接A

    # --- 美股 ---
    {"code": "159632", "exchange": "SZ", "name": "纳斯达克ETF", "sector": "美股", "company": "华安"},       # ← 016453 南方纳斯达克100(QDII)C

    # --- 券商 ---
    {"code": "512000", "exchange": "SH", "name": "券商ETF", "sector": "券商", "company": "华宝"},           # ← 007531 华宝券商ETF联接C

    # --- 黄金 ---
    {"code": "518880", "exchange": "SH", "name": "黄金ETF", "sector": "黄金", "company": "华安"},           # ← 京东黄金积存金 1.0096克
]

# 板块分类
SECTORS = list(set(etf["sector"] for etf in ETF_POOL))

# 板块分组（用于看板展示）
SECTOR_GROUPS = {
    "科技": ["半导体", "芯片", "5G通信", "AI算力"],
    "医药": ["创新药"],
    "价值": ["红利"],
    "金融": ["券商"],
    "海外": ["美股"],
    "避险": ["黄金"],
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
    "半导体": ["半导体", "芯片", "硅片", "晶圆", "光刻", "集成电路"],
    "AI算力": ["AI", "人工智能", "算力", "大模型", "数据中心", "GPU"],
    "5G通信": ["5G", "通信", "光模块", "CPO", "基站"],
    "创新药": ["创新药", "医药", "生物", "新药", "临床试验", "FDA"],
    "红利": ["红利", "高股息", "分红", "价值投资"],
    "黄金": ["黄金", "金价", "避险", "美联储"],
    "券商": ["券商", "成交量", "两融", "牛市", "IPO"],
    "美股": ["纳斯达克", "美股", "美联储", "英伟达", "苹果", "科技股"],
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
