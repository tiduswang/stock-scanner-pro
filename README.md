# 🚀 智能选股系统 Pro (Stock Scanner Pro)

> 基于 **量化交易思路** 的智能选股系统，支持 A股 / 港股 / ETF，集成 **本地 Ollama AI** 深度分析，适配 **T+1 交易模式**，提供网页界面实时计算与盘后分析。

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![Vue3](https://img.shields.io/badge/Vue-3.4-42b883.svg)](https://vuejs.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📋 目录

- [项目简介](#项目简介)
- [核心功能](#核心功能)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [在其他电脑安装](#在其他电脑安装)
- [配置说明](#配置说明)
- [API 文档](#api-文档)
- [项目结构](#项目结构)
- [免责声明](#免责声明)

---

## 项目简介

这是一个比较专业的 AI 增强股票分析系统，集成了 **技术面 / 基本面 / 情绪面** 三维度量化评分、**买卖点决策**、**本地 Ollama AI 深度解读**，支持 A股、港股、ETF 基金，以网页界面呈现，支持实时计算和盘后分析。

### 与同类项目对比

| 特性 | 本项目 | 参考项目(DR-lin-eng) |
|------|--------|----------------------|
| 前端框架 | Vue3 + 零构建CDN版（双前端） | Vue3 单一 |
| 后端框架 | FastAPI（异步+SSE原生） | Flask |
| AI 模型 | 本地 Ollama（私有化） | 云端API（OpenAI/Claude） |
| 搜索 | 代码+拼音首字母+完整拼音+中文 | 仅代码 |
| 选股 | 分市场扫描+板块+自定义代码+阈值筛选 | 批量代码 |
| 进度追踪 | SSE实时流+ETA时间预估 | SSE |
| 买卖点 | T+1适配+两档买入+两档止盈+仓位建议 | 基础建议 |
| 参数调节 | 三面权重+RSI+阈值+并发均可调 | 固定权重 |

---

## 核心功能

### 🎯 多维度量化分析

| 维度 | 指标 | 说明 |
|------|------|------|
| **技术面** | MA(5/10/20/60/120/250)、MACD、RSI、布林带、量价、趋势 | 6项细分评分加权汇总 |
| **基本面** | ROE、净利率、资产负债率、流动比率、营收增长率、PE/PB/PEG | 盈利/偿债/营运/成长/估值五面 |
| **情绪面** | 新闻情绪、公告情绪、短期量价情绪 | 规则词典+聚合评分 |

### 🤖 AI 智能选股

- **分市场自动扫描**：A股 / 港股 / ETF 一键扫描
- **筛选后深度分析**：量化评分过滤 → 高分股票送入 AI 深度分析
- **自定义选股范围**：
  - 输入多个股票代码
  - 选择某个板块（银行/新能源/白酒/半导体等）
  - 设置分数阈值（如 ≥70 分才分析）
- **本地 Ollama 模型**：数据不出本机，安全私有

### 🔍 智能搜索

- **代码搜索**：`000001`、`600519`
- **拼音首字母**：`PAYH`（平安银行）、`MTS`（茅台）
- **完整拼音**：`pinganyinhang`
- **中文名称**：`平安银行`

### 📊 T+1 买卖点决策

- **买入点**：激进价 + 稳健回踩支撑价
- **止损价**：基于支撑位自动计算
- **止盈目标**：第一目标（阻力位）+ 第二目标（+15%）
- **仓位建议**：根据评级推荐仓位比例
- **持有周期**：短线/中线建议
- **结构化理由**：买入逻辑 + 风险提示 + T+1提醒

### 📈 进度条与时间预估

- 实时百分比进度
- 已处理/通过筛选/失败计数
- 处理速度（只/秒）
- 预计剩余时间（ETA）
- 阶段日志时间线

### ⚙️ 参数可调节

- 技术面 / 基本面 / 情绪面 **权重滑杆**（总和=100%）
- RSI 超买/超卖阈值
- 筛选分数下限（50-90分可调）
- 输出 Top N 数量
- 并发线程数（1-8）
- 市场选择 / 板块选择 / 自定义代码

---

## 系统架构

```
📦 智能选股系统 Pro
├── 🖥️ 前端（两种模式）
│   ├── frontend_no_build/    # 零构建版（CDN+ElementPlus，开箱即用）
│   └── frontend/              # Vue3工程版（Vite+TS+NaiveUI，需npm构建）
│
├── ⚙️ 后端 (backend/)
│   ├── services/
│   │   ├── data/              # 数据获取层（akshare）
│   │   │   ├── stock_list.py  # A/HK/ETF列表+拼音索引
│   │   │   ├── market_data.py # K线+实时快照
│   │   │   ├── fundamental.py # 25项财务指标
│   │   │   └── news.py        # 新闻+公告+情绪
│   │   │
│   │   ├── analysis/          # 量化分析层
│   │   │   ├── technical.py        # 技术面6项指标
│   │   │   ├── fundamental_analysis.py # 基本面5面评分
│   │   │   ├── sentiment.py        # 情绪面分析
│   │   │   ├── scoring.py          # 综合评分引擎
│   │   │   └── buy_sell.py         # T+1买卖点决策
│   │   │
│   │   ├── scanner/           # 选股引擎
│   │   │   ├── progress.py    # 进度追踪+ETA
│   │   │   ├── base_scanner.py # 基础量化选股
│   │   │   └── ai_scanner.py  # AI选股+Ollama
│   │   │
│   │   └── search/
│   │       └── stock_search.py # 代码/拼音搜索
│   │
│   ├── routers/               # API路由
│   │   ├── common.py          # 健康/配置/Ollama检查
│   │   ├── search.py          # 搜索接口
│   │   ├── analyze.py         # 单股分析+AI深度
│   │   └── scan.py            # 选股扫描+SSE进度流
│   │
│   ├── utils/
│   │   ├── logger.py          # loguru日志
│   │   └── cache.py           # TTL内存缓存
│   │
│   ├── config.py              # pydantic-settings配置
│   └── main.py                # FastAPI入口
│
├── requirements.txt           # Python依赖
├── installer.py               # 📦 独立安装 App（装依赖+检查，不启动）
├── install.bat                # Windows 一键安装（调用 installer.py）
├── start.bat                  # ▶️ 主程序启动（只启动，不装依赖）
└── .env.example               # 配置模板
```

> **职责分离**：`installer.py / install.bat` 只负责依赖安装和环境检查；`start.bat / backend.main` 只负责启动 Web 服务。主程序不包含任何依赖安装逻辑。

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | FastAPI + Uvicorn | 异步高性能，原生SSE流式 |
| 数据源 | akshare 1.16.72 | A股/港股/ETF，免费开源 |
| 数据处理 | pandas + numpy | 量化计算核心 |
| AI 推理 | Ollama | 本地大模型，私有化 |
| 搜索增强 | pypinyin | 拼音首字母索引 |
| 前端（工程版） | Vue3 + Vite + TS + Naive UI | 响应式现代化 |
| 前端（零构建版） | Vue3 CDN + Element Plus | 无需npm，开箱即用 |
| 可视化 | ECharts 5 | K线图/雷达图 |

---

## 快速开始

> 项目已将「依赖安装」与「主程序启动」彻底分离：安装逻辑只存在于 `installer.py`，主程序 `start.bat / backend.main` 不再包含任何依赖安装代码。

### 方式一：Windows 两步走（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/stock-scanner-pro.git
cd stock-scanner-pro

# 2. 安装依赖（只装不启动）—— 双击 install.bat 或：
python installer.py

# 3. 启动主程序（不装依赖）—— 双击 start.bat 或：
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload
```

### 方式二：手动命令

```bash
# 1. 安装依赖（独立 App 完成）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
python installer.py --check-only    # 复检（不重新装）

# 2. 配置环境
cp .env.example .env
# 编辑 .env 修改端口/Ollama地址/权重等

# 3. 启动主程序
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload
```

### installer.py 子命令

| 命令 | 说明 |
|------|------|
| `python installer.py` | 完整安装+检查（默认） |
| `python installer.py --check-only` | 仅检查，不安装（CI/复检用） |
| `python installer.py --install-only` | 仅安装依赖，不做后续检查 |
| `python installer.py --no-mirror` | 不使用清华源，直接官方源 |

### 方式三：Docker（计划中）

```bash
docker build -t stock-scanner-pro .
docker run -d -p 8888:8888 --name stock-scanner stock-scanner-pro
```

### 访问地址

| 地址 | 说明 |
|------|------|
| http://127.0.0.1:8888/ | **零构建前端**（推荐，无需npm） |
| http://127.0.0.1:8888/docs | Swagger API 文档 |
| http://127.0.0.1:8888/vue | Vue工程版（需先 `npm run build`） |

---

## 在其他电脑安装

### 第一步：安装 Python 3.10+

#### Windows
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.10/3.11/3.12
3. 安装时**勾选 "Add Python to PATH"**
4. 验证：打开 CMD 输入 `python --version`

#### macOS
```bash
brew install python@3.12
python3 --version
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
python3 --version
```

### 第二步：下载项目代码

```bash
git clone https://github.com/your-username/stock-scanner-pro.git
cd stock-scanner-pro
```

或直接在 GitHub 页面下载 ZIP 压缩包，解压后进入目录。

### 第三步：创建虚拟环境（推荐）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 第四步：安装依赖（使用独立安装 App）

> 项目将「依赖安装」从主程序中剥离，单独做成一个 App。主程序不会自动装依赖，必须先执行本步。

```bash
# 推荐：使用独立安装 App（自动用清华源加速 + 语法检查 + 导入检查）
python installer.py

# 或者 Windows 用户双击：
install.bat

# 国际用户不使用清华源：
python installer.py --no-mirror

# 只想检查不重装（CI/复检）：
python installer.py --check-only
```

<details>
<summary><b>手动安装（不使用 installer.py）</b></summary>

```bash
# 国内用户
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 国际用户
pip install -r requirements.txt
```

> **如果遇到 numpy 安装冲突**（已有旧版无 RECORD 文件）：
> ```bash
> pip install --force-reinstall --no-deps numpy==2.1.2
> pip install -r requirements.txt
> ```
</details>

### 第五步：（可选）安装 Ollama

AI 选股功能需要本地 Ollama 服务，不装也能用量化选股功能。

1. 访问 https://ollama.com/download 下载安装
2. 拉取模型：
   ```bash
   ollama pull qwen2.5:7b
   ```
3. 验证服务：浏览器访问 http://127.0.0.1:11434

> **模型推荐**：
> - `qwen2.5:7b` — 中文理解好，速度快（默认）
> - `qwen2.5:14b` — 分析更深入，需要更多内存
> - `llama3.1:8b` — 英文强，通用性好
> - `deepseek-r1:7b` — 推理能力强

### 第六步：配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```ini
# 应用端口
APP_PORT=8888

# Ollama 配置
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:7b

# 分析权重（总和=1）
WEIGHT_TECHNICAL=0.45
WEIGHT_FUNDAMENTAL=0.35
WEIGHT_SENTIMENT=0.20

# 选股阈值
DEFAULT_SCORE_THRESHOLD=70
```

### 第七步：启动主程序（不装依赖，依赖请用 installer 安装）

```bash
# 方式1：直接启动主程序
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8888 --reload

# 方式2：Windows 双击 start.bat（含轻量自检，缺失依赖会提示运行 install.bat）
start.bat
```

### 第八步：打开浏览器

访问 http://127.0.0.1:8888/

### 常见安装问题

<details>
<summary><b>Q: pip install 很慢？</b></summary>

使用国内镜像源：
```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```
</details>

<details>
<summary><b>Q: numpy 安装报错 "no RECORD file"？</b></summary>

```bash
pip uninstall numpy -y
pip install numpy==2.1.2 --force-reinstall --no-deps
pip install -r requirements.txt
```
</details>

<details>
<summary><b>Q: akshare 获取数据失败？</b></summary>

- 检查网络连接
- 升级 akshare：`pip install akshare --upgrade`
- 非交易时段部分实时数据可能延迟
</details>

<details>
<summary><b>Q: Ollama 连接失败？</b></summary>

- 确认 Ollama 已启动：`ollama serve`
- 确认端口 11434 可访问
- 确认模型已拉取：`ollama list`
</details>

<details>
<summary><b>Q: PowerShell 执行策略阻止脚本？</b></summary>

```powershell
# 以管理员身份运行
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
</details>

<details>
<summary><b>Q: 想用 Vue 工程版前端？</b></summary>

```bash
cd frontend
npm install
npm run build
# 然后访问 http://127.0.0.1:8888/vue
```
</details>

---

## 配置说明

### `.env` 完整配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `8888` | 服务端口 |
| `APP_DEBUG` | `true` | 调试模式（热重载） |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 使用的 AI 模型 |
| `OLLAMA_TIMEOUT` | `300` | AI 请求超时（秒） |
| `CACHE_MARKET_DATA` | `300` | 行情缓存（秒） |
| `CACHE_FUNDAMENTAL` | `3600` | 财务缓存（秒） |
| `CACHE_NEWS` | `1800` | 新闻缓存（秒） |
| `CACHE_STOCK_LIST` | `86400` | 列表缓存（秒） |
| `WEIGHT_TECHNICAL` | `0.45` | 技术面权重 |
| `WEIGHT_FUNDAMENTAL` | `0.35` | 基本面权重 |
| `WEIGHT_SENTIMENT` | `0.20` | 情绪面权重 |
| `DEFAULT_SCORE_THRESHOLD` | `70` | 默认选股分数阈值 |

### 评级体系

| 评级 | 分数范围 | 含义 | 颜色 |
|------|----------|------|------|
| S | ≥85 | 强烈推荐（极佳买入机会） | 红色 |
| A | 75-85 | 推荐（可考虑买入） | 橙色 |
| B | 65-75 | 中性偏多（逢低关注） | 黄色 |
| C | 55-65 | 中性（观望为主） | 蓝色 |
| D | 40-55 | 中性偏空（谨慎） | 灰色 |
| E | <40 | 回避（不建议参与） | 深灰 |

---

## API 文档

启动服务后访问 http://127.0.0.1:8888/docs 查看完整 Swagger 文档。

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/common/health` | GET | 健康检查 |
| `/api/common/config` | GET | 默认配置 |
| `/api/common/ollama/check` | POST | Ollama 连通性检查 |
| `/api/search/stock?q=PAYH` | GET | 股票搜索 |
| `/api/search/hot` | GET | 热门推荐 |
| `/api/analyze/stock` | POST | 单股量化分析+买卖点 |
| `/api/analyze/stock/ai` | POST | 单股 AI 深度分析 |
| `/api/scan/start` | POST | 启动量化选股扫描 |
| `/api/scan/ai/start` | POST | 启动 AI 智能选股 |
| `/api/scan/progress/{id}` | GET | 获取扫描进度 |
| `/api/scan/progress/{id}/stream` | GET | SSE 实时进度流 |

### SSE 事件类型

- `progress`：进度更新（百分比/速度/ETA/日志）
- `final`：扫描完成（含最终结果+AI报告）

---

## 项目结构

```
stock-scanner-pro/
├── backend/
│   ├── __init__.py
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                 # 配置
│   ├── routers/
│   │   ├── common.py
│   │   ├── search.py
│   │   ├── analyze.py
│   │   └── scan.py
│   ├── services/
│   │   ├── data/
│   │   │   ├── stock_list.py
│   │   │   ├── market_data.py
│   │   │   ├── fundamental.py
│   │   │   └── news.py
│   │   ├── analysis/
│   │   │   ├── technical.py
│   │   │   ├── fundamental_analysis.py
│   │   │   ├── sentiment.py
│   │   │   ├── scoring.py
│   │   │   └── buy_sell.py
│   │   ├── scanner/
│   │   │   ├── progress.py
│   │   │   ├── base_scanner.py
│   │   │   └── ai_scanner.py
│   │   └── search/
│   │       └── stock_search.py
│   └── utils/
│       ├── logger.py
│       └── cache.py
├── frontend/                      # Vue3 工程版
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.vue
│       ├── main.ts
│       ├── api/http.ts
│       ├── stores/app.ts
│       ├── router/index.ts
│       ├── components/
│       │   ├── ProgressPanel.vue
│       │   ├── ParamsPanel.vue
│       │   └── StockResultTable.vue
│       └── views/
│           ├── Home.vue
│           └── AnalyzeDetail.vue
├── frontend_no_build/             # 零构建版（开箱即用）
│   └── index.html
├── requirements.txt
├── .env.example
├── .gitignore
├── installer.py                   # 📦 独立安装 App（装依赖+检查，不启动）
├── install.bat                    # Windows 一键安装
├── start.bat                      # ▶️ 主程序启动（只启动，不装依赖）
└── README.md
```

---

## 免责声明

**本系统仅用于学习和研究目的，所有分析结果仅供参考，不构成投资建议。投资有风险，入市需谨慎。**

- 数据来源：[akshare](https://github.com/akfamily/akshare)（公开免费接口）
- AI 分析：本地 Ollama 模型生成，可能存在偏差
- 量化评分：基于公开指标计算，不保证准确性

## License

MIT License - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [DR-lin-eng/stock-scanner](https://github.com/DR-lin-eng/stock-scanner) — 原始项目架构参考
- [lanzhihong6/stock-scanner](https://github.com/lanzhihong6/stock-scanner) — Vue3 重构参考
- [akshare](https://github.com/akfamily/akshare) — 金融数据接口
- [Ollama](https://ollama.com) — 本地大模型推理
- [FastAPI](https://fastapi.tiangolo.com) — 异步 Web 框架
