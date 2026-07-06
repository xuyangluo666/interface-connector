# 接口对接服务 - 配置说明与功能概述

## 一、项目简介

本项目是一个接口对接服务，实现从 **A 系统（纷享销客 CRM）** 到 **B 系统** 的数据自动化同步。采用经典的 **ETL 架构模式**（Extract-Transform-Load），将纷享销客中的客户数据及商机信息自动抽取、格式转换后写入 B 系统。

### 核心功能
- 客户基础信息同步（公司名称、地址、客户级别等）
- 商机编号自动关联与同步
- 定时任务调度，支持增量同步
- 自动重试机制，保证接口调用稳定性
- 敏感信息脱敏，日志自动清理

---

## 二、目录结构

```
interface-connector/
├── main.py                  # 主入口，启动调度器
├── requirements.txt         # 依赖列表
├── .env                     # 环境变量配置（敏感信息，不提交）
├── .env.example             # 环境变量示例文件
├── .gitignore               # Git 忽略规则
│
├── sync/                    # 核心同步模块
│   ├── config.py            # 配置管理（从 .env 加载）
│   ├── extractor.py         # 数据提取层（A 系统 -> 纷享销客 API）
│   ├── transformer.py       # 数据转换层（A 格式 -> B 格式）
│   ├── loader.py            # 数据加载层（写入 B 系统）
│   └── scheduler.py         # 定时任务调度器
│
├── models/                  # 数据模型定义
│   ├── a_models.py          # A 系统数据模型（Pydantic）
│   └── b_models.py          # B 系统数据模型（Pydantic）
│
├── utils/                   # 工具模块
│   ├── logging_config.py    # 日志配置与清理
│   ├── retry.py             # 重试策略
│   └── idempotency.py       # 幂等性工具
│
└── tests/                   # 测试目录
```

---

## 三、环境配置说明

### 3.1 配置文件位置

所有配置均通过根目录下的 `.env` 文件管理，**该文件包含敏感信息，禁止提交到 Git 仓库**。首次使用时可复制 `.env.example` 作为模板：

```powershell
Copy-Item .env.example .env
```

### 3.2 配置项详解

#### 3.2.1 B 系统配置

| 配置项 | 别名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| `B_SYSTEM_BASE_URL` | `b_system_base_url` | string | 是 | - | B 系统 API 基础地址，如 `https://www.bangwo8.com` |
| `B_SYSTEM_AUTHORIZATION` | `b_system_authorization` | string | 是 | - | B 系统 HTTP Basic 认证 Token，格式：`Basic xxxxxx` |
| `B_SYSTEM_COOKIE` | `b_system_cookie` | string | 否 | None | 可选的 Cookie 值，部分接口可能需要 |

#### 3.2.2 A 系统配置（纷享销客）

| 配置项 | 别名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| `A_SYSTEM_BASE_URL` | `a_system_base_url` | string | 是 | - | 纷享销客开放平台地址，固定为 `https://open.fxiaoke.com` |
| `A_SYSTEM_APP_ID` | `a_system_app_id` | string | 是 | - | 纷享销客应用 ID，格式如 `FSAID_xxxxxx` |
| `A_SYSTEM_PERMANENT_CODE` | `a_system_permanent_code` | string | 是 | - | 纷享销客永久授权码 |
| `A_SYSTEM_APP_SECRET` | `a_system_app_secret` | string | 是 | - | 纷享销客应用密钥 |
| `A_SYSTEM_DEFAULT_MOBILE` | `a_system_default_mobile` | string | 是 | - | 默认用户手机号，用于查询 `openUserId` |

#### 3.2.3 同步配置

| 配置项 | 别名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| `SYNC_INTERVAL_MINUTES` | `sync_interval_minutes` | int | 否 | 3 | 同步任务执行间隔，单位：分钟 |
| `SYNC_BATCH_SIZE` | `sync_batch_size` | int | 否 | 100 | 单次同步数据批大小，最大 100 |

#### 3.2.4 日志配置

| 配置项 | 别名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|------|--------|------|
| `LOG_RETENTION_DAYS` | `log_retention_days` | int | 否 | 7 | 日志文件保留天数，过期自动清理 |

### 3.3 .env 文件示例

```ini
# ===== B 系统配置 =====
B_SYSTEM_BASE_URL=https://www.bangwo8.com
B_SYSTEM_AUTHORIZATION=Basic empzenpoaW5lbmc6YTEyMzQ1Ng==
B_SYSTEM_COOKIE=

# ===== A 系统配置（纷享销客） =====
A_SYSTEM_BASE_URL=https://open.fxiaoke.com
A_SYSTEM_APP_ID=FSAID_1324417
A_SYSTEM_PERMANENT_CODE=C13DD771E81BD8AC8CC8DB5525DBBAD1
A_SYSTEM_APP_SECRET=fd2587a581354fc0836333029ed1d1cc
A_SYSTEM_DEFAULT_MOBILE=16635022959

# ===== 同步配置 =====
SYNC_INTERVAL_MINUTES=3
SYNC_BATCH_SIZE=100

# ===== 日志配置 =====
LOG_RETENTION_DAYS=7
```

---

## 四、功能模块详解

### 4.1 数据提取层 - AExtractor

文件：[sync/extractor.py](file:///d:/interface-connector/sync/extractor.py)

负责从纷享销客 CRM 系统中抽取数据。

#### 核心方法

| 方法 | 功能 | API 接口 |
|------|------|----------|
| `_get_corp_access_token()` | 获取企业访问令牌 | `POST /cgi/corpAccessToken/get/V2` |
| `_ensure_token_valid()` | 校验 Token 有效性，过期自动刷新 | - |
| `get_user_id_by_mobile(mobile)` | 通过手机号查询用户 openUserId | `POST /cgi/user/getByMobile` |
| `get_crm_data()` | 查询 CRM 客户数据（增量：当天 00:00 起） | `POST /cgi/crm/v2/data/query` |
| `get_opportunity_by_account_id(account_id)` | 按客户 ID 查询商机信息 | `POST /cgi/crm/v2/data/query` |
| `get_companies_with_opportunities()` | 获取客户 + 关联商机的完整数据 | 组合调用 |

#### 认证流程

```
1. 调用 _get_corp_access_token()
   ├─ 入参: appId, permanentCode, appSecret
   └─ 返回: corpAccessToken, corpId, expiresIn

2. 调用 get_user_id_by_mobile()
   ├─ 入参: corpAccessToken, corpId, mobile
   └─ 返回: openUserId（后续接口必需参数）

3. 后续所有 CRM 查询均携带:
   ├─ corpAccessToken
   ├─ corpId
   └─ currentOpenUserId
```

#### 客户级别映射（纷享销客 → B 系统）

| 纷享销客编码 | B 系统显示文本 |
|--------------|----------------|
| 1 | 品牌【年综合销售额大于10亿（含）】 |
| 2 | KA【综合销售额大于1亿（含）】 |
| 3 | 基石客户（S） |
| 4 | 重点客户（A） |
| 5 | 一般客户（B） |
| 6 | 其他【综合销售额小于1亿（含）】 |

---

### 4.2 数据转换层 - Transformer

文件：[sync/transformer.py](file:///d:/interface-connector/sync/transformer.py)

将 A 系统数据结构转换为 B 系统要求的格式。

#### 转换示例

**A 系统原始数据**：
```json
{
  "_id": "695b1ef13a3ff70006a4c751",
  "name": "重庆药友制药有限责任公司",
  "account_level": "4",
  "address": "重庆市渝北区人和镇星光大道100号",
  "owner": ["FSUID_18824304454AC5065B7E6A60D9721282"],
  "data_own_department": ["1011"],
  "商机信息": [
    {"name": "重庆药友-IT机器人", "field_4dH68__c": "SJ-2026-02-06011"}
  ]
}
```

**B 系统目标格式**：
```json
{
  "company": {
    "companyName": "重庆药友制药有限责任公司",
    "custom_fields": [
      {"key": "field_1", "value": "重点客户（A）"},
      {"key": "address", "value": "重庆市渝北区人和镇星光大道100号"}
    ]
  }
}
```

---

### 4.3 数据加载层 - BLoader

文件：[sync/loader.py](file:///d:/interface-connector/sync/loader.py)

负责将转换后的数据写入 B 系统。

#### 核心方法

| 方法 | 功能 | API 接口 |
|------|------|----------|
| `search_company_by_name(name)` | 按公司名称查询 B 系统公司，获取 uId | `GET /api/v1/companies/search.json` |
| `create_company(data)` | 创建单个公司（公司已存在时自动复用） | `POST /api/v1/companies.json` |
| `create_companies_batch(companies)` | 批量创建公司，返回创建结果统计 | 组合调用 |
| `search_business_opportunities(owner)` | 查询公司已有商机编号（用于去重） | `GET /api/v1/forms/asset_form/9154740/search.json` |
| `create_business_opportunities(uId, ops)` | 写入商机编号（自动去重） | `POST /api/v1/forms/asset_form/9154740.json` |

#### 商机编号同步流程

```
1. 先查询 B 系统已有商机编号（防止重复写入）
   GET /api/v1/forms/asset_form/9154740/search.json
   参数: query=owner:{uId} ownerType:company

2. 过滤已存在的商机编号，仅写入新增部分

3. 批量写入新商机
   POST /api/v1/forms/asset_form/9154740.json
   Body:
   {
     "items_data": [
       {
         "owner": "{company_uId}",
         "ownerType": "company",
         "field_3": "SJ-2026-02-06011",      // 商机编号
         "field_4": "重庆药友-IT机器人"       // 商机名称
       }
     ]
   }
```

---

### 4.4 调度器 - Scheduler

文件：[sync/scheduler.py](file:///d:/interface-connector/sync/scheduler.py)

基于 APScheduler 的定时任务调度器。

#### 同步流程（`run_sync()`）

```
┌─────────────────────────────────────┐
│  1. 初始化 AExtractor                │
│     - 获取 corpAccessToken / corpId  │
│     - 通过手机号获取 openUserId      │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  2. 抽取数据                         │
│     get_companies_with_opportunities()│
│     获取客户数据 + 关联商机信息       │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  3. 格式转换                         │
│     transform_companies()            │
│     A 格式 → B 系统格式               │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  4. 批量创建公司                     │
│     create_companies_batch()         │
│     返回: 成功/失败 + B系统 uId       │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  5. 同步商机编号                     │
│     对每个创建成功的公司:             │
│       - 查询已有商机（去重）          │
│       - 仅写入新增商机编号            │
└─────────────────────────────────────┘
```

#### 启动行为

- **立即执行**：服务启动后立即执行一次同步任务
- **定时执行**：按 `SYNC_INTERVAL_MINUTES` 配置的间隔循环执行（默认 3 分钟）
- **防堆积**：同一时间最多 1 个同步实例运行，防止任务重叠

---

### 4.5 日志配置与清理

文件：[utils/logging_config.py](file:///d:/interface-connector/utils/logging_config.py)

#### 日志配置

| 输出目标 | 级别 | 格式 | 滚动策略 |
|----------|------|------|----------|
| 控制台（stdout） | INFO+ | 带颜色，含时间/级别/函数名/行号 | - |
| 文件 `logs/sync_YYYY-MM-DD.log` | DEBUG+ | 纯文本，含完整时间戳 | 每日滚动，按保留天数清理 |

#### 日志清理机制

1. **Loguru 内置 retention**：文件输出器配置了 `retention="{N} days"`，Loguru 自动清理滚动产生的过期日志
2. **启动时主动清理**：`cleanup_old_logs()` 函数在服务启动时扫描 `logs/` 目录，删除超过保留天数的 `sync_*.log` 文件

#### 敏感信息脱敏

日志输出中以下字段自动脱敏为 `***`：
- corpAccessToken / corpId
- openUserId
- 手机号
- HTTP Authorization 头
- HTTP Cookie 头

---

## 五、运行与部署

### 5.1 环境准备

确保已创建虚拟环境并安装依赖：

```powershell
# 创建虚拟环境（首次）
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt
```

### 5.2 启动服务

```powershell
# 方式一：使用虚拟环境 Python
.\.venv\Scripts\python.exe main.py

# 方式二：激活虚拟环境后直接运行
.\.venv\Scripts\Activate.ps1
python main.py
```

启动成功后控制台输出：
```
接口对接服务启动
日志配置完成，保留天数: 7 天
调度器已启动，执行间隔: 3 分钟
启动后立即执行首次同步任务...
========== 开始执行同步任务 ==========
```

### 5.3 停止服务

按 `Ctrl + C` 停止服务，调度器将优雅关闭：
```
收到中断信号，正在关闭调度器...
服务已关闭
```

---

## 六、稳定性保障

### 6.1 自动重试机制

基于 `tenacity` 库实现，所有 HTTP 调用均配置：
- **重试条件**：HTTP 错误（4xx/5xx）及网络异常
- **重试策略**：指数退避，最小等待 2 秒，最大 30 秒
- **重试次数**：最多 3 次
- **失败处理**：超过重试次数后抛出异常，由上层记录错误日志

### 6.2 幂等性设计

- **公司创建**：检测到 `status=110026`（已存在）时，自动复用已有 companyId
- **商机写入**：写入前查询已有商机编号，仅写入新增部分，避免重复

### 6.3 Token 自动刷新

`corpAccessToken` 过期时间减 60 秒作为阈值，调用接口前自动检查并刷新，避免使用过期 Token。

---

## 七、关键配置项速查表

| 配置项 | 推荐值 | 说明 |
|--------|--------|------|
| `SYNC_INTERVAL_MINUTES` | 3 ~ 10 | 根据数据实时性要求调整，过短可能触发 API 限流 |
| `SYNC_BATCH_SIZE` | 100 | 纷享销客单次查询上限，不建议修改 |
| `LOG_RETENTION_DAYS` | 7 ~ 30 | 根据磁盘空间和合规要求调整 |
| `A_SYSTEM_DEFAULT_MOBILE` | 实际运维账号手机号 | 必须是纷享销客内有效用户，用于数据查询权限 |

---

## 八、常见问题排查

### Q1: 获取 Token 失败？
- 检查 `.env` 中 `A_SYSTEM_APP_ID`、`A_SYSTEM_PERMANENT_CODE`、`A_SYSTEM_APP_SECRET` 是否正确
- 确认纷享销客应用已授权对应企业

### Q2: 查询 CRM 返回 0 条数据？
- 默认仅查询**当天 00:00** 以后创建的客户（增量同步）
- 如需全量同步，修改 `get_crm_data()` 中 `start_time=0`

### Q3: B 系统返回 403 Forbidden？
- 检查 `B_SYSTEM_AUTHORIZATION` 是否正确（注意 Base64 编码的 `Basic ` 前缀）
- 确认账号在 B 系统中有公司创建和资产表单写入权限

### Q4: 商机编号未同步？
- 先检查该客户在纷享销客中是否有关联商机
- 再检查 B 系统中该商机编号是否已存在（已存在会自动跳过）

### Q5: 日志文件未自动清理？
- 确认 `.env` 中 `LOG_RETENTION_DAYS` 配置正确
- 日志清理在服务**启动时**执行，长期运行的服务会通过 Loguru retention 机制自动清理
