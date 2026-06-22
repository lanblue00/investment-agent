"""
投研大脑 - L2 信息层
获取并分析财经新闻、政策动态、市场情绪
注意: finance-news-source未安装，此处使用内置的静态分析逻辑
在实际运行时，由Pipeline传入通过WebSearch获取的新闻数据
"""

import sys
import time
import requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from config import NEWS_KEYWORDS
from etf_manager import get_all_sectors


# ==================== 情感分析关键词 ====================

BULLISH_KEYWORDS = [
    "利好", "上涨", "大涨", "涨停", "突破", "新高", "放量",
    "政策扶持", "补贴", "超预期", "订单", "涨价", "回购", "增持",
    "并购", "重组", "技术突破", "景气度提升", "需求增长",
    "降息", "降准", "宽松", "刺激", "改革", "开放",
    "资金流入", "北向买入", "融资增加",
]

BEARISH_KEYWORDS = [
    "利空", "下跌", "大跌", "跌停", "破位", "新低", "缩量",
    "监管处罚", "调查", "暴雷", "取消", "降价", "减持", "质押",
    "诉讼", "技术失败", "需求下滑",
    "加息", "收紧", "制裁", "限制", "贸易战",
    "资金流出", "北向卖出", "融资减少", "解禁", "IPO",
]

# 板块关联词映射
SECTOR_KEYWORD_MAP = {
    "半导体": ["半导体", "芯片", "硅片", "晶圆", "光刻", "封测", "制程", "GPU"],
    "芯片": ["芯片", "半导体", "集成电路", "MCU", "SoC"],
    "存储芯片": ["存储", "DRAM", "NAND", "闪存", "HBM", "美光"],
    "CPO通信": ["光模块", "CPO", "5G", "通信", "光纤", "数据中心", "交换机"],
    "PCB电子": ["PCB", "电路板", "电子", "消费电子", "苹果"],
    "AI算力": ["AI", "人工智能", "算力", "大模型", "ChatGPT", "AGI", "智算"],
    "有色金属": ["有色", "铜", "铝", "锂", "稀土", "大宗商品", "期货"],
    "黄金": ["黄金", "金价", "避险", "美联储", "利率", "美元"],
    "券商": ["券商", "成交", "两融", "牛市", "IPO", "资本市场", "基金"],
    "新能源电池": ["电池", "锂电", "储能", "宁德时代", "比亚迪"],
    "光伏": ["光伏", "太阳能", "硅料", "组件", "装机"],
    "新能源车": ["新能源车", "电动车", "充电桩", "智能驾驶", "特斯拉"],
    "宽基": ["大盘", "指数", "A股", "市场", "沪指", "深指", "创业板"],
}


def analyze_sentiment(text: str) -> dict:
    """
    分析单条新闻的情感倾向
    返回: {sentiment: "bullish"/"bearish"/"neutral", score: -100~100, reasons: []}
    """
    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text)

    total = bullish_count + bearish_count
    if total == 0:
        return {"sentiment": "neutral", "score": 0, "reasons": ["无明显利好/利空信号"]}

    score = int((bullish_count - bearish_count) / total * 100)

    if score > 20:
        sentiment = "bullish"
    elif score < -20:
        sentiment = "bearish"
    else:
        sentiment = "neutral"

    reasons = []
    for kw in BULLISH_KEYWORDS:
        if kw in text:
            reasons.append(f"利好: {kw}")
    for kw in BEARISH_KEYWORDS:
        if kw in text:
            reasons.append(f"利空: {kw}")

    return {"sentiment": sentiment, "score": score, "reasons": reasons[:5]}


def _ensure_sector_keywords():
    """确保所有板块(含自定义ETF引入的新板块)都有对应的关键词"""
    all_sectors = get_all_sectors()
    for sector in all_sectors:
        if sector not in SECTOR_KEYWORD_MAP:
            # 用板块名称本身作为关键词
            SECTOR_KEYWORD_MAP[sector] = [sector]


def identify_related_sectors(text: str) -> list:
    """识别新闻关联的板块"""
    _ensure_sector_keywords()
    related = []
    for sector, keywords in SECTOR_KEYWORD_MAP.items():
        if any(kw in text for kw in keywords):
            related.append(sector)
    return related


def assess_impact_level(text: str) -> str:
    """评估新闻影响级别: market / sector / company"""
    market_keywords = ["央行", "降准", "降息", "GDP", "PMI", "贸易战", "美联储",
                       "加息", "降准", "MLF", "LPR", "政治局", "国务院"]
    if any(kw in text for kw in market_keywords):
        return "market"

    sector_keywords = ["行业", "板块", "产业链", "补贴", "政策", "标准", "规范"]
    if any(kw in text for kw in sector_keywords):
        return "sector"

    return "company"


# ==================== 实时新闻抓取 ====================

def fetch_live_news(page_size: int = 20) -> list:
    """
    从东方财富获取实时财经新闻
    返回: [{"title", "source", "time", "url", "summary"}, ...]
    失败时返回空列表，由调用方回退到 SAMPLE_NEWS
    """
    print("[L2 信息层] 正在从东方财富抓取实时新闻...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://finance.eastmoney.com/",
    }

    all_articles = []
    seen_urls = set()

    # 多栏目抓取: 350=财经要闻, 11791=券商, 1345=半导体/AI科技
    columns = ["350", "11791"]
    for col in columns:
        try:
            url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
            params = {
                "client": "web",
                "biz": "web_news_col",
                "column": col,
                "order": 1,
                "needInteractData": 0,
                "page_index": 1,
                "page_size": page_size,
                "req_trace": str(int(time.time() * 1000)),
            }
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            data = resp.json()
            articles = data.get("data", {}).get("list", [])
            for art in articles:
                art_url = art.get("uniqueUrl", "") or art.get("url", "")
                if not art_url or art_url in seen_urls:
                    continue
                seen_urls.add(art_url)

                title = art.get("title", "").strip()
                if not title:
                    continue

                # 提取时间: "2026-06-23 03:40:59" → "HH:MM"
                show_time = art.get("showTime", "")
                time_short = show_time
                if " " in show_time:
                    time_part = show_time.split(" ")[1]
                    time_short = time_part[:5]  # "03:40"

                all_articles.append({
                    "title": title,
                    "source": art.get("mediaName", "东方财富") or "东方财富",
                    "time": time_short,
                    "url": art_url,
                    "summary": art.get("summary", "")[:200],
                })
        except Exception as e:
            print(f"  [L2] 栏目{col}抓取失败: {e}")
            continue

        # 限速
        time.sleep(0.3)

    # 限制总数
    all_articles = all_articles[:page_size]

    if all_articles:
        print(f"  [L2] 成功抓取 {len(all_articles)} 条实时新闻")
    else:
        print("  [L2] 未抓取到新闻")

    return all_articles


def process_news(news_items: list) -> dict:
    """
    L2 信息层主入口
    处理新闻列表，输出结构化分析结果

    参数: news_items = [{"title": "...", "source": "...", "time": "...", "url": "..."}]
    返回: 结构化分析结果
    """
    print(f"[L2 信息层] 开始分析 {len(news_items)} 条新闻...")

    analyzed = []
    dynamic_sectors = get_all_sectors()
    sector_sentiment = {s: [] for s in dynamic_sectors}
    all_scores = []

    for item in news_items:
        text = item.get("title", "") + " " + item.get("summary", "")

        sentiment = analyze_sentiment(text)
        related_sectors = identify_related_sectors(text)
        impact_level = assess_impact_level(text)

        analyzed_item = {
            **item,
            "sentiment": sentiment["sentiment"],
            "score": sentiment["score"],
            "reasons": sentiment["reasons"],
            "related_sectors": related_sectors,
            "impact_level": impact_level,
        }
        analyzed.append(analyzed_item)
        all_scores.append(sentiment["score"])

        for sector in related_sectors:
            if sector in sector_sentiment:
                sector_sentiment[sector].append(sentiment["score"])

    # 计算整体市场情绪
    market_score = int(sum(all_scores) / max(len(all_scores), 1))
    if market_score > 20:
        market_mood = "偏多"
    elif market_score < -20:
        market_mood = "偏空"
    else:
        market_mood = "中性"

    # 计算各板块情绪
    sector_scores = {}
    for sector, scores in sector_sentiment.items():
        if scores:
            sector_scores[sector] = int(sum(scores) / len(scores))
        else:
            sector_scores[sector] = 0

    # 统计
    bullish_count = sum(1 for a in analyzed if a["sentiment"] == "bullish")
    bearish_count = sum(1 for a in analyzed if a["sentiment"] == "bearish")
    neutral_count = sum(1 for a in analyzed if a["sentiment"] == "neutral")

    result = {
        "news_count": len(analyzed),
        "market_score": market_score,
        "market_mood": market_mood,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "sector_scores": sector_scores,
        "analyzed_news": analyzed,
        "hot_sectors": [s for s, sc in sorted(sector_scores.items(), key=lambda x: -x[1])[:5] if sc != 0],
    }

    print(f"[L2 信息层] 完成: 市场情绪={market_mood}({market_score}), "
          f"利好{bullish_count}/利空{bearish_count}/中性{neutral_count}")
    return result


# ==================== 静态新闻数据（用于离线测试） ====================

SAMPLE_NEWS = [
    {"title": "央行推进外汇市场双向开放，六家银行获批自贸区离岸人民币外汇交易试点", "source": "新浪财经", "time": "08:30", "url": "https://k.sina.cn/article_7857201856_1d45362c0019074pw4.html?from=finance"},
    {"title": "信越化学等三大国际巨头同步上调12英寸硅片价格，半导体材料迎来涨价潮", "source": "证券时报", "time": "09:15", "url": "https://m.toutiao.com/a7651882850316223030/"},
    {"title": "美光科技业绩预期大增，存储芯片景气度持续向好", "source": "第一财经", "time": "10:00", "url": "https://wap.eastmoney.com/a/202606223778287939.html"},
    {"title": "苹果折叠屏iPhone供应链已开始小批量供货，消费电子板块受益", "source": "21世纪经济", "time": "08:45", "url": "https://finance.sina.com.cn/tech/roll/2026-06-22/doc-iniefuxy0450382.shtml"},
    {"title": "韩国突破芯片液冷技术，叠加美国数据中心缺电，利好液冷服务器", "source": "财联社", "time": "09:30", "url": "https://www.cls.cn/detail/2403007"},
    {"title": "微信原生AI助手开启内测，AI应用落地加速", "source": "36氪", "time": "11:00", "url": "https://m.36kr.com/newsflashes/3858353349645318"},
    {"title": "贵州茅台2025年度每股派发现金红利28.02元", "source": "上交所", "time": "16:30", "url": "https://finance.sina.cn/2026-06-21/detail-inieepen9594422.d.html"},
    {"title": "高盛下调金价预期，贵金属板块承压", "source": "华尔街见闻", "time": "07:00", "url": "https://m.21jingji.com/article/20260621/herald/6436056d4dff8536c7d5e7d4f198ba90.html"},
    {"title": "本周49家公司限售股解禁，总解禁市值达549亿元", "source": "东方财富", "time": "08:00", "url": "https://finance.sina.com.cn/roll/2026-06-22/doc-iniefzfw0332647.shtml"},
    {"title": "深交所史上最大规模IPO华润新能源今日申购", "source": "深圳商报", "time": "09:25", "url": "https://m.163.com/dy/article/L02NM9LK05199NPP.html"},
    {"title": "智微智能拟购买服务器及配套设备，总金额不超过40亿元，算力投入加码", "source": "公告", "time": "17:00", "url": "https://finance.sina.cn/2026-06-22/detail-iniefuxz7108686.d.html"},
    {"title": "七部门发文规范平台经济，净化直播电商行业生态", "source": "新华社", "time": "10:30", "url": "https://new.qq.com/rain/a/20260618A06GNT00"},
]


if __name__ == "__main__":
    result = process_news(SAMPLE_NEWS)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
