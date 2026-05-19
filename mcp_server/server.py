from __future__ import annotations

from typing import Any

from mcp.server import FastMCP

from .data_access import ShijiKnowledgeBase


kb = ShijiKnowledgeBase()
mcp = FastMCP("Shiji Knowledge Base")


@mcp.tool()
def list_chapters(limit: int = 130) -> list[dict[str, str]]:
    """列出可供检索的《史记》章节元信息。"""

    return kb.list_chapters(limit=limit)


@mcp.tool()
def get_chapter(chapter_id: str, include_content: bool = False) -> dict[str, Any]:
    """按章节编号获取章节元信息，可选返回整章 tagged 原文。"""

    return kb.get_chapter(chapter_id=chapter_id, include_content=include_content)


@mcp.tool()
def get_passage(chapter_id: str, anchor: str, window: int = 1) -> dict[str, Any]:
    """按章节和锚点读取精确原文片段，并附带相邻上下文。"""

    return kb.get_passage(chapter_id=chapter_id, anchor=anchor, window=window)


@mcp.tool()
def lookup_entity(
    name: str,
    chapter_id: str | None = None,
    entity_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """查找实体，支持别名与按章节的人名消歧。"""

    return kb.lookup_entity(name=name, chapter_id=chapter_id, entity_type=entity_type, limit=limit)


@mcp.tool()
def query_relations(
    name: str,
    other_name: str | None = None,
    relation_type: str | None = None,
    chapter_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """查询人物关系网络，可按关系类型、另一人物和章节过滤。"""

    return kb.query_relations(
        name=name,
        other_name=other_name,
        relation_type=relation_type,
        chapter_id=chapter_id,
        limit=limit,
    )


@mcp.tool()
def search_events(
    keyword: str | None = None,
    person: str | None = None,
    chapter_id: str | None = None,
    event_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """检索事件索引，可按关键词、人物、章节和事件类型过滤。"""

    return kb.search_events(
        keyword=keyword,
        person=person,
        chapter_id=chapter_id,
        event_type=event_type,
        limit=limit,
    )


@mcp.resource("shiji://about")
def about_resource() -> dict[str, Any]:
    """服务概览与当前首版能力说明。"""

    return {
        "name": "Shiji Knowledge Base",
        "stage": "MCP MVP",
        "capabilities": [
            "entity lookup",
            "chapter lookup",
            "anchor passage retrieval",
            "relation query",
            "event search",
        ],
        "notes": [
            "首版专注确定性检索，不在服务端直接生成问答答案。",
            "SKU 与冲突/异常索引计划在后续阶段接入。",
        ],
        "chapter_catalog_uri": "shiji://catalog/chapters",
    }


@mcp.resource("shiji://catalog/chapters")
def chapter_catalog_resource() -> dict[str, Any]:
    """返回章节目录，供客户端或模型快速建立章节导航。"""

    return {"chapters": kb.list_chapters()}


@mcp.resource("shiji://chapter/{chapter_id}")
def chapter_resource(chapter_id: str) -> str:
    """读取整章 tagged 原文。"""

    return kb.get_chapter_text(chapter_id)


@mcp.resource("shiji://entity/{name}")
def entity_resource(name: str) -> dict[str, Any]:
    """读取实体检索结果的资源视图。"""

    return kb.lookup_entity(name=name, limit=20)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()