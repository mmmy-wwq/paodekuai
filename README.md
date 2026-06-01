# 跑得快 (Pao De Kuai)

一个基于 WebSocket 的实时多人在线卡牌游戏——**跑得快**。支持 2~4 人对战，包含包牌、托管、语音播报、断线重连等功能。专为家庭局域网或 ngrok 远程对战设计。

## 游戏规则

跑得快是一款流行于中国各地的纸牌游戏，目标是最先出完手中的所有牌。

- **牌型**：单张、对子、三带二、顺子（≥5张）、连对（≥3对）、飞机带翅膀、炸弹（四张同点）、A炸（4张A）
- **大小**：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2
- **包牌**：首轮可自愿"包牌"——包牌者需独自对抗其余所有玩家，赢则双倍得分，输则双倍扣分
- **托管**：玩家可随时开启/关闭自动出牌
- **计分**：每轮根据排名计分，历史总分持久化保存

## 技术栈

### 后端

- **Python 3.8+** — 运行环境
- **FastAPI** — HTTP + WebSocket 服务
- **Uvicorn** — ASGI 服务器
- **Pydantic** — 数据模型与验证
- **edge-tts** — 中文字幕语音播报生成

### 前端

- **React 19** — UI 框架
- **TypeScript** — 类型安全
- **Vite 6** — 构建工具
- **React Router 7** — 客户端路由

### 架构

```
┌─────────────┐     WebSocket      ┌──────────────────┐
│  React SPA  │ ◄─────────────────► │  FastAPI Server   │
│  (Browser)  │     JSON 消息       │  (Python)         │
└─────────────┘                     └───────┬──────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
              ┌─────▼──────┐       ┌────────▼────────┐     ┌───────▼───────┐
              │ RoomManager │       │ GameStateMachine│     │   CardEngine  │
              │ 房间/玩家管理│       │  状态机/计分    │     │  识别/比较/发牌│
              └────────────┘       └─────────────────┘     └───────────────┘
```

## 快速开始

### 前置依赖

- **Python 3.8+**
- **Node.js 18+**
- **npm**

### 1. 克隆 & 安装

```bash
# 克隆仓库
git clone https://github.com/mmmy-wwq/paodekuai.git
cd paodekuai

# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd client
npm install
cd ..
```

### 2. 构建前端

```bash
cd client
npm run build
cd ..
```

### 3. 启动服务器

```bash
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
```

### 4. 打开游戏

浏览器访问 **http://127.0.0.1:8000**

### 5. 多人远程对战（可选）

使用 ngrok 将本地服务暴露到公网：

```bash
ngrok http 8000 --log=stdout
```

将生成的 Public URL（如 `https://abc123.ngrok.io`）分享给家人朋友即可。

> 详细启动步骤见项目根目录的 `QUICK_START.txt`。

### 开发模式

```bash
# 前端热重载开发
cd client
npm run dev

# 后端自动重载
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

## 项目结构

```
├── client/                      # React 前端
│   ├── public/
│   │   ├── sound/              # TTS 音效文件 (默认 / 爸爸 / 妈妈 / 姐姐 / 弟弟)
│   │   └── 头像/               # 默认头像图片
│   └── src/
│       ├── components/          # UI 组件 (PlayerSlot, Avatar 等)
│       ├── hooks/               # 自定义 Hooks (WebSocket, 音效, 动画, 提示引擎等)
│       ├── pages/               # 页面 (Home 大厅, GameRoom 游戏房间)
│       └── types/               # TypeScript 类型定义 (与后端 Pydantic 模型对应)
├── server/                      # Python 后端
│   ├── card_engine/             # 核心牌引擎 (牌模型/识别/比较/发牌)
│   ├── game_engine/             # 游戏逻辑 (状态机/计分/回合计时器)
│   ├── network/                 # 网络层 (GameServer/WebSocket协议/房间管理/分数存储)
│   ├── config.py                # 服务配置 (端口/CORS/静态文件路径)
│   └── main.py                  # FastAPI 应用入口
├── tests/                       # 后端测试
├── requirements.txt             # 后端依赖
└── README.md                    # 本文件
```

## WebSocket 协议

客户端与服务器通过 WebSocket 进行 JSON 消息通信，消息格式：

```json
{
  "type": "PLAY",
  "payload": { ... },
  "timestamp": 1234567890.0,
  "player_id": "xxx"
}
```

### 消息类型

| 类型 | 方向 | 说明 |
|---|---|---|
| `JOIN` | → 服务端 | 加入房间 |
| `LEAVE` | → 服务端 | 离开房间 |
| `START_GAME` | → 服务端 | 开始游戏 |
| `PLAY` | → 服务端 | 出牌 |
| `PASS` | → 服务端 | 过牌 |
| `DECLARE` | → 服务端 | 声明包牌 |
| `READY` | → 服务端 | 准备就绪 |
| `AUTO_PLAY` | → 服务端 | 切换托管模式 |
| `PING` | → 服务端 | 心跳检测 |
| `STATE_SYNC` | ← 客户端 | 游戏状态同步 |
| `GAME_START` | ← 客户端 | 游戏开始通知 |
| `ROUND_END` | ← 客户端 | 回合结算 |
| `ERROR` | ← 客户端 | 错误信息 |

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_comparator.py -v
python -m pytest tests/test_state_machine.py -v
```

## 生成音效

```bash
# 重新生成所有 TTS 语音播报文件
python -m server.generate_sounds
```

## API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/scores` | 获取所有玩家历史总分 |
| `POST` | `/api/scores/{player_name}?delta=N` | 更新玩家分数 |
| `POST` | `/api/admin/reset` | 重置所有游戏房间 |
| `GET` | `/debug/room/{room_id}` | 调试：查看房间原始状态 |

## License

MIT
