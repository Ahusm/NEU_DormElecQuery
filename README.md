# NEU_ElecQuery

东北大学宿舍电量查询工具。通过 CAS 统一身份认证自动登录，查询宿舍剩余电量，支持 Cookie 复用避免重复登录。

## 功能特性

- 自动完成 NEU 统一身份认证（CAS）登录
- RSA 加密账号密码，安全提交
- Cookie 本地缓存，2 小时内免重复登录
- Cookie 失效自动重新登录
- 查询失败自动重试
- 支持作为 Python 模块调用，也支持命令行直接运行

## 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

需要 Python >= 3.13。

### 2. 配置账号

```bash
# 复制配置模板
cp constant.py.example constant.py

# 编辑填入你的学号和密码
# Windows
notepad constant.py
# macOS / Linux
nano constant.py
```

`constant.py` 内容示例：

```python
ACCOUNT = "20241234"   # 你的学号
PASSWD = "your_password"  # 你的密码
```

> **注意**: `constant.py` 已在 `.gitignore` 中排除，不会被提交到版本库。

首次使用需手动获取并填入有效的cookie，见[手动缓存 Cookie](#手动填入-cookie)

### 3. 运行查询

```bash
# 使用默认房间号（需在 main.py 中修改）
python main.py

# 或在代码中调用
python -c "from main import get_electricity; print(get_electricity('1120294'))"
```

## 项目结构

```
NEU_ElecQuery/
├── main.py              # 主模块：电量查询入口
├── login.py             # 登录模块：CAS 认证与 RSA 加密
├── cookie_store.py      # Cookie 缓存模块：本地持久化与过期管理
├── constant.py.example  # 配置模板（复制为 constant.py 使用）
├── cookie.json.template # Cookie 缓存模板（手动填入时参考）
├── pyproject.toml       # 项目配置与依赖
└── docs/
    ├── MAINTENANCE.md          # 核心原理与维护指南
    └── 电量查询接口文档.md      # 接口详细文档
```

## 作为模块使用

```python
from main import get_electricity, query_electricity

# 便捷函数：查询并格式化输出
info = get_electricity("1120294")
print(info)
# 房间信息: 南湖校区学生第十宿舍B区0294寝室
# 剩余电量: 159 度
# 电表地址: 112012038104
# 最后抄表: 2026/9/1 0:00:00

# 原始接口数据
result = query_electricity("1120294")
print(result["elecRemain"])  # "159 度"
```

## 手动填入-Cookie

如果自动登录失败，可以从浏览器手动获取 Cookie：

1. 登录 [pay.neu.edu.cn](https://pay.neu.edu.cn/)
2. 打开开发者工具 → 网络 → 找到 `queryDefaultRoominfo` 请求
3. 复制请求中的 `JSESSIONID` 值
4. 复制 `cookie.json.template` 为 `cookie.json`，填入 `jsessionid`

```json
{
  "jsessionid": "你从浏览器复制的JSESSIONID",
  "saved_at": 0,
  "ttl": 7200
}
```

## 依赖

| 包             | 用途                    |
| -------------- | ----------------------- |
| `requests`     | HTTP 请求（登录与查询） |
| `cryptography` | RSA 加密（密码加密）    |

## 文档

- [核心原理与维护指南](docs/MAINTENANCE.md) — 登录流程、加密原理、Cookie 机制、失效排查
- [电量查询接口文档](docs/电量查询接口文档.md) — 接口参数、请求头、响应格式

## 常见问题

**Q: 提示"未能提取到 lt 或 execution"**
A: 学校登录页 HTML 结构可能已变更，参考 [维护指南 - 登录页参数提取失败](docs/MAINTENANCE.md#51-登录页参数提取失败) 排查。

**Q: Cookie 总是很快失效**
A: CASTGC 有效期约 2 小时，过期后程序会自动重新登录。如持续失败，参考 [维护指南 - Cookie 失效排查](docs/MAINTENANCE.md#53-cookie-失效或查询被拒)。

**Q: 查询返回错误数据或 404**
A: 接口地址可能变更，参考 [维护指南 - 接口变更排查](docs/MAINTENANCE.md#54-电费查询接口变更)。
