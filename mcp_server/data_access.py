from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any


PARAGRAPH_RE = re.compile(r"^\[(\d+(?:\.\d+)*)\]\s*(.*)$")
HEADER_PREFIX_RE = re.compile(r"^#+\s*")
TAGGED_ENTITY_RE = re.compile(r"〖.([^〖〗]+)〗")


def clean_tagged_text(text: str) -> str:
    def replace_tagged(match: re.Match[str]) -> str:
        inner = match.group(1)
        return inner.split("|", 1)[0]

    cleaned = TAGGED_ENTITY_RE.sub(replace_tagged, text)
    cleaned = cleaned.replace("〘", "").replace("〙", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_anchor(anchor: str) -> str:
    return anchor.strip().strip("[]")


@dataclass(frozen=True)
class ChapterRecord:
    short_id: str
    chapter_id: str
    title: str
    path: Path

    @property
    def resource_uri(self) -> str:
        return f"shiji://chapter/{self.short_id}"

    def to_dict(self) -> dict[str, str]:
        return {
            "short_id": self.short_id,
            "chapter_id": self.chapter_id,
            "title": self.title,
            "path": str(self.path),
            "resource_uri": self.resource_uri,
        }


class ShijiKnowledgeBase:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or Path(__file__).resolve().parent.parent
        self.chapter_dir = self.project_root / "chapter_md"
        self.entity_index_path = self.project_root / "kg" / "entities" / "data" / "entity_index.json"
        self.aliases_path = self.project_root / "kg" / "entities" / "data" / "entity_aliases.json"
        self.disambiguation_path = self.project_root / "kg" / "entities" / "data" / "disambiguation_map.json"
        self.person_lifespans_path = self.project_root / "kg" / "entities" / "data" / "person_lifespans.json"
        self.relations_path = self.project_root / "kg" / "relations" / "all_relations.json"
        self.family_relations_path = self.project_root / "kg" / "relations" / "family_relations.json"
        self.events_summary_path = self.project_root / "kg" / "events" / "events_summary.json"
        self.events_dir = self.project_root / "kg" / "events" / "data"

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    @cached_property
    def chapter_records(self) -> list[ChapterRecord]:
        records: list[ChapterRecord] = []
        for path in sorted(self.chapter_dir.glob("*.tagged.md")):
            chapter_id = path.stem.replace(".tagged", "")
            if "_" not in chapter_id:
                continue
            short_id, title = chapter_id.split("_", 1)
            records.append(
                ChapterRecord(
                    short_id=short_id,
                    chapter_id=chapter_id,
                    title=title,
                    path=path,
                )
            )
        return records

    @cached_property
    def chapter_by_short_id(self) -> dict[str, ChapterRecord]:
        return {record.short_id: record for record in self.chapter_records}

    @cached_property
    def chapter_by_id(self) -> dict[str, ChapterRecord]:
        return {record.chapter_id: record for record in self.chapter_records}

    @cached_property
    def chapter_by_title(self) -> dict[str, ChapterRecord]:
        return {record.title: record for record in self.chapter_records}

    @cached_property
    def entity_index(self) -> dict[str, dict[str, dict[str, Any]]]:
        return self._load_json(self.entity_index_path)

    @cached_property
    def entity_aliases(self) -> dict[str, dict[str, list[str]]]:
        return self._load_json(self.aliases_path)

    @cached_property
    def disambiguation_map(self) -> dict[str, dict[str, str]]:
        return self._load_json(self.disambiguation_path)

    @cached_property
    def person_lifespans(self) -> dict[str, dict[str, Any]]:
        payload = self._load_json(self.person_lifespans_path)
        return payload.get("persons", {})

    @cached_property
    def relations_data(self) -> dict[str, list[dict[str, Any]]]:
        payload = self._load_json(self.relations_path)
        return payload.get("relations", {})

    @cached_property
    def events_summary(self) -> dict[str, Any]:
        return self._load_json(self.events_summary_path)

    @cached_property
    def entity_lookup(self) -> dict[str, list[dict[str, Any]]]:
        lookup: dict[str, list[dict[str, Any]]] = {}
        for entity_type, entries in self.entity_index.items():
            for canonical_name, payload in entries.items():
                aliases = payload.get("aliases", [])
                record = {
                    "entity_type": entity_type,
                    "canonical_name": canonical_name,
                    "aliases": aliases,
                    "refs": payload.get("refs", []),
                }
                for key in {canonical_name, *aliases}:
                    lookup.setdefault(key, []).append(record)
        return lookup

    @cached_property
    def chapter_text_cache(self) -> dict[str, str]:
        return {
            record.short_id: record.path.read_text(encoding="utf-8")
            for record in self.chapter_records
        }

    @cached_property
    def chapter_blocks_cache(self) -> dict[str, list[dict[str, Any]]]:
        cache: dict[str, list[dict[str, Any]]] = {}
        for record in self.chapter_records:
            blocks: list[dict[str, Any]] = []
            current_heading = ""
            lines = self.chapter_text_cache[record.short_id].splitlines()
            for line_number, raw_line in enumerate(lines, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    current_heading = stripped
                candidate = HEADER_PREFIX_RE.sub("", stripped)
                match = PARAGRAPH_RE.match(candidate)
                if not match:
                    continue
                anchor = match.group(1)
                text = match.group(2)
                blocks.append(
                    {
                        "anchor": anchor,
                        "text": text,
                        "plain_text": clean_tagged_text(text),
                        "heading": current_heading,
                        "line_number": line_number,
                        "kind": "heading" if stripped.startswith("#") else "paragraph",
                        "raw_line": raw_line,
                    }
                )
            cache[record.short_id] = blocks
        return cache

    @cached_property
    def event_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in sorted(self.events_dir.glob("*_事件索引.md")):
            chapter_id = path.stem.replace("_事件索引", "")
            chapter_record = self.normalize_chapter_id(chapter_id)
            if chapter_record is None:
                continue

            details: dict[str, dict[str, str]] = {}
            lines = path.read_text(encoding="utf-8").splitlines()
            current_event_id: str | None = None
            in_table = False

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### "):
                    match = re.match(r"^###\s+(\S+)\s+(.+)$", stripped)
                    if match:
                        current_event_id = match.group(1)
                        details.setdefault(current_event_id, {})["detail_title"] = match.group(2).strip()
                    continue
                if current_event_id and stripped.startswith("- **"):
                    field_match = re.match(r"^- \*\*(.+?)\*\*[:：]\s*(.*)$", stripped)
                    if field_match:
                        field_name = field_match.group(1)
                        value = field_match.group(2).strip()
                        mapping = {
                            "段落位置": "anchor",
                            "事件描述": "description",
                            "原文引用": "quote",
                            "年代推断": "time_reasoning",
                        }
                        key = mapping.get(field_name)
                        if key:
                            details.setdefault(current_event_id, {})[key] = value
                    continue

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("| 事件ID "):
                    in_table = True
                    continue
                if in_table and stripped.startswith("|--------"):
                    continue
                if in_table and not stripped.startswith("|"):
                    in_table = False
                    continue
                if not in_table:
                    continue
                parts = [part.strip() for part in stripped.split("|")[1:-1]]
                if len(parts) < 7:
                    continue

                event_id, event_name, event_type, time_text, locations, people, dynasty = parts[:7]
                if not event_id or not event_name:
                    continue
                detail = details.get(event_id, {})
                anchor = normalize_anchor(detail.get("anchor", "")) if detail.get("anchor") else ""
                record = {
                    "event_id": event_id,
                    "chapter_id": chapter_record.chapter_id,
                    "chapter_short_id": chapter_record.short_id,
                    "chapter_title": chapter_record.title,
                    "event_name": clean_tagged_text(event_name),
                    "event_name_raw": event_name,
                    "event_type": clean_tagged_text(event_type),
                    "time": clean_tagged_text(time_text),
                    "time_raw": time_text,
                    "locations": clean_tagged_text(locations),
                    "locations_raw": locations,
                    "people": clean_tagged_text(people),
                    "people_raw": people,
                    "dynasty": clean_tagged_text(dynasty),
                    "dynasty_raw": dynasty,
                    "anchor": anchor,
                    "description": detail.get("description", ""),
                    "quote": detail.get("quote", ""),
                    "time_reasoning": detail.get("time_reasoning", ""),
                    "source_path": str(path),
                    "chapter_resource_uri": chapter_record.resource_uri,
                }
                records.append(record)
        return records

    def normalize_chapter_id(self, chapter_id: str | int | None) -> ChapterRecord | None:
        if chapter_id is None:
            return None
        text = str(chapter_id).strip()
        if not text:
            return None
        if text in self.chapter_by_id:
            return self.chapter_by_id[text]
        if text in self.chapter_by_title:
            return self.chapter_by_title[text]
        if text.endswith(".tagged.md"):
            normalized = text[:-10]
            if normalized in self.chapter_by_id:
                return self.chapter_by_id[normalized]
        if "_" in text:
            prefix = text.split("_", 1)[0]
            if prefix.isdigit():
                return self.chapter_by_short_id.get(prefix.zfill(3))
        if text.isdigit():
            return self.chapter_by_short_id.get(text.zfill(3))
        for record in self.chapter_records:
            if text in record.chapter_id or text == record.title:
                return record
        return None

    def list_chapters(self, limit: int = 130) -> list[dict[str, str]]:
        bounded_limit = max(1, min(int(limit), len(self.chapter_records)))
        return [record.to_dict() for record in self.chapter_records[:bounded_limit]]

    def get_chapter(self, chapter_id: str | int, include_content: bool = False) -> dict[str, Any]:
        record = self.normalize_chapter_id(chapter_id)
        if record is None:
            raise ValueError(f"Unknown chapter: {chapter_id}")
        payload: dict[str, Any] = record.to_dict()
        payload["line_count"] = len(self.chapter_text_cache[record.short_id].splitlines())
        if include_content:
            payload["content"] = self.chapter_text_cache[record.short_id]
        return payload

    def get_chapter_text(self, chapter_id: str | int) -> str:
        record = self.normalize_chapter_id(chapter_id)
        if record is None:
            raise ValueError(f"Unknown chapter: {chapter_id}")
        return self.chapter_text_cache[record.short_id]

    def get_passage(self, chapter_id: str | int, anchor: str, window: int = 1) -> dict[str, Any]:
        record = self.normalize_chapter_id(chapter_id)
        if record is None:
            raise ValueError(f"Unknown chapter: {chapter_id}")
        normalized_anchor = normalize_anchor(anchor)
        blocks = self.chapter_blocks_cache[record.short_id]
        target_index = next((idx for idx, block in enumerate(blocks) if block["anchor"] == normalized_anchor), None)
        if target_index is None:
            raise ValueError(f"Anchor not found: {record.short_id}#{normalized_anchor}")

        bounded_window = max(0, min(int(window), 5))
        start = max(0, target_index - bounded_window)
        end = min(len(blocks), target_index + bounded_window + 1)
        excerpt_blocks = []
        for idx, block in enumerate(blocks[start:end], start=start):
            excerpt_blocks.append(
                {
                    "anchor": block["anchor"],
                    "kind": block["kind"],
                    "heading": block["heading"],
                    "raw_line": block["raw_line"],
                    "text": block["text"],
                    "plain_text": block["plain_text"],
                    "line_number": block["line_number"],
                    "is_target": idx == target_index,
                }
            )

        target_block = blocks[target_index]
        return {
            "chapter": record.to_dict(),
            "target_anchor": normalized_anchor,
            "target": {
                "anchor": target_block["anchor"],
                "kind": target_block["kind"],
                "heading": target_block["heading"],
                "raw_line": target_block["raw_line"],
                "text": target_block["text"],
                "plain_text": target_block["plain_text"],
                "line_number": target_block["line_number"],
            },
            "window": bounded_window,
            "blocks": excerpt_blocks,
        }

    def _entity_variants(self, name: str, chapter_id: str | int | None = None) -> set[str]:
        query = name.strip()
        variants = {query}
        for match in self.lookup_entity(query, chapter_id=chapter_id, limit=20)["matches"]:
            variants.add(match["canonical_name"])
            variants.update(match.get("aliases", []))
        return variants

    def lookup_entity(
        self,
        name: str,
        chapter_id: str | int | None = None,
        entity_type: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        query = name.strip()
        if not query:
            raise ValueError("name is required")

        chapter_record = self.normalize_chapter_id(chapter_id)
        chapter_key = chapter_record.short_id if chapter_record else None
        matches: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        disambiguated_name: str | None = None
        if chapter_key and query in self.disambiguation_map.get(chapter_key, {}):
            disambiguated_name = self.disambiguation_map[chapter_key][query]

        candidate_records: list[dict[str, Any]] = []
        if disambiguated_name and disambiguated_name in self.entity_lookup:
            candidate_records.extend(self.entity_lookup[disambiguated_name])
        candidate_records.extend(self.entity_lookup.get(query, []))

        if not candidate_records:
            for surface, records in self.entity_lookup.items():
                if query in surface or surface in query:
                    candidate_records.extend(records)

        bounded_limit = max(1, min(int(limit), 25))
        for candidate in candidate_records:
            if entity_type and candidate["entity_type"] != entity_type:
                continue
            key = (candidate["entity_type"], candidate["canonical_name"])
            if key in seen:
                continue
            seen.add(key)

            refs = candidate.get("refs", [])
            if chapter_record is not None:
                refs = [ref for ref in refs if ref[0] == chapter_record.chapter_id]

            alias_match = query in set(candidate.get("aliases", []))
            resolved_by = "canonical"
            if disambiguated_name and candidate["canonical_name"] == disambiguated_name:
                resolved_by = "chapter_disambiguation"
            elif alias_match:
                resolved_by = "alias"
            elif candidate["canonical_name"] != query:
                resolved_by = "partial_match"

            match = {
                "entity_type": candidate["entity_type"],
                "canonical_name": candidate["canonical_name"],
                "aliases": candidate.get("aliases", []),
                "resolved_by": resolved_by,
                "resource_uri": f"shiji://entity/{candidate['canonical_name']}",
                "ref_count": len(refs),
                "refs": [
                    {
                        "chapter_id": ref[0],
                        "anchor": ref[1],
                        "chapter_resource_uri": f"shiji://chapter/{ref[0].split('_', 1)[0]}",
                    }
                    for ref in refs[:20]
                ],
            }
            if candidate["entity_type"] == "person" and candidate["canonical_name"] in self.person_lifespans:
                match["lifespan"] = self.person_lifespans[candidate["canonical_name"]]
            matches.append(match)
            if len(matches) >= bounded_limit:
                break

        return {
            "query": query,
            "chapter_context": chapter_record.to_dict() if chapter_record else None,
            "disambiguated_name": disambiguated_name,
            "match_count": len(matches),
            "matches": matches,
        }

    def query_relations(
        self,
        name: str,
        other_name: str | None = None,
        relation_type: str | None = None,
        chapter_id: str | int | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        query_name = name.strip()
        if not query_name:
            raise ValueError("name is required")

        chapter_record = self.normalize_chapter_id(chapter_id)
        primary_variants = self._entity_variants(query_name, chapter_id=chapter_id)
        secondary_variants = self._entity_variants(other_name, chapter_id=chapter_id) if other_name else set()
        bounded_limit = max(1, min(int(limit), 100))

        matches: list[dict[str, Any]] = []
        for rel_type, relations in self.relations_data.items():
            if relation_type and rel_type != relation_type:
                continue
            for relation in relations:
                relation_chapter = relation.get("chapter", "")
                if chapter_record and relation_chapter != chapter_record.chapter_id:
                    continue

                person1 = relation.get("person1", "")
                person2 = relation.get("person2", "")
                if person1 not in primary_variants and person2 not in primary_variants:
                    continue
                if secondary_variants and person1 not in secondary_variants and person2 not in secondary_variants:
                    continue

                matches.append(
                    {
                        "relation_type": rel_type,
                        "person1": person1,
                        "person2": person2,
                        "direction": relation.get("direction"),
                        "chapter_id": relation_chapter,
                        "chapter_resource_uri": f"shiji://chapter/{relation_chapter.split('_', 1)[0]}" if relation_chapter else None,
                        "context": relation.get("context", ""),
                    }
                )
                if len(matches) >= bounded_limit:
                    break
            if len(matches) >= bounded_limit:
                break

        return {
            "query": query_name,
            "other_name": other_name,
            "relation_type": relation_type,
            "chapter_context": chapter_record.to_dict() if chapter_record else None,
            "available_relation_types": sorted(self.relations_data.keys()),
            "match_count": len(matches),
            "matches": matches,
        }

    def search_events(
        self,
        keyword: str | None = None,
        person: str | None = None,
        chapter_id: str | int | None = None,
        event_type: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        if not any([keyword, person, chapter_id, event_type]):
            raise ValueError("At least one filter is required")

        keyword_text = keyword.strip() if keyword else None
        chapter_record = self.normalize_chapter_id(chapter_id)
        person_variants = self._entity_variants(person, chapter_id=chapter_id) if person else set()
        bounded_limit = max(1, min(int(limit), 100))
        matches: list[dict[str, Any]] = []

        for event in self.event_records:
            if chapter_record and event["chapter_short_id"] != chapter_record.short_id:
                continue
            if event_type and event["event_type"] != event_type:
                continue
            if keyword_text:
                haystack = " ".join(
                    [
                        event["event_name"],
                        event.get("description", ""),
                        event.get("quote", ""),
                        event.get("people", ""),
                        event.get("locations", ""),
                    ]
                )
                if keyword_text not in haystack:
                    continue
            if person_variants:
                people_text = event.get("people", "")
                if not any(variant in people_text for variant in person_variants):
                    continue

            matches.append(event)
            if len(matches) >= bounded_limit:
                break

        return {
            "query": {
                "keyword": keyword,
                "person": person,
                "chapter_id": chapter_record.to_dict() if chapter_record else None,
                "event_type": event_type,
            },
            "match_count": len(matches),
            "matches": matches,
        }
