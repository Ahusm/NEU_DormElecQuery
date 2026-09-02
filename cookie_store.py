"""Cookie 持久化存储模块

将 JSESSIONID 保存到本地 JSON 文件，避免每次查询都需要重新登录。
TTL 优先使用服务端 CASTGC 的 expires 时间戳计算，无则回退到默认值。
"""

import json
import time
from pathlib import Path

# Cookie 存储文件路径（与本项目同级）
COOKIE_FILE = Path(__file__).parent / "cookie.json"

# 默认 Cookie 有效期（秒），当服务端未返回 expires 时使用
DEFAULT_TTL = 2 * 60 * 60  # 2 小时


def save_cookie(jsessionid: str, expires_at: float | None = None) -> None:
    """保存 JSESSIONID 到本地文件

    Args:
        jsessionid: 有效的 JSESSIONID 值
        expires_at: CASTGC 的过期时间戳（秒级，time.time() 格式），
                    来自服务端 Set-Cookie。为 None 时使用默认 TTL。
    """
    now = time.time()
    if expires_at and expires_at > now:
        ttl = int(expires_at - now)
    else:
        ttl = DEFAULT_TTL

    data = {
        "jsessionid": jsessionid,
        "saved_at": now,
        "ttl": ttl,
    }
    COOKIE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_cookie() -> str | None:
    """从本地文件加载 JSESSIONID

    Returns:
        有效的 JSESSIONID 字符串，如果文件不存在或已过期则返回 None
    """
    if not COOKIE_FILE.exists():
        return None

    try:
        data = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return None

    jsessionid = data.get("jsessionid")
    saved_at = data.get("saved_at", 0)
    ttl = data.get("ttl", DEFAULT_TTL)

    if not jsessionid:
        return None

    # 检查是否过期
    if time.time() - saved_at > ttl:
        return None

    return jsessionid


def clear_cookie() -> None:
    """清除本地保存的 Cookie 文件"""
    if COOKIE_FILE.exists():
        COOKIE_FILE.unlink()
