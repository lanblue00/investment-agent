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
# 注意：以下配置为场外联接基金（exchange: OTC），与用户实际持仓一致

ETF_POOL = [
    # --- 半导体 & 芯片 ---
    {"code": "024418", "exchange": "OTC", "name": "华夏科创半导体ETF联接C", "sector": "半导体", "company": "华夏"},
    {"code": "006502", "exchange": "OTC", "name": "财通集成电路产业股票A", "sector": "芯片", "company": "财通"},

    # --- 红利 ---
    {"code": "005125", "exchange": "OTC", "name": "华宝标普中国A股红利机会ETF联接C", "sector": "红利", "company": "华宝"},

    # --- 创新药 ---
    {"code": "012738", "exchange": "OTC", "name": "广发创新药ETF联接C", "sector": "创新药", "company": "广发"},

    # --- 通信 ---
    {"code": "008087", "exchange": "OTC", "name": "华夏中证5G通信主题ETF联接C", "sector": "5G通信", "company": "华夏"},

    # --- AI 科技 ---
    {"code": "026211", "exchange": "OTC", "name": "平安科技精选混合发起式C", "sector": "AI算力", "company": "平安"},

    # --- 宽基指数 ---
    {"code": "018177", "exchange": "OTC", "name": "华夏科创50指数增强A", "sector": "宽基", "company": "华夏"},
    {"code": "001052", "exchange": "OTC", "name": "华夏中证500ETF联接A", "sector": "宽基", "company": "华夏"},
    {"code": "110020", "exchange": "OTC", "name": "易方达沪深300ETF联接A", "sector": "宽基", "company": "易方达"},

    # --- 美股 ---
    {"code": "016453", "exchange": "OTC", "name": "南方纳斯达克100指数发起(QDII)C", "sector": "美股", "company": "南方"},

    # --- 券商 ---
    {"code": "007531", "exchange": "OTC", "name": "华宝券商ETF联接C", "sector": "券商", "company": "华宝"},

    # --- 混合基金 ---
    {"code": "014915", "exchange": "OTC", "name": "财通匠心优选一年持有期混合A", "sector": "混合", "company": "财通"},
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
