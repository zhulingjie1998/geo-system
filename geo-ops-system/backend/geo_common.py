"""geo_common.py — 跨模块共享的轻量工具：项目根路径、时间戳、上传目录工厂

设计原则：
  本模块只允许 import 标准库，禁止反向依赖任何业务模块（db / app …），
  这样它能作为最底层依赖被任何模块安全 import，不引入循环。
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

# 项目根目录：所有需要绝对路径的地方都用这个，不要再写 "<部署目录>"
PROJECT_ROOT: Path = Path(__file__).resolve().parent

# 上传文件根目录（uploads/ 在项目下）；子目录通过 upload_dir() 获取
UPLOAD_ROOT: Path = PROJECT_ROOT / "uploads"

# 默认 .env 路径，可在 load_dotenv() 调用时覆盖
DEFAULT_DOTENV: Path = PROJECT_ROOT / ".env"


def load_dotenv(path: Path = DEFAULT_DOTENV) -> None:
    """轻量 .env 加载：把 KEY=VALUE 注入 os.environ（只在未设置时注入，不覆盖外部传入）。
    不依赖第三方库；忽略空行和 # 注释。db.py 与 gunicorn_conf.py 共用此函数。"""
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def now_str() -> str:
    """统一时间戳：'YYYY-MM-DD HH:MM:SS'，本地时区。
    所有写库的时间字段都应该用它，避免不同模块产生格式分歧。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def date_range(date_str: str) -> tuple[str, str]:
    """对 'YYYY-MM-DD' 返回 (date_str, next_day_str)，用于索引友好的当日过滤：
    `WHERE col >= %s AND col < %s` 等价于 `LEFT(col,10)=%s` 但能命中索引。
    适用于 col 是 VARCHAR 'YYYY-MM-DD HH:MM:SS' 或 DATETIME 的场景。"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (date_str, (d + timedelta(days=1)).strftime("%Y-%m-%d"))


def upload_dir(subdir: str) -> Path:
    """获取（并自动创建）某子目录下的上传目录。
    例：upload_dir("keyword_expand") -> PROJECT_ROOT/uploads/keyword_expand"""
    p = UPLOAD_ROOT / subdir
    p.mkdir(parents=True, exist_ok=True)
    return p
