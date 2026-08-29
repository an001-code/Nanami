# 七海 Nanami —— 智能桌宠 Agent

一只常驻 Windows 桌面的 AI 数字伙伴：会动、会说话、有长期记忆，还能像真正的 agent 一样调用工具（联网搜索、读写工作区文件），危险操作需要权限确认。

## 技术栈

- **外壳**：Python + PySide6（仅 Windows）
- **渲染**：Live2D 立绘（Soullink Emotion SDK + Cubism Web，经 `QWebEngineView` 渲染）
- **Agent 核心**：LangGraph（ReAct 风格状态机）
- **LLM**：多服务商可切换（OpenAI 兼容协议：DeepSeek / 通义千问 / 智谱 / OpenAI / Ollama）
- **语音**：Edge TTS（合成）+ faster-whisper（识别，Phase 2）
- **长期记忆**：四层架构——PostgreSQL（完整历史）+ Redis（工作记忆 + 用户画像）+ chromadb（语义记忆）
- **工具生态**：内置工具（web_search / file_ops / remember）+ 权限系统（allow / deny / ask）；MCP 与 Skill 为 Phase 2

## 快速开始

```bash
# 1. 安装依赖
pip install -e .

# 2. 配置 API key（对话 + 语义记忆 embedding 各需一个）
set DEEPSEEK_API_KEY=sk-xxxx     # 对话模型（默认 deepseek）
set DASHSCOPE_API_KEY=sk-xxxx    # 语义记忆 embedding（通义千问）

# 3. 启动基础设施容器（可选；未启动则对应记忆功能降级跳过）
#    PostgreSQL（完整历史，端口 5432，凭据 nanami/nanami）
docker run -d --name nanami-pg \
  -e POSTGRES_USER=nanami -e POSTGRES_PASSWORD=nanami -e POSTGRES_DB=nanami \
  -p 5432:5432 postgres:16
#    Redis（工作记忆 + 画像，主机端口 6390）
docker run -d --name nanami-redis -p 6390:6379 redis:7

# 4. 运行
python -m nanami.app
```

编辑 `config/config.yaml` 可切换 LLM 服务商、音色、工作区路径等；API key 一律通过环境变量注入，不要写进配置文件。

## 仪表盘

托盘图标右键 → **仪表盘**，打开独立窗口，可：

- 查看四层记忆数据（对话历史 / 工作记忆 / 用户画像 / 语义记忆）
- 切换 Live2D 模型与 LLM 服务商（写回 `config.yaml`，重启后生效）

## 配置说明

见 [config/config.yaml](config/config.yaml)。

## 项目结构

```
src/nanami/
├── app.py            # 入口，组装所有模块
├── config.py         # 配置加载 / 写回
├── agent/            # LangGraph 核心 + LLM 抽象 + 人格提示词
├── tools/            # 工具注册表 + 内置工具（web_search / file_ops）
├── permissions/      # 权限系统（allow / deny / ask）
├── memory/           # 四层记忆（history / work_memory / profile / vector_store）
├── voice/            # TTS（edge-tts）
├── ui/               # 主窗口 / 仪表盘窗口 / QWebChannel 桥接 / 托盘
└── live2d/           # Live2D 渲染（构建产物 + 模型，运行时加载）
```

`soullink-emotion-sdk/` 是 Live2D 情绪引擎源码（MIT），仅「换模型重新构建」时使用；运行时依赖的是 `src/nanami/live2d/static/` 里已构建好的产物。

## 路线图

- **Phase 1（已完成）**：Live2D 渲染 + 文字对话 + TTS + 内置工具 + 权限 + 四层长期记忆 + 仪表盘
- **Phase 2**：MCP 客户端、Skill 加载器、语音输入、定时提醒
- **Phase 3**：屏幕感知、打包发布

## 待准备资源

- **Live2D 模型文件**（`.model3.json` / `.moc3` / 贴图 / 动作）与 **Cubism Web SDK** 需从 [Live2D 官网](https://www.live2d.com/) 获取并遵守其授权协议。
- 至少一家 LLM 服务商的 API key（对话）+ 一家 embedding 服务商的 key（语义记忆）。
