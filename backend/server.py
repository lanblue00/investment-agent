"""
投研大脑 - 本地HTTP服务
提供ETF搜索/添加/删除API + 静态Dashboard文件服务
"""

import json
import sys
import os
import threading
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 设置路径
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from etf_manager import search_etf, add_custom_etf, remove_custom_etf, get_custom_etfs, hide_etf, unhide_etf

PORT = 8765

# 全局状态：Pipeline是否正在运行
_pipeline_running = False
_pipeline_lock = threading.Lock()


class DashboardHandler(SimpleHTTPRequestHandler):
    """处理API请求和静态文件"""

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "":
            # 提供原始 dashboard.html 模板（无内嵌数据）
            # Dashboard JS 会通过 /api/report 获取最新数据
            html_path = PROJECT_DIR / "frontend" / "dashboard.html"
            if html_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                with open(html_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "Dashboard template not found.")

        elif path == "/api/report":
            # 直接返回最新的报告JSON（新鲜数据）
            report_path = PROJECT_DIR / "output" / "latest_report.json"
            if report_path.exists():
                with open(report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._json_response(data)
            else:
                self._json_response({"error": "报告尚未生成"}, 404)

        elif path == "/api/pipeline/status":
            # Pipeline运行状态
            with _pipeline_lock:
                running = _pipeline_running
            self._json_response({"running": running})

        elif path == "/api/search":
            # 搜索ETF
            qs = parse_qs(parsed.query)
            keyword = qs.get("q", [""])[0]
            if not keyword:
                self._json_response({"error": "missing q parameter"})
                return
            results = search_etf(keyword)
            self._json_response({"results": results})

        elif path == "/api/custom":
            # 获取自定义ETF列表
            self._json_response({"custom_etfs": get_custom_etfs()})

        elif path == "/api/status":
            # 服务状态
            self._json_response({"ok": True, "port": PORT})

        else:
            # 尝试作为静态文件服务
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # 读取POST body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        if path == "/api/add":
            code = data.get("code", "")
            exchange = data.get("exchange", "")
            name = data.get("name", "")
            sector = data.get("sector", "")
            if not code or not exchange or not name:
                self._json_response({"ok": False, "message": "missing required fields"})
                return
            result = add_custom_etf(code, exchange, name, sector)
            if result["ok"]:
                # 触发Pipeline重跑
                self._run_pipeline_async()
            self._json_response(result)

        elif path == "/api/remove":
            code = data.get("code", "")
            if not code:
                self._json_response({"ok": False, "message": "missing code"})
                return
            result = remove_custom_etf(code)
            if result["ok"]:
                self._run_pipeline_async()
            self._json_response(result)

        elif path == "/api/hide":
            code = data.get("code", "")
            if not code:
                self._json_response({"ok": False, "message": "missing code"})
                return
            result = hide_etf(code)
            if result["ok"]:
                self._run_pipeline_async()
            self._json_response(result)

        elif path == "/api/unhide":
            code = data.get("code", "")
            if not code:
                self._json_response({"ok": False, "message": "missing code"})
                return
            result = unhide_etf(code)
            if result["ok"]:
                self._run_pipeline_async()
            self._json_response(result)

        elif path == "/api/refresh":
            # 手动触发Pipeline重跑
            self._run_pipeline_async()
            self._json_response({"ok": True, "message": "Pipeline refreshing"})

        else:
            self.send_error(404)

    def _run_pipeline_async(self):
        """在后台线程中运行Pipeline"""
        def _run():
            global _pipeline_running
            with _pipeline_lock:
                _pipeline_running = True
            try:
                from pipeline import run_pipeline
                print("\n[Server] Pipeline rerun triggered...")
                run_pipeline()
                print("[Server] Pipeline rerun complete.")
            except Exception as e:
                print(f"[Server] Pipeline rerun failed: {e}")
            finally:
                with _pipeline_lock:
                    _pipeline_running = False

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def _json_response(self, data: dict, status: int = 200):
        """发送JSON响应"""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """处理CORS预检请求"""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        """简化日志输出"""
        print(f"[Server] {args[0]}")


def main():
    server = HTTPServer(("localhost", PORT), DashboardHandler)
    print(f"{'='*50}")
    print(f"  投研大脑 Server")
    print(f"  http://localhost:{PORT}")
    print(f"  Dashboard: http://localhost:{PORT}/")
    print(f"  Search API: http://localhost:{PORT}/api/search?q=")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
