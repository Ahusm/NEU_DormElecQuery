"""NEU 统一身份认证登录模块

通过 CAS 认证登录，获取 pay.neu.edu.cn 的 JSESSIONID。
"""

import requests
import re
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import constant

# 从 login_neu.js 中提取的固定公钥
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnjA28DLKXZzxbKmo9/1W
kVLf1mr+wtLXLXt6sC4WiBCtsbzF5ewm7ARZeAdS3iZtqlYPn6IcUoOw42H8nAK/
tfFcIb6dZ1K0atn0U39oWCGPzYuKtLJeMuNZiDXVuAXtojrckOjLW9B3gUnaNGLu
Ix0fYe66l0o9WjU2cGLNZQfiIxs2h00z1EA9IdSnVxiVQWSD+lsP3JZXh2TT287l
a4Y4603SQNKTK/QvXfcmccwTEd1IW6HwGxD6QrkInBiHisKWxmveN7UDSaQRZ/J9
7G0YC32pD38WT53izXeK0p/kU/X37VP555um1wVWFvPIuc9I7gMP1+hq5a+X6c++
tQIDAQAB
-----END PUBLIC KEY-----"""


def encrypt_rsa(plaintext: str) -> str:
    """使用公钥对明文进行 RSA 加密，并返回 Base64 字符串"""
    public_key = serialization.load_pem_public_key(
        PUBLIC_KEY_PEM, backend=default_backend()
    )
    ciphertext = public_key.encrypt(plaintext.encode("utf-8"), padding.PKCS1v15())
    return base64.b64encode(ciphertext).decode("utf-8")


def login_neu(username: str = "", password: str = "") -> dict | None:
    """通过 CAS 登录并获取 JSESSIONID 及 Cookie 过期信息

    Args:
        username: 学号，为空时从 constant 模块读取
        password: 密码，为空时从 constant 模块读取

    Returns:
        成功时返回字典:
            {"jsessionid": str, "cookie_expires": int|None}
        cookie_expires 为 CASTGC 的过期时间戳（秒），用于推算 JSESSIONID 有效期；
        若无法获取则为 None，调用方应使用默认 TTL。
        登录失败返回 None
    """
    username = username or constant.ACCOUNT
    password = password or constant.PASSWD

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0.0.0 Safari/537.36"
            )
        }
    )

    login_url = (
        "https://pass.neu.edu.cn/tpass/login?"
        "service=https%3A%2F%2Fpay.neu.edu.cn%2FdrCasLogin"
    )

    # 1. 访问登录页，获取动态的 lt 和 execution
    resp = session.get(login_url, timeout=15)

    lt_match = re.search(r'id="lt"[^>]+value="([^"]+)"', resp.text)
    exec_match = re.search(r'name="execution"\s+value="([^"]+)"', resp.text)

    if not lt_match or not exec_match:
        print("[登录] 未能提取到 lt 或 execution，页面结构可能已改变")
        return None

    lt = lt_match.group(1)
    execution = exec_match.group(1)

    # 2. RSA 加密 (明文 = 账号 + 密码)
    plaintext = username + password
    rsa_str = encrypt_rsa(plaintext)

    # 3. 构造表单 Payload
    payload = {
        "service": "https://pay.neu.edu.cn/drCasLogin",
        "rsa": rsa_str,
        "ul": str(len(username)),
        "pl": str(len(password)),
        "lt": lt,
        "execution": execution,
        "_eventId": "submit",
    }

    # 4. 提交登录请求 (手动跟踪重定向，处理相对 URL)
    from urllib.parse import urljoin

    resp = session.post(login_url, data=payload, allow_redirects=False, timeout=15)

    # 手动跟踪 302 重定向链
    max_redirects = 10
    last_url = login_url
    for _ in range(max_redirects):
        if resp.status_code not in (301, 302, 303, 307):
            break
        location = resp.headers.get("Location", "")
        if not location:
            break
        # 处理相对 URL（如 "openPortal;jsessionid=xxx"）
        if not location.startswith("http"):
            location = urljoin(last_url, location)
        last_url = location
        resp = session.get(location, allow_redirects=False, timeout=15)

    # 5. 验证登录结果
    if "CASTGC" not in session.cookies:
        print("[登录] 登录失败，未获取到 CASTGC Cookie")
        return None

    # 提取 JSESSIONID 和 CASTGC 过期时间
    jsessionid = None
    castgc_expires = None

    for cookie in session.cookies:
        if cookie.name == "JSESSIONID" and "pay.neu.edu.cn" in cookie.domain:
            jsessionid = cookie.value
        if cookie.name == "CASTGC":
            castgc_expires = cookie.expires  # 秒级时间戳，可能为 None

    if not jsessionid:
        jsessionid = session.cookies.get("JSESSIONID")

    if not jsessionid:
        print("[登录] 登录成功但未找到 JSESSIONID")
        return None

    # 计算 TTL：CASTGC 过期时间 - 当前时间
    import time
    ttl = None
    if castgc_expires:
        ttl = int(castgc_expires - time.time())
        if ttl < 0:
            ttl = None
        print(f"[登录] 登录成功，CASTGC 剩余有效期: {ttl}秒 ({ttl // 60}分钟)")
    else:
        print("[登录] 登录成功，CASTGC 无 expires 信息，将使用默认 TTL")

    return {"jsessionid": jsessionid, "cookie_expires": castgc_expires}


if __name__ == "__main__":
    result = login_neu()
    if result:
        print(f"JSESSIONID: {result['jsessionid']}")
        print(f"CASTGC expires: {result['cookie_expires']}")
    else:
        print("登录失败")