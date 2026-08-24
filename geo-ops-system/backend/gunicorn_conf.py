import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
# gunicorn 在 master 启动时直接执行本文件（无 sys.path 入口模块），
# 所以这里手动把项目根加进去，再 import geo_common 共用 .env 加载逻辑
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from geo_common import load_dotenv  # noqa: E402
load_dotenv()

# 强制使用项目内 logs/ 目录，忽略 GEO_LOG_DIR 环境变量
# （避免 /www/wwwlogs/... 等宝塔路径不存在导致启动失败）
_LOG_DIR = _PROJECT_ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

chdir = str(_PROJECT_ROOT)

workers = int(os.environ.get("GEO_GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GEO_GUNICORN_THREADS", "8"))
worker_class = "gthread"
bind = os.environ.get("GEO_GUNICORN_BIND", "127.0.0.1:7006")

# 超时：SSE 流式任务需要较长时间
timeout = int(os.environ.get("GEO_GUNICORN_TIMEOUT", "600"))
keepalive = 5

max_requests = 0
max_requests_jitter = 0

pidfile = str(_PROJECT_ROOT / "gunicorn.pid")
accesslog = str(_LOG_DIR / "gunicorn_access.log")
errorlog  = str(_LOG_DIR / "gunicorn_error.log")
loglevel  = "info"

# 访问日志格式：包含响应时间
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sµs'
