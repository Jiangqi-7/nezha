# neZha

一个给 Agent 使用的 Agent。

## 快速开始

```bash
# 安装依赖
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 交互模式
uv run nezha-cli --interactive

# 单次调用
uv run nezha-cli --role tech --prompt "帮我分析这段代码"

# MCP Server
uv run nezha-mcp
```

## 角色

| 角色 | 说明 |
|------|------|
| lawyer | 合同风险、法律建议 |
| tech | 代码、架构、技术选型 |
| marketing | 推广策略、用户增长 |
| screenwriter | 剧本创作 |
| resume_coach | 简历优化 |
| picky_boss | 挑剔老板模拟 |
| ai_comic_creator | AI漫画创作 |
| image_prompt_generator | 图片提示词生成 |
| json_prompt_generator | JSON提示词生成 |
| nanobanana2 | 电影级拼图大导 |

## 架构

- LangGraph StateGraph + MessagesState + add_messages reducer
- MemorySaver 自动保存/恢复消息历史
- 双入口：CLI + MCP Server（stdio 模式）
- 角色切换时通过 store 中转保存各角色历史

## 配置

所有配置在 `config/config.yaml` 中统一管理。

```yaml
app:
  name: nezha
  cli: nezha-cli
  mcp: nezha-mcp

model:
  provider: dashscope-aliyun
  model: qwen3-8b
  api_key: ${DASHSCOPE_API_KEY}
  base_url: ${DASHSCOPE_BASE_URL}

roles:
  lawyer:
    name: 律师
    prompt_file: prompts/lawyer.md
```

## 入口

| 命令 | 说明 |
|------|------|
| `nezha-cli --interactive` | 交互模式 |
| `nezha-cli --role xxx --prompt "..."` | 单次调用 |
| `nezha-cli server` | 启动 TCP 服务 |
| `nezha-mcp` | MCP Server（stdio） |
