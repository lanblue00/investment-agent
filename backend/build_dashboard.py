"""
投研大脑 - Dashboard 生成器
将最新的分析JSON嵌入到dashboard.html模板中，生成可直接打开的独立HTML文件
"""

import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
TEMPLATE_PATH = PROJECT_DIR / "frontend" / "dashboard.html"
JSON_PATH = PROJECT_DIR / "output" / "latest_report.json"
OUTPUT_PATH = PROJECT_DIR / "output" / "index.html"


def embed_data():
    """将JSON数据嵌入HTML模板，生成独立可打开的dashboard"""

    # 读取JSON报告
    if not JSON_PATH.exists():
        print(f"[ERROR] 报告文件不存在: {JSON_PATH}")
        print("请先运行 pipeline.py 生成报告")
        return False

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    # 读取HTML模板
    if not TEMPLATE_PATH.exists():
        print(f"[ERROR] 模板文件不存在: {TEMPLATE_PATH}")
        return False

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        html_template = f.read()

    # 生成内嵌数据的script标签
    json_str = json.dumps(report_data, ensure_ascii=False, indent=2)
    embedded_script = f'<script id="embedded-data" type="application/json">{json_str}</script>'

    # 在 </head> 前插入内嵌数据
    if "</head>" in html_template:
        html_output = html_template.replace("</head>", f"{embedded_script}\n</head>")
    else:
        # fallback: 在 <body> 前插入
        html_output = html_template.replace("<body>", f"{embedded_script}\n<body>")

    # 同时修改fetch逻辑：优先使用内嵌数据
    # 在JS中添加一个检测函数
    override_fetch = """
<script>
// 静态部署模式：内嵌数据 + 拦截所有API调用
(function() {
  var embeddedEl = document.getElementById('embedded-data');
  if (embeddedEl) {
    window.STATIC_MODE = true;
    var embeddedData = JSON.parse(embeddedEl.textContent);
    var origFetch = window.fetch;
    window.fetch = function(url, opts) {
      if (typeof url === 'string') {
        // /api/report → 返回内嵌报告数据
        if (url.includes('/api/report') || url.includes('latest_report.json')) {
          return Promise.resolve(new Response(JSON.stringify(embeddedData), {
            status: 200, headers: {'Content-Type': 'application/json'}
          }));
        }
        // /api/pipeline/status → 返回空闲状态
        if (url.includes('/api/pipeline/status')) {
          return Promise.resolve(new Response('{"running":false}', {
            status: 200, headers: {'Content-Type': 'application/json'}
          }));
        }
        // /api/custom → 返回内嵌的自定义ETF列表（如果有）
        if (url.includes('/api/custom')) {
          return Promise.resolve(new Response('{"custom_etfs":[]}', {
            status: 200, headers: {'Content-Type': 'application/json'}
          }));
        }
        // 其他API（搜索/添加/删除）→ 提示静态模式，但 /api/chat 放行
        if (url.includes('/api/') && !url.includes('/api/chat')) {
          return Promise.resolve(new Response(JSON.stringify({error:'static_mode'}), {
            status: 503, headers: {'Content-Type': 'application/json'}
          }));
        }
      }
      return origFetch.apply(this, arguments);
    };
    console.log('[Dashboard] 静态部署模式 — 数据内嵌，仅查看');
  }
})();
</script>
"""

    if "</head>" in html_output:
        # Insert fetch override first
        html_output = html_output.replace("</head>", f"{override_fetch}\n</head>")
        # Then add static mode styles
        static_style = """
<style>
/* Static mode: hide interactive elements that require backend */
.etf-search-wrap { display: none !important; }
.etf-remove-btn { display: none !important; }
.static-mode-badge {
  display: inline-flex !important; align-items: center; gap: 4px;
  font-size: 11px; padding: 2px 10px; border-radius: 3px;
  background: rgba(52,152,219,.15); color: #3498db; margin-left: 8px;
}
</style>
<script>
document.addEventListener('DOMContentLoaded', function() {
  if (window.STATIC_MODE) {
    // Add view-only badge to top bar
    var metaInfo = document.querySelector('.top-bar .meta-info');
    if (metaInfo) {
      var badge = document.createElement('div');
      badge.className = 'meta-item static-mode-badge';
      badge.style.display = 'inline-flex';
      badge.innerHTML = '&#128065; 仅查看模式';
      metaInfo.insertBefore(badge, metaInfo.firstChild);
    }
  }
});
</script>
"""
        html_output = html_output.replace("</head>", f"{static_style}\n</head>")

    # 生成 _worker.js 用于 Cloudflare Pages Advanced Mode
    # CF_AI_TOKEN: 专门用于 Workers AI 的令牌（Read+Edit权限）
    cf_ai_token = os.environ.get("CF_AI_TOKEN", "")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "02d85fe7929a981a11752af570010576")
    worker_js = f"""
export default {{
  async fetch(request, env) {{
    const url = new URL(request.url);
    if (url.pathname === '/api/chat' && request.method === 'POST') {{
      try {{
        const {{ messages }} = await request.json();
        if (!messages || !Array.isArray(messages)) {{
          return new Response(JSON.stringify({{ error: 'messages required' }}), {{
            status: 400, headers: {{ 'Content-Type': 'application/json' }}
          }});
        }}
        const aiResp = await fetch(
          'https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/ai/run/@cf/qwen/qwen2.5-72b-instruct',
          {{
            method: 'POST',
            headers: {{
              'Authorization': 'Bearer {cf_ai_token}',
              'Content-Type': 'application/json',
            }},
            body: JSON.stringify({{ messages, max_tokens: 2048 }}),
          }}
        );
        const aiData = await aiResp.json();
        return new Response(JSON.stringify(aiData), {{
          status: aiResp.status, headers: {{ 'Content-Type': 'application/json' }}
        }});
      }} catch (err) {{
        return new Response(JSON.stringify({{ success: false, error: err.message || 'AI request failed' }}), {{
          status: 500, headers: {{ 'Content-Type': 'application/json' }}
        }});
      }}
    }}
    return env.ASSETS.fetch(request);
  }}
}};
"""
    worker_path = OUTPUT_PATH.parent / "_worker.js"
    with open(worker_path, "w", encoding="utf-8") as f:
        f.write(worker_js.strip())

    # 写入输出文件
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_output)

    file_size = OUTPUT_PATH.stat().st_size / 1024
    print(f"[OK] Dashboard 已生成: {OUTPUT_PATH}")
    print(f"     文件大小: {file_size:.1f} KB")
    print(f"     包含 {len(report_data.get('data', {}).get('quotes', []))} 只ETF数据")
    print(f"     生成时间: {report_data.get('meta', {}).get('generated_at', 'N/A')}")
    return True


if __name__ == "__main__":
    success = embed_data()
    sys.exit(0 if success else 1)
