"""NEU 宿舍电量查询主模块

核心功能:
- 查询指定寝室的剩余电量
- 自动复用已保存的 Cookie，避免重复登录
- Cookie 失效时自动重新登录
- 查询失败时自动重试
"""

import requests
import cookie_store
from login import login_neu

# 默认重试次数
MAX_RETRIES = 3

# 查询接口 URL
QUERY_URL = "https://pay.neu.edu.cn/queryRommInfo"

# 默认厂商/校区代码
DEFAULT_FACTORY_CODE = "E039"


class ElecQueryError(Exception):
    """电量查询异常"""

    pass


def _build_headers(jsessionid: str) -> dict:
    """构造查询请求头

    Args:
        jsessionid: 有效的 JSESSIONID

    Returns:
        包含必要请求头的字典
    """
    return {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://pay.neu.edu.cn/openPayElecPagesDbdx51414{DEFAULT_FACTORY_CODE}.html",
        "Origin": "https://pay.neu.edu.cn",
        "Cookie": f"JSESSIONID={jsessionid}",
    }


def _is_cookie_invalid(response: requests.Response) -> bool:
    """判断响应是否表明 Cookie 已失效

    当 Cookie 失效时，服务器可能返回:
    - 302 重定向到登录页
    - 401 未授权
    - sessionstatus: timeout 响应头
    - 空响应体（Content-Length: 0）
    - 响应体包含登录页 HTML 特征

    Args:
        response: 请求响应对象

    Returns:
        True 表示 Cookie 已失效
    """
    # 302 重定向或 401
    if response.status_code in (302, 401):
        return True
    # sessionstatus: timeout 表示会话已过期
    if response.headers.get("sessionstatus") == "timeout":
        return True
    # 空响应体（服务端返回200但body为空，通常是session失效）
    if len(response.content) == 0:
        return True
    # 响应体包含登录页特征
    text = response.text.lower()
    if "login" in text and "cas" in text:
        return True
    if "tpass" in text and "redirect" in text:
        return True
    return False


def _get_valid_cookie(username: str = "", password: str = "", cookie: str = "") -> str:
    """获取有效的 JSESSIONID

    优先使用传入的 cookie 参数，其次从本地缓存加载，最后尝试登录。
    登录成功后会自动保存 Cookie。

    Args:
        username: 学号（可选，默认从 constant 读取）
        password: 密码（可选，默认从 constant 读取）
        cookie: 外部传入的 JSESSIONID（可选，优先级最高，传入后直接使用并缓存）

    Returns:
        有效的 JSESSIONID 字符串

    Raises:
        ElecQueryError: 登录失败时抛出
    """
    # 0. 优先使用外部传入的 Cookie
    if cookie:
        print("[Cookie] 使用外部传入的 Cookie")
        cookie_store.save_cookie(cookie)
        return cookie

    # 1. 尝试从本地加载已保存的 Cookie
    jsessionid = cookie_store.load_cookie()
    if jsessionid:
        print("[Cookie] 使用已保存的 Cookie")
        return jsessionid

    # 2. Cookie 不可用，执行登录
    print("[Cookie] 本地无有效 Cookie，正在登录...")
    login_result = login_neu(username, password)

    if not login_result:
        raise ElecQueryError("登录失败，无法获取 JSESSIONID")

    jsessionid = login_result["jsessionid"]
    expires_at = login_result.get("cookie_expires")

    # 3. 保存新获取的 Cookie（使用服务端返回的过期时间）
    cookie_store.save_cookie(jsessionid, expires_at=expires_at)
    print("[Cookie] 已保存新 Cookie")
    return jsessionid


def query_electricity(
    room_no: str,
    factory_code: str = DEFAULT_FACTORY_CODE,
    max_retries: int = MAX_RETRIES,
    cookie: str = "",
) -> dict:
    """查询宿舍剩余电量

    自动管理 Cookie：优先复用已保存的 Cookie，失效时自动重新登录。
    查询失败时会自动重试，重试次数耗尽后抛出异常。

    Args:
        room_no: 宿舍房间号，如 "1120294"
        factory_code: 厂商/校区代码，默认 "E039"
        max_retries: 最大重试次数，默认 3
        cookie: 外部传入的 JSESSIONID（可选，优先级最高，传入后直接使用并缓存）

    Returns:
        接口返回的 JSON 数据字典，包含:
        - returncode: 状态码 ("SUCCESS" 表示成功)
        - elecroominfo: 房间信息
        - elecRemain: 剩余电量
        - mAddr: 电表地址
        - lastReadTime: 最后抄表时间

    Raises:
        ElecQueryError: 重试次数耗尽仍无法查询时抛出
    """
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            # 获取有效 Cookie（首次尝试使用传入的 cookie，重试时不再使用以避免循环）
            jsessionid = _get_valid_cookie(cookie=cookie if attempt == 1 else "")

            # 发起查询请求
            headers = _build_headers(jsessionid)
            data = {
                "elecroomno": room_no,
                "factorycode": factory_code,
            }

            response = requests.post(
                QUERY_URL,
                headers=headers,
                data=data,
                timeout=10,
                allow_redirects=False,  # 不自动跟随重定向，以便检测 Cookie 失效
            )

            # 检查 Cookie 是否失效
            if _is_cookie_invalid(response):
                print(f"[查询] 第 {attempt} 次尝试: Cookie 已失效，清除并重试")
                cookie_store.clear_cookie()
                last_error = ElecQueryError("Cookie 已失效")
                continue

            response.raise_for_status()
            result = response.json()

            # 检查业务层返回码
            if result.get("returncode") != "SUCCESS":
                # 业务错误不需要重试（如房间号错误）
                return result

            print(f"[查询] 第 {attempt} 次尝试: 查询成功")
            return result

        except requests.RequestException as e:
            last_error = e
            print(f"[查询] 第 {attempt} 次尝试: 请求异常 - {e}")

        except (ValueError, KeyError) as e:
            last_error = e
            print(f"[查询] 第 {attempt} 次尝试: 解析异常 - {e}")
            # JSON 解析失败通常意味着 Cookie 失效，清除后重试
            cookie_store.clear_cookie()

    # 所有重试都失败
    raise ElecQueryError(f"查询失败，已重试 {max_retries} 次。最后错误: {last_error}")


def format_result(result: dict) -> str:
    """格式化查询结果用于显示

    Args:
        result: 接口返回的 JSON 数据

    Returns:
        格式化后的字符串
    """
    if result.get("returncode") != "SUCCESS":
        return f"查询失败: {result.get('returnmsg', '未知错误')}"

    return (
        f"房间信息: {result.get('elecroominfo', '未知')}\n"
        f"剩余电量: {result.get('elecRemain', '未知')}\n"
        f"电表地址: {result.get('mAddr', '未知')}\n"
        f"最后抄表: {result.get('lastReadTime', '未知')}"
    )


def get_electricity(
    room_no: str, factory_code: str = DEFAULT_FACTORY_CODE, cookie: str = ""
) -> str:
    """获取寝室电量信息（便捷函数）

    这是面向外部调用的主要接口，封装了完整的查询流程：
    Cookie 复用 → 自动登录 → 重试 → 格式化输出

    Args:
        room_no: 宿舍房间号
        factory_code: 厂商/校区代码，默认 "E039"
        cookie: 外部传入的 JSESSIONID（可选，优先级最高，传入后直接使用并缓存）

    Returns:
        格式化的电量信息字符串

    Raises:
        ElecQueryError: 查询失败时抛出
    """
    result = query_electricity(room_no, factory_code, cookie=cookie)
    return format_result(result)


if __name__ == "__main__":
    import sys

    try:
        info = get_electricity("1120291", "E039")
        print(info)
    except ElecQueryError as e:
        print(f"错误: {e}")
        sys.exit(1)
