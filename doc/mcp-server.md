# 《史记》MCP Server 使用说明

## 这是什么

`mcp_server` 是这个仓库的首版 MCP 服务封装，定位是“确定性检索层”，把现有《史记》知识资产通过 stdio MCP 暴露给外部客户端调用。

当前版本不在服务端直接生成自然语言答案，而是提供可组合的基础能力：

- 章节目录查询
- 整章读取
- 锚点片段读取
- 实体检索与按章消歧
- 人物关系查询
- 事件检索

适用场景：

- 在支持 MCP 的客户端里，把《史记》作为可调用知识库接入
- 给后续的 Wiki、问答、时间线、人物卡片等应用提供稳定数据接口
- 作为 GraphRAG / Agent 工作流里的“原始事实检索层”使用

## 服务能力

### Tools

| Tool | 作用 | 常用参数 |
|------|------|----------|
| `list_chapters` | 列出章节目录 | `limit` |
| `get_chapter` | 读取章节元信息，可选整章内容 | `chapter_id`, `include_content` |
| `get_passage` | 按锚点读取原文片段和上下文 | `chapter_id`, `anchor`, `window` |
| `lookup_entity` | 检索实体，支持别名和章节消歧 | `name`, `chapter_id`, `entity_type`, `limit` |
| `query_relations` | 查询人物关系 | `name`, `other_name`, `relation_type`, `chapter_id`, `limit` |
| `search_events` | 检索事件索引 | `keyword`, `person`, `chapter_id`, `event_type`, `limit` |

### Resources

| Resource | 作用 |
|----------|------|
| `shiji://about` | 服务概览 |
| `shiji://catalog/chapters` | 章节目录资源 |
| `shiji://chapter/{chapter_id}` | 整章 tagged 原文 |
| `shiji://entity/{name}` | 某个实体的资源视图 |

## 本地启动

推荐直接在项目虚拟环境里启动，避免“客户端调用的 Python”和“安装 `mcp` 的 Python”不一致。

```bash
cd /Users/raymond/workspace/shiji-kb

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-mcp.txt

python -m mcp_server
```

说明：

- 服务使用 stdio transport。
- 启动后会等待 MCP 客户端接入，不会像普通 CLI 一样输出交互提示。
- 如果你已经有可用的 `.venv`，只需要激活后执行 `pip install -r requirements-mcp.txt`。

## 客户端接入

### 在 VS Code 中接入

这个仓库已经放好了工作区级配置文件 [/.vscode/mcp.json](.vscode/mcp.json)。当前内容如下：

```json
{
  "servers": {
    "shiji-kb": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

这意味着你在 VS Code 里打开当前仓库后，不需要再手写工作区配置，只需要保证虚拟环境和依赖已经就绪。

建议按这个顺序使用：

1. 在仓库根目录准备运行环境。
2. 确认 `.venv` 里已经安装了 `mcp`。
3. 在 VS Code 命令面板里检查并启动 `shiji-kb` 服务器。
4. 在 Copilot Chat 的 Agent 模式里直接用自然语言调用。

准备环境：

```bash
cd /Users/raymond/workspace/shiji-kb
source .venv/bin/activate
pip install -r requirements-mcp.txt
```

在 VS Code 里可用的入口包括：

- `MCP: Open Workspace Folder MCP Configuration`
- `MCP: Show Installed Servers`
- `MCP: Start Server`
- `MCP: Show Output`
- `MCP: Browse MCP Servers`

推荐你先执行：

1. `MCP: Show Installed Servers`
2. 确认列表里有 `shiji-kb`
3. 如果没有自动启动，再执行 `MCP: Start Server`
4. 如果启动失败，执行 `MCP: Show Output` 看日志

如果你不想把配置放在仓库里，也可以走用户级配置。VS Code 内置了 `Add Server...` 入口，接受这种 JSON：

```json
{
  "name": "shiji-kb",
  "command": "/Users/raymond/workspace/shiji-kb/.venv/bin/python",
  "args": ["-m", "mcp_server"],
  "cwd": "/Users/raymond/workspace/shiji-kb"
}
```

对应的用户配置入口有：

- `MCP: Open User Configuration`
- `MCP: Add Server...`

### 在 VS Code Chat 里怎么用

当 `shiji-kb` 已经启动后，可以直接在 Copilot Chat 的 Agent 模式里用自然语言调用它，不需要手写 MCP 协议报文。

可以直接这样问：

- “用 shiji-kb 查一下韩信在 092 里的实体信息。”
- “检索韩信相关事件，只返回 2 条，并保留 event_id 和 anchor。”
- “读取 092 章 12.1 附近原文，带上下文。”
- “查询韩信和刘邦的关系，并给出对应章节。”

更稳妥的提问方式是把意图说清楚：

- 要查哪一类数据：章节、实体、关系、事件、原文片段
- 过滤条件是什么：人物名、章节号、锚点、关系类型、数量上限
- 输出要保留哪些字段：例如 `event_id`、`anchor`、`resource_uri`

例如：

```text
用 shiji-kb 检索韩信在 092_淮阴侯列传 里的相关事件，最多返回 3 条。
每条保留 event_id、event_name、anchor、quote。
```

如果你要的是“先检索再回原文”的链路，建议这样说：

```text
先查韩信在 092 章里的事件，再对第一条结果回跳原文片段，展示对应 anchor 的上下文。
```

这样 Agent 通常会先调用 `search_events`，再调用 `get_passage`，结果会更稳定。

这是一个标准 stdio MCP 服务。客户端只需要知道以下三项：

- `command`：启动服务的 Python 解释器
- `args`：`["-m", "mcp_server"]`
- `cwd`：仓库根目录 `/Users/raymond/workspace/shiji-kb`

如果你使用项目内虚拟环境，推荐配置为：

```json
{
  "command": "/Users/raymond/workspace/shiji-kb/.venv/bin/python",
  "args": ["-m", "mcp_server"],
  "cwd": "/Users/raymond/workspace/shiji-kb"
}
```

不管你接入的是哪个 MCP 客户端，核心原则都一样：

- 客户端启动的解释器，必须就是安装了 `mcp` 包的解释器。
- `cwd` 必须指向仓库根目录，这样服务才能读到 `chapter_md/`、`kg/` 等数据目录。

## 参数约定

### `chapter_id`

以下形式都可用：

- `092`
- `092_淮阴侯列传`
- `淮阴侯列传`
- `092_淮阴侯列传.tagged.md`

### `anchor`

`get_passage` 使用章节内锚点，例如：

- `12.1`
- `3.4`

建议先通过整章 tagged 文本或已有页面确认锚点，再做精确片段抓取。

### 结果数量限制

- `list_chapters.limit`: `1` 到 `130`
- `lookup_entity.limit`: `1` 到 `25`
- `query_relations.limit`: `1` 到 `100`
- `search_events.limit`: `1` 到 `100`
- `get_passage.window`: `0` 到 `5`

## 最小调用示例

### 例 1：实体检索

请求参数：

```json
{
  "name": "韩信",
  "chapter_id": "092"
}
```

典型返回字段：

- `query`
- `chapter_context`
- `disambiguated_name`
- `match_count`
- `matches`

`matches` 中会带上：

- `canonical_name`
- `aliases`
- `entity_type`
- `refs`
- `resource_uri`

### 例 2：读取原文片段

请求参数：

```json
{
  "chapter_id": "092",
  "anchor": "12.1",
  "window": 1
}
```

适合做：

- 根据关系或事件结果回跳原文
- 给问答结果补“证据片段”
- 在 Wiki 页面里做精确引用

### 例 3：检索人物相关事件

请求参数：

```json
{
  "person": "韩信",
  "chapter_id": "092",
  "limit": 2
}
```

返回结果里会包含：

- `event_id`
- `event_name`
- `event_type`
- `anchor`
- `description`
- `quote`

## Python 客户端最小自测

下面这段代码已经在当前仓库环境里跑通过，可以直接作为自测模板：

```python
import asyncio
from mcp import ClientSession, StdioServerParameters, stdio_client


async def main() -> None:
    server = StdioServerParameters(
        command="/Users/raymond/workspace/shiji-kb/.venv/bin/python",
        args=["-m", "mcp_server"],
        cwd="/Users/raymond/workspace/shiji-kb",
    )

    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print([tool.name for tool in tools.tools])

            entity = await session.call_tool(
                "lookup_entity",
                {"name": "韩信", "chapter_id": "092"},
            )
            print(entity.structuredContent["match_count"])

            passage = await session.call_tool(
                "get_passage",
                {"chapter_id": "092", "anchor": "12.1", "window": 1},
            )
            print(passage.structuredContent["target"]["anchor"])

            chapter = await session.read_resource("shiji://chapter/092")
            print(chapter.contents[0].text[:80])


asyncio.run(main())
```

注意：

- Python MCP 客户端里，工具结果通常从 `result.structuredContent` 读取。
- 如果你只看展示文本，也可以读 `result.content[0].text`。

## 推荐使用方式

最稳妥的调用链是：

1. 先 `list_chapters` 或读 `shiji://catalog/chapters`，拿到章节编号。
2. 再用 `lookup_entity`、`query_relations`、`search_events` 缩小检索范围。
3. 最后用 `get_passage` 或 `shiji://chapter/{chapter_id}` 回到原文证据。

这样做的好处是：

- 先查结构化索引，再回到原文，速度更快。
- 每个结果都能落回《史记》具体章节和锚点，便于引用和校验。
- 适合后续叠加 Agent 推理，但不会把“生成答案”和“事实检索”混在一起。

## 排障

### `ModuleNotFoundError: No module named 'mcp'`

通常是解释器装错了。请确认：

- 你运行 `python -m mcp_server` 用的是哪个 Python
- 你执行 `pip install -r requirements-mcp.txt` 装到的是不是同一个 Python

最简单的办法是始终使用：

```bash
source /Users/raymond/workspace/shiji-kb/.venv/bin/activate
python -m mcp_server
```

### 客户端能启动服务，但读不到数据

优先检查：

- `cwd` 是否为 `/Users/raymond/workspace/shiji-kb`
- 仓库里的 `chapter_md/`、`kg/` 是否完整存在

### `Unknown chapter` 或 `Anchor not found`

先做这两步：

1. 用 `list_chapters` 确认章节编号。
2. 用整章资源 `shiji://chapter/{chapter_id}` 确认实际锚点。

## 当前边界

当前版本刻意保持简单：

- 有检索，不直接生成问答答案
- 有实体/关系/事件/原文回跳，不做复杂推理编排
- 有资源接口，不绑定 LangChain 或某个特定前端框架

这意味着它很适合作为后续应用层的“稳定底座”，而不是一次性把检索、推理、展示全部耦合在服务端。