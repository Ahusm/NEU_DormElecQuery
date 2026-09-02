# NEU_ElecQuery 核心原理与维护指南

## 一、登录认证流程

### 1.1 完整登录链路
```
1. GET 登录页 → 获取动态参数 (lt, execution)
   ↓
2. RSA加密 (账号+密码) → 生成 rsa 字段
   ↓
3. POST 提交登录表单 → 获取 CASTGC Cookie
   ↓
4. 自动重定向 → 获得 pay.neu.edu.cn 的 JSESSIONID
   ↓
5. 携带 Cookie 访问电费接口
```

### 1.2 关键接口

#### **统一身份认证登录页**
- **URL**: `https://pass.neu.edu.cn/tpass/login?service=https%3A%2F%2Fpay.neu.edu.cn%2FdrCasLogin`
- **方法**: GET (首次访问) / POST (提交登录)
- **作用**: 获取 `lt` 和 `execution` 参数，提交账号密码

#### **CAS 回调地址**
- **URL**: `https://pay.neu.edu.cn/drCasLogin?ticket=ST-xxx-tpass`
- **方法**: GET (302 重定向)
- **作用**: 验证 ticket，下发 `JSESSIONID`

#### **最终跳转页**
- **URL**: `https://pay.neu.edu.cn/openPortal`
- **方法**: GET (302 重定向后的最终页)
- **作用**: 登录成功标志，确认已获得有效 Cookie

---

## 二、加密原理（最关键）

### 2.1 密码加密规则
```python
明文 = username + password  # 直接拼接，无分隔符
密文 = RSA_Encrypt(明文, 公钥)  # PKCS1v1_5 填充
rsa字段 = Base64Encode(密文)
```

### 2.2 RSA 公钥
**固定公钥**（从前端 JS 提取）：
```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnjA28DLKXZzxbKmo9/1W
kVLf1mr+wtLXLXt6sC4WiBCtsbzF5ewm7ARZeAdS3iZtqlYPn6IcUoOw42H8nAK/
tfFcIb6dZ1K0atn0U39oWCGPzYuKtLJeMuNZiDXVuAXtojrckOjLW9B3gUnaNGLu
Ix0fYe66l0o9WjU2cGLNZQfiIxs2h00z1EA9IdSnVxiVQWSD+lsP3JZXh2TT287l
a4Y4603SQNKTK/QvXfcmccwTEd1IW6HwGxD6QrkInBiHisKWxmveN7UDSaQRZ/J9
7G0YC32pD38WT53izXeK0p/kU/X37VP555um1wVWFvPIuc9I7gMP1+hq5a+X6c++
tQIDAQAB
```

### 2.3 POST 表单参数
```python
{
    'service': 'https://pay.neu.edu.cn/drCasLogin',  # 登录成功后跳转目标
    'rsa': '<Base64加密串>',                          # RSA加密后的账号+密码
    'ul': '<账号长度>',                               # username length
    'pl': '<密码长度>',                               # password length
    'lt': '<从登录页提取>',                           # 动态参数
    'execution': '<从登录页提取>',                    # 动态参数
    '_eventId': 'submit'                              # 固定值
}
```

---

## 三、Cookie 机制

### 3.1 关键 Cookie
| Cookie 名称 | 来源 | 作用 | 有效期 |
|------------|------|------|--------|
| `JSESSIONID` | pay.neu.edu.cn | 支付系统会话标识 | 会话级 |
| `CASTGC` | pass.neu.edu.cn | CAS 票据授予 Cookie | 约 2 小时 |
| `Language` | pass.neu.edu.cn | 语言设置 | 7 天 |

### 3.2 Cookie 传递规则
- **登录请求**：携带 `JSESSIONID`（首次 GET 登录页时获得）
- **登录成功后**：服务器返回 `Set-Cookie: CASTGC=...`
- **查询电费**：同时携带 `JSESSIONID` 和 `CASTGC`

---

## 四、电费查询接口

### 4.1 接口信息
- **URL**: 需从浏览器 F12 获取（可能为 `/pay.neu.edu.cn/queryProList` 或类似）
- **方法**: GET 或 POST
- **参数**: 通常包含房间号、学号等
- **响应**: JSON 格式，包含剩余电量、电表地址等

### 4.2 请求头要求
```python
headers = {
    'Cookie': 'JSESSIONID=xxx; CASTGC=xxx',
    'Referer': 'https://pay.neu.edu.cn/',
    'User-Agent': 'Mozilla/5.0 ...'
}
```

---

## 五、失效排查指南

### 5.1 登录页参数提取失败
**现象**: 正则无法匹配 `lt` 或 `execution`  
**排查步骤**:
1. 浏览器访问：`https://pass.neu.edu.cn/tpass/login?service=https%3A%2F%2Fpay.neu.edu.cn%2FdrCasLogin`
2. 右键 → 查看页面源代码
3. 搜索 `id="lt"` 和 `name="execution"`
4. 更新正则表达式以匹配新的 HTML 结构

### 5.2 RSA 加密失败或登录被拒
**现象**: 服务器返回错误，未获得 `CASTGC`  
**排查步骤**:
1. 浏览器打开登录页，按 F12 → **Sources** 面板
2. 查找文件：`/tpass/comm/neu/js/login_neu.js`
3. 搜索 `login()` 函数，检查加密逻辑是否仍为：
   ```javascript
   var originalData = rsa.encrypt(u+p);  // 确认仍是 u+p 拼接
   ```
4. 搜索 `publicKeyStr`，确认公钥是否变更
5. 对比浏览器 Network 面板中 `rsa` 字段的长度和格式

### 5.3 Cookie 失效或查询被拒
首先应去电费查询页面查询一次电费（进入页面会自动查询一次），在开发者工具->网络 里面找到`queryDefaultRoominfo`，把Cookie替换到本机缓存文件中，并把`ttl`改为一个较大的数字，避免程序认为缓存过期。

替换方法：复制一份`cookie.json.template`，修改`jsessionid`为浏览器获取到的

**现象**: 查询接口返回登录页 HTML 或 401 错误  
**排查步骤**:
1. 检查 `CASTGC` 是否过期（通常 2 小时）
2. 浏览器 F12 → **Application** → **Cookies**
3. 查看 `https://pass.neu.edu.cn` 下的 `CASTGC` 是否存在
4. 重新执行登录流程获取新 Cookie

### 5.4 电费查询接口变更
**现象**: JSON 解析错误，或返回数据结构变化  
**排查步骤**:
1. 浏览器登录 pay.neu.edu.cn
2. F12 → **Network** → 筛选 **XHR** 或 **Fetch**
3. 找到电费查询相关的请求（可能包含 `query`、`elec`、`room` 等关键词）
4. 记录：
   - 完整 URL
   - 请求方法 (GET/POST)
   - 请求参数
   - 响应 JSON 结构

---

## 六、关键网址速查

| 用途 | URL |
|------|-----|
| **统一身份认证登录页** | `https://pass.neu.edu.cn/tpass/login` |
| **支付系统首页** | `https://pay.neu.edu.cn/` |
| **加密 JS 文件** | `https://pass.neu.edu.cn/tpass/comm/neu/js/login_neu.js` |
| **RSA 公钥文件** | `https://pass.neu.edu.cn/tpass/comm/neu/js/rsa.js` |
| **CAS 票据验证** | `https://pay.neu.edu.cn/drCasLogin` |

---

## 七、服务端变更应对策略

### 7.1 学校系统升级时的检查清单
1. ✅ 访问登录页，检查 HTML 结构是否变化
2. ✅ 查看 `login_neu.js`，确认加密逻辑和公钥
3. ✅ 手动登录一次，F12 抓包对比请求参数
4. ✅ 测试电费查询接口，确认 URL 和响应格式

### 7.2 常见变更场景
| 变更类型 | 影响 | 修复方法 |
|---------|------|---------|
| 登录页 HTML 改版 | `lt`/`execution` 提取失败 | 更新正则表达式 |
| 加密算法升级 | RSA 加密失败 | 更新 `login_neu.js` 中的加密逻辑 |
| 公钥轮换 | 登录被拒 | 替换新的公钥 PEM |
| 接口路径变更 | 查询 404 | 从浏览器 F12 获取新 URL |
| Cookie 策略调整 | 会话失效快 | 增加登录重试机制 |

---

## 八、调试技巧

### 8.1 打印关键信息
```python
# 1. 打印登录页源码（检查参数提取）
print(resp.text)

# 2. 打印加密后的 rsa（对比浏览器）
print(f"RSA密文: {rsa_str[:50]}...")

# 3. 打印 POST 响应（查看服务器错误信息）
print(post_resp.text[:300])

# 4. 打印所有 Cookie（确认是否获得 CASTGC）
print(session.cookies.get_dict())

# 5. 打印最终 URL（确认跳转成功）
print(f"最终跳转: {resp.url}")
```

### 8.2 浏览器对比法
1. 浏览器登录 → F12 → **Network**
2. 找到 `login` 请求 → 查看 **Payload**
3. 对比 Python 脚本提交的参数是否一致
4. 特别注意 `rsa` 字段的长度和格式