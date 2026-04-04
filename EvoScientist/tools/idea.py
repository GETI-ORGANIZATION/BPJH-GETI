"""Idea workflow helpers for interactive literature-driven ideation."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from langchain_core.tools import tool

from ..config import get_effective_config
from ..llm import get_chat_model
from .search import _load_jsonl, collect_sources, crawl_site_articles, extract_claims, read_paper_source

DEFAULT_IDEA_DIR = Path("artifacts") / "ideas"
DEFAULT_RUNS_DIR = DEFAULT_IDEA_DIR / "runs"
DEFAULT_DOC_STATE = DEFAULT_IDEA_DIR / "feishu_docs.json"
DEFAULT_PIPELINE_LOG = DEFAULT_IDEA_DIR / "latest_pipeline_log.md"
DEFAULT_PIPELINE_RUN_STATE = DEFAULT_IDEA_DIR / "last_run.json"


def _idea_root() -> Path:
    root = Path.cwd() / DEFAULT_IDEA_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _runs_root() -> Path:
    root = Path.cwd() / DEFAULT_RUNS_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _new_run_dir(query: str) -> tuple[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(query or "idea-run")
    run_id = f"{timestamp}-{slug}"
    run_dir = _runs_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_id, run_dir


def _display_path(path: Path | str) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        return candidate.as_posix()


class IdeaPipelineLogger:
    """Persist a markdown log for one idea pipeline run."""

    def __init__(self, query: str, request_text: str, *, run_dir: Path):
        root = _idea_root()
        self.path = run_dir / "pipeline_log.md"
        self.latest_path = root / DEFAULT_PIPELINE_LOG.name
        self.query = query or "N/A"
        self.request_text = request_text.strip()
        self.entries: list[dict[str, str]] = []
        self.persist()

    def add(self, step: str, status: str, details: str) -> None:
        self.entries.append(
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "step": step.strip(),
                "status": status.strip().upper(),
                "details": details.strip(),
            }
        )
        self.persist()

    def persist(self) -> None:
        lines = [
            "# Idea Pipeline Log",
            "",
            f"- Query: {self.query}",
            f"- Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Log Path: {_display_path(self.path)}",
            "",
            "## Request",
            self.request_text or "N/A",
            "",
            "## Steps",
        ]
        if not self.entries:
            lines.append("- Pipeline initialized.")
        else:
            for idx, entry in enumerate(self.entries, start=1):
                lines.extend(
                    [
                        f"### Step {idx}: {entry['step']}",
                        f"- Time: {entry['time']}",
                        f"- Status: {entry['status']}",
                        f"- Details: {entry['details']}",
                        "",
                    ]
                )
        payload = "\n".join(lines).rstrip() + "\n"
        self.path.write_text(payload, encoding="utf-8")
        self.latest_path.write_text(payload, encoding="utf-8")


def _save_last_run_state(payload: dict[str, Any]) -> None:
    state_path = _idea_root() / DEFAULT_PIPELINE_RUN_STATE.name
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_run_index(payload: dict[str, Any]) -> None:
    index_path = _runs_root() / "index.json"
    existing: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []
    existing.append(payload)
    index_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_lines = [
        "# Idea Exploration History",
        "",
        f"- Run Count: {len(existing)}",
        "",
    ]
    for item in reversed(existing):
        markdown_lines.extend(
            [
                f"## {item.get('run_id', 'unknown-run')}",
                f"- Query: {item.get('query', 'N/A')}",
                f"- Created At: {item.get('created_at', 'N/A')}",
                f"- Run Directory: {item.get('run_dir', '')}",
                f"- Candidates JSON: {item.get('candidates_json_path', '')}",
                f"- Pipeline Log: {item.get('log_path', '')}",
                "",
            ]
        )
    (_runs_root() / "index.md").write_text(
        "\n".join(markdown_lines).rstrip() + "\n",
        encoding="utf-8",
    )


def _safe_int(value: str, default: int) -> int:
    try:
        parsed = int(str(value).strip())
        return parsed
    except Exception:
        return default


def _normalize_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        parts = value
    else:
        parts = re.split(r"[,;\n]+", value)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = str(part).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return cleaned[:80] or "idea"


def _extract_urls(text: str) -> list[str]:
    urls = re.findall(r"https?://[^\s<>\]\)]+", text)
    ordered: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = url.rstrip(".,;")
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def parse_idea_request_text(text: str) -> dict[str, Any]:
    """Parse a user-friendly ideation request into structured fields.

    Supported format example::

        /idea start
        query: multimodal scientific discovery
        requirements: novel, interesting, low-cost
        urls:
        - https://example.com/paper-1
        - https://example.com/paper-2
        notes:
        - focus on practical experiments
    """
    lines = [line.rstrip() for line in text.splitlines()]
    data: dict[str, list[str] | str] = {
        "query": "",
        "requirements": [],
        "seed_urls": [],
        "site_urls": [],
        "notes": [],
        "max_ideas": "3",
        "max_sources": "4",
    }
    current_key: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            current_key = None
            continue
        if line.startswith("/idea"):
            continue

        key_match = re.match(
            r"^(query|requirements|requirement|urls|url|seed_urls|seeds|site_urls|sites|notes|max_ideas|max_sources)\s*:\s*(.*)$",
            line,
            flags=re.IGNORECASE,
        )
        if key_match:
            raw_key = key_match.group(1).lower()
            value = key_match.group(2).strip()
            mapped_key = {
                "query": "query",
                "requirements": "requirements",
                "requirement": "requirements",
                "urls": "seed_urls",
                "url": "seed_urls",
                "seed_urls": "seed_urls",
                "seeds": "seed_urls",
                "site_urls": "site_urls",
                "sites": "site_urls",
                "notes": "notes",
                "max_ideas": "max_ideas",
                "max_sources": "max_sources",
            }[raw_key]
            current_key = mapped_key
            if value:
                if mapped_key == "query":
                    data["query"] = value
                elif mapped_key in ("max_ideas", "max_sources"):
                    data[mapped_key] = value
                else:
                    cast_list = data[mapped_key]
                    assert isinstance(cast_list, list)
                    cast_list.extend(
                        _extract_urls(value)
                        if mapped_key in ("seed_urls", "site_urls")
                        else _normalize_list(value)
                    )
            continue

        if line.startswith("- ") or line.startswith("* "):
            item = line[2:].strip()
            if current_key in ("seed_urls", "site_urls"):
                cast_list = data[current_key]
                assert isinstance(cast_list, list)
                cast_list.extend(_extract_urls(item) or [item])
            elif current_key in ("requirements", "notes"):
                cast_list = data[current_key]
                assert isinstance(cast_list, list)
                cast_list.append(item)
            elif current_key == "query":
                data["query"] = f"{data['query']} {item}".strip()
            elif current_key in ("max_ideas", "max_sources"):
                data[current_key] = item
            continue

        if current_key in ("seed_urls", "site_urls"):
            cast_list = data[current_key]
            assert isinstance(cast_list, list)
            cast_list.extend(_extract_urls(line) or [line])
        elif current_key in ("requirements", "notes"):
            cast_list = data[current_key]
            assert isinstance(cast_list, list)
            cast_list.extend(_normalize_list(line))
        elif current_key in ("max_ideas", "max_sources"):
            data[current_key] = line
        elif current_key == "query":
            data["query"] = f"{data['query']} {line}".strip()
        else:
            if not data["query"]:
                data["query"] = line
            else:
                cast_list = data["notes"]
                assert isinstance(cast_list, list)
                cast_list.append(line)

    if not data["query"]:
        non_url_text = re.sub(r"https?://[^\s<>\]\)]+", " ", text)
        non_url_text = re.sub(r"\s+", " ", non_url_text).strip()
        data["query"] = non_url_text

    merged_urls = data["seed_urls"] + _extract_urls(text)
    data["seed_urls"] = _normalize_list(merged_urls)
    data["site_urls"] = _normalize_list(data["site_urls"])
    data["requirements"] = _normalize_list(data["requirements"])
    data["notes"] = _normalize_list(data["notes"])
    return {
        "query": str(data["query"]).strip(),
        "requirements": data["requirements"],
        "seed_urls": data["seed_urls"],
        "site_urls": data["site_urls"],
        "notes": data["notes"],
        "max_ideas": max(1, min(_safe_int(str(data["max_ideas"]), 3), 8)),
        "max_sources": max(1, min(_safe_int(str(data["max_sources"]), 4), 12)),
        "raw_text": text.strip(),
    }


def _idea_evidence_matches(record: dict[str, Any], query_terms: list[str], url_set: set[str]) -> tuple[int, float]:
    if url_set and record.get("url") in url_set:
        return (999, float(record.get("relevance_score", 0.0)))
    haystack = "\n".join(
        [
            str(record.get("title", "")),
            str(record.get("summary", "")),
            " ".join(str(item) for item in record.get("claims", [])),
        ]
    ).lower()
    overlap = sum(1 for term in query_terms if term and term in haystack)
    return (overlap, float(record.get("relevance_score", 0.0)))


def _select_evidence(
    records: list[dict[str, Any]],
    query: str,
    evidence_urls: list[str],
    max_evidence: int,
) -> list[dict[str, Any]]:
    query_terms = [term.lower() for term in re.findall(r"[a-zA-Z0-9\u4e00-\u9fff]+", query) if len(term) > 1]
    url_set = set(evidence_urls)
    ranked = sorted(
        records,
        key=lambda record: _idea_evidence_matches(record, query_terms, url_set),
        reverse=True,
    )
    filtered = [
        record for record in ranked if _idea_evidence_matches(record, query_terms, url_set)[0] > 0 or not query_terms
    ]
    if url_set:
        filtered = [record for record in ranked if record.get("url") in url_set] or filtered
    return filtered[:max_evidence]


def _render_idea_brief_markdown(
    *,
    title: str,
    query: str,
    idea_description: str,
    requirements: list[str],
    notes: list[str],
    evidence_records: list[dict[str, Any]],
) -> str:
    lines = [
        f"# {title}",
        "",
        "## Idea Description",
        idea_description.strip() or "TBD",
        "",
        "## Research Request",
        f"- Query: {query or 'N/A'}",
    ]
    if requirements:
        lines.append(f"- Requirements: {', '.join(requirements)}")
    if notes:
        lines.append(f"- Notes: {', '.join(notes)}")
    lines.extend(["", "## Relevant Evidence And Research Results"])
    if not evidence_records:
        lines.append("- No evidence has been linked yet.")
    else:
        for idx, record in enumerate(evidence_records, start=1):
            lines.extend(
                [
                    f"### Evidence {idx}: {record.get('title', 'Untitled')}",
                    f"- URL: {record.get('url', '')}",
                    f"- Source Type: {record.get('source_type', 'unknown')}",
                    f"- Relevance Score: {record.get('relevance_score', 0.0)}",
                    f"- Summary: {record.get('summary', '') or 'N/A'}",
                ]
            )
            claims = record.get("claims", []) or []
            if claims:
                lines.append("- Research Results:")
                for claim in claims:
                    lines.append(f"  - {claim}")
            lines.append("")

    lines.extend(
        [
            "## Open Questions",
            "- What is the strongest novelty claim compared with existing work?",
            "- Which experiments would most directly validate this idea?",
            "- What assumptions or risks still need to be checked?",
            "",
            "## Sources",
        ]
    )
    if evidence_records:
        for record in evidence_records:
            lines.append(f"- {record.get('title', 'Untitled')}: {record.get('url', '')}")
    else:
        lines.append("- None yet")
    lines.append("")
    return "\n".join(lines)


def _render_source_index_markdown(query: str, sources: list[dict[str, Any]]) -> str:
    lines = [
        "# Source Index",
        "",
        f"- Query: {query or 'N/A'}",
        f"- Source Count: {len(sources)}",
        "",
    ]
    if not sources:
        lines.append("No sources were collected.")
        return "\n".join(lines) + "\n"
    for source in sources:
        lines.extend(
            [
                f"## {source.get('rank', '-')}. {source.get('title', source.get('url', 'Untitled'))}",
                f"- URL: {source.get('url', '')}",
                f"- Source Type: {source.get('source_type', 'unknown')}",
            ]
        )
        snippet = str(source.get("snippet", "")).strip()
        if snippet:
            lines.append(f"- Snippet: {snippet}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_evidence_markdown(query: str, evidence_records: list[dict[str, Any]]) -> str:
    lines = [
        "# Evidence Report",
        "",
        f"- Query: {query or 'N/A'}",
        f"- Evidence Rows: {len(evidence_records)}",
        "",
    ]
    if not evidence_records:
        lines.append("No evidence records are available.")
        return "\n".join(lines) + "\n"
    for idx, record in enumerate(evidence_records, start=1):
        lines.extend(
            [
                f"## Evidence {idx}: {record.get('title', 'Untitled')}",
                f"- URL: {record.get('url', '')}",
                f"- Relevance Score: {record.get('relevance_score', 0.0)}",
                f"- Summary: {record.get('summary', '') or 'N/A'}",
            ]
        )
        claims = record.get("claims", []) or []
        if claims:
            lines.append("- Claims:")
            for claim in claims:
                lines.append(f"  - {claim}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _doc_state_path() -> Path:
    root = _idea_root()
    return root / DEFAULT_DOC_STATE.name


def _load_doc_state() -> dict[str, Any]:
    path = _doc_state_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_doc_state(state: dict[str, Any]) -> None:
    path = _doc_state_path()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


class FeishuIdeaDocClient:
    """Minimal Feishu docx client for idea briefs.

    The previous markdown import-task flow was accepted by Feishu but the task
    later failed server-side for this tenant. This client now creates a docx
    directly and appends plain text blocks converted from markdown.
    """

    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        domain: str = "https://open.feishu.cn",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.domain = domain.rstrip("/")
        self._http_client = http_client
        self._token: str | None = None

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
        return self._http_client

    async def aclose(self) -> None:
        if self._http_client is not None:
            await self._http_client.aclose()

    async def _access_token(self) -> str:
        if self._token:
            return self._token
        client = await self._ensure_http()
        response = await client.post(
            f"{self.domain}/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(data.get("msg") or "Failed to fetch Feishu access token")
        self._token = data["tenant_access_token"]
        return self._token

    async def _headers(self) -> dict[str, str]:
        token = await self._access_token()
        return {"Authorization": f"Bearer {token}"}

    async def _root_folder_token(self) -> str:
        client = await self._ensure_http()
        response = await client.get(
            f"{self.domain}/open-apis/drive/explorer/v2/root_folder/meta",
            headers=await self._headers(),
        )
        data = response.json()
        if data.get("code") != 0:
            raise RuntimeError(data.get("msg") or "Failed to fetch Feishu root folder")
        return data["data"]["token"]

    async def _folder_children(self, *, folder_token: str) -> list[dict[str, Any]]:
        client = await self._ensure_http()
        children: list[dict[str, Any]] = []
        page_token = ""

        while True:
            params: dict[str, Any] = {"page_size": 200}
            if page_token:
                params["page_token"] = page_token
            response = await client.get(
                f"{self.domain}/open-apis/drive/explorer/v2/folder/{folder_token}/children",
                headers=await self._headers(),
                params=params,
            )
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(
                    payload.get("msg")
                    or f"Failed to list Feishu folder children: {json.dumps(payload, ensure_ascii=False)}"
                )
            data = payload.get("data", {})
            batch = data.get("children") or data.get("items") or data.get("files") or []
            if isinstance(batch, list):
                children.extend(batch)
            if not data.get("has_more"):
                break
            page_token = str(data.get("page_token", "") or "")
            if not page_token:
                break
        return children

    def _folder_payload_to_record(self, child: dict[str, Any]) -> dict[str, Any] | None:
        child_name = str(child.get("name") or child.get("title") or "").strip()
        child_type = str(
            child.get("type") or child.get("file_type") or child.get("obj_type") or ""
        ).lower()
        if child_type and child_type != "folder":
            return None
        token = child.get("token", "") or child.get("folder_token", "") or child.get("node_token", "")
        if not token:
            return None
        return {
            "token": token,
            "url": child.get("url", ""),
            "name": child_name,
            "created": False,
        }

    async def list_child_folders(self, *, parent_folder_token: str) -> list[dict[str, Any]]:
        folders: list[dict[str, Any]] = []
        for child in await self._folder_children(folder_token=parent_folder_token):
            folder = self._folder_payload_to_record(child)
            if folder is not None:
                folders.append(folder)
        return folders

    async def find_child_folder(
        self,
        *,
        parent_folder_token: str,
        name: str,
    ) -> dict[str, Any] | None:
        for child in await self.list_child_folders(parent_folder_token=parent_folder_token):
            if str(child.get("name", "")).strip() == name:
                return child
        return None

    async def create_folder(
        self,
        *,
        parent_folder_token: str,
        name: str,
    ) -> dict[str, Any]:
        client = await self._ensure_http()
        response = await client.post(
            f"{self.domain}/open-apis/drive/explorer/v2/folder/{parent_folder_token}",
            headers={**(await self._headers()), "Content-Type": "application/json; charset=utf-8"},
            json={"title": name},
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                payload.get("msg")
                or f"Failed to create Feishu folder: {json.dumps(payload, ensure_ascii=False)}"
            )
        data = payload.get("data", {})
        return {
            "token": data.get("token", "") or data.get("folder_token", ""),
            "url": data.get("url", ""),
            "revision": data.get("revision"),
            "name": name,
        }

    async def ensure_child_folder(
        self,
        *,
        parent_folder_token: str,
        name: str,
    ) -> dict[str, Any]:
        existing = await self.find_child_folder(
            parent_folder_token=parent_folder_token,
            name=name,
        )
        if existing is not None:
            return existing

        created = await self.create_folder(parent_folder_token=parent_folder_token, name=name)
        created["created"] = True
        return created

    async def upload_drive_file(
        self,
        *,
        file_path: str,
        parent_folder_token: str,
    ) -> dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise RuntimeError(f"Local file does not exist: {file_path}")

        client = await self._ensure_http()
        with path.open("rb") as handle:
            response = await client.post(
                f"{self.domain}/open-apis/drive/v1/files/upload_all",
                headers=await self._headers(),
                data={
                    "file_name": path.name,
                    "parent_type": "explorer",
                    "parent_node": parent_folder_token,
                    "size": str(path.stat().st_size),
                },
                files={"file": (path.name, handle, "application/octet-stream")},
            )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                payload.get("msg")
                or f"Failed to upload Feishu drive file: {json.dumps(payload, ensure_ascii=False)}"
            )
        data = payload.get("data", {})
        return {
            "name": path.name,
            "file_token": data.get("file_token", "") or data.get("token", ""),
            "url": data.get("url", ""),
            "parent_folder_token": parent_folder_token,
        }

    async def wait_for_drive_task(
        self,
        *,
        task_id: str,
        timeout_seconds: float = 20.0,
        poll_interval_seconds: float = 0.5,
    ) -> str:
        client = await self._ensure_http()
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        last_status = ""

        while True:
            response = await client.get(
                f"{self.domain}/open-apis/drive/v1/files/task_check",
                headers=await self._headers(),
                params={"task_id": task_id},
            )
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(
                    payload.get("msg")
                    or f"Failed to check Feishu drive task: {json.dumps(payload, ensure_ascii=False)}"
                )
            status = str(payload.get("data", {}).get("status", "") or "").strip().lower()
            if status:
                last_status = status
            if status in {"success", "failed"}:
                return status
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError(
                    f"Timed out while waiting for Feishu drive task {task_id}. Last status: {last_status or 'unknown'}"
                )
            await asyncio.sleep(poll_interval_seconds)

    async def delete_drive_file(
        self,
        *,
        file_token: str,
        file_type: str = "file",
        wait_timeout_seconds: float = 20.0,
    ) -> dict[str, Any]:
        client = await self._ensure_http()
        response = await client.delete(
            f"{self.domain}/open-apis/drive/v1/files/{file_token}",
            headers=await self._headers(),
            params={"type": file_type},
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                payload.get("msg")
                or f"Failed to delete Feishu drive file: {json.dumps(payload, ensure_ascii=False)}"
            )

        task_id = str(payload.get("data", {}).get("task_id", "") or "").strip()
        status = "success"
        if task_id:
            status = await self.wait_for_drive_task(
                task_id=task_id,
                timeout_seconds=wait_timeout_seconds,
            )
            if status != "success":
                raise RuntimeError(
                    f"Feishu drive deletion task did not succeed: {task_id} ({status})"
                )

        return {
            "file_token": file_token,
            "file_type": file_type,
            "task_id": task_id,
            "status": status,
        }

    async def _create_document(
        self,
        *,
        title: str,
        folder_token: str,
    ) -> dict[str, Any]:
        client = await self._ensure_http()
        body = {
            "title": title,
            "folder_token": folder_token,
        }
        response = await client.post(
            f"{self.domain}/open-apis/docx/v1/documents",
            headers={**(await self._headers()), "Content-Type": "application/json; charset=utf-8"},
            json=body,
        )
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                payload.get("msg")
                or f"Failed to create Feishu docx document: {json.dumps(payload, ensure_ascii=False)}"
            )
        return payload["data"]["document"]

    def _markdown_to_paragraphs(self, markdown_content: str) -> list[str]:
        normalized = markdown_content.replace("\r\n", "\n").replace("\r", "\n")
        lines = normalized.split("\n")
        paragraphs: list[str] = []
        current: list[str] = []

        def flush() -> None:
            if current:
                paragraphs.append(" ".join(part.strip() for part in current if part.strip()))
                current.clear()

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped:
                flush()
                continue
            if re.match(r"^(#{1,6}\s+|[-*]\s+|\d+\.\s+|>\s+)", stripped):
                flush()
                paragraphs.append(stripped)
                continue
            current.append(stripped)
        flush()
        return [paragraph for paragraph in paragraphs if paragraph]

    async def _append_text_blocks(
        self,
        *,
        document_id: str,
        paragraphs: list[str],
        chunk_size: int = 20,
    ) -> int:
        if not paragraphs:
            return 0
        client = await self._ensure_http()
        document_revision_id = -1
        appended = 0

        for start in range(0, len(paragraphs), chunk_size):
            chunk = paragraphs[start : start + chunk_size]
            children = [
                {
                    "block_type": 2,
                    "text": {
                        "elements": [
                            {
                                "text_run": {
                                    "content": paragraph,
                                }
                            }
                        ]
                    },
                }
                for paragraph in chunk
            ]
            response = await client.post(
                (
                    f"{self.domain}/open-apis/docx/v1/documents/{document_id}/blocks/"
                    f"{document_id}/children?document_revision_id={document_revision_id}"
                ),
                headers={**(await self._headers()), "Content-Type": "application/json; charset=utf-8"},
                json={
                    "children": children,
                    "index": -1,
                    "client_token": str(uuid4()),
                },
            )
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(
                    payload.get("msg")
                    or f"Failed to append Feishu docx blocks: {json.dumps(payload, ensure_ascii=False)}"
                )
            data = payload.get("data", {})
            document_revision_id = data.get("document_revision_id", document_revision_id)
            appended += len(chunk)

        return appended

    async def publish_markdown_doc(
        self,
        *,
        title: str,
        markdown_content: str,
        folder_token: str = "",
    ) -> dict[str, Any]:
        effective_folder = folder_token or await self._root_folder_token()
        paragraphs = self._markdown_to_paragraphs(markdown_content)
        created = await self._create_document(title=title, folder_token=effective_folder)
        doc_token = created.get("document_id", "")
        appended_count = await self._append_text_blocks(document_id=doc_token, paragraphs=paragraphs)
        return {
            "title": title,
            "folder_token": effective_folder,
            "document_token": doc_token,
            "url": "",
            "result": {
                "document_id": doc_token,
                "revision_id": created.get("revision_id"),
                "appended_paragraphs": appended_count,
            },
        }


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _extract_json_payload(text: str) -> Any:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\[[\s\S]*\]|\{[\s\S]*\})", cleaned)
        if not match:
            raise
        return json.loads(match.group(1))


async def _generate_candidate_ideas(
    *,
    query: str,
    requirements: list[str],
    notes: list[str],
    evidence_records: list[dict[str, Any]],
    max_ideas: int,
) -> list[dict[str, Any]]:
    cfg = get_effective_config()
    model = get_chat_model(model=cfg.model, provider=cfg.provider)
    evidence_digest = []
    for record in evidence_records[:8]:
        evidence_digest.append(
            {
                "title": record.get("title", ""),
                "url": record.get("url", ""),
                "summary": record.get("summary", ""),
                "claims": record.get("claims", [])[:3],
                "relevance_score": record.get("relevance_score", 0.0),
            }
        )

    prompt = f"""
You are helping generate candidate research paper ideas.

Query:
{query}

Requirements:
{json.dumps(requirements, ensure_ascii=False)}

Notes:
{json.dumps(notes, ensure_ascii=False)}

Evidence:
{json.dumps(evidence_digest, ensure_ascii=False, indent=2)}

Return JSON only. Produce exactly {max_ideas} idea candidates as a JSON array.
Each item must contain:
- title
- idea_description
- motivation
- novelty
- background
- proposed_method
- validation_plan
- risks
- evidence_urls (array of URLs from the evidence)
- research_results (array of short bullet strings grounded in the evidence)

Be concrete, avoid generic fluff, and do not invent citations outside the evidence URLs.
""".strip()

    response = await model.ainvoke(prompt)
    payload = _extract_json_payload(_message_content_text(response.content))
    if not isinstance(payload, list):
        raise ValueError("Idea generation model did not return a JSON list")
    return payload[:max_ideas]


def _render_candidate_ideas_markdown(
    *,
    query: str,
    requirements: list[str],
    notes: list[str],
    candidates: list[dict[str, Any]],
) -> str:
    lines = [
        "# Idea Candidates",
        "",
        f"- Query: {query}",
    ]
    if requirements:
        lines.append(f"- Requirements: {', '.join(requirements)}")
    if notes:
        lines.append(f"- Notes: {', '.join(notes)}")
    lines.append("")

    for idx, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"## Candidate {idx}: {candidate.get('title', f'Idea {idx}')}",
                "",
                "### Idea Description",
                candidate.get("idea_description", "").strip() or "N/A",
                "",
                "### Motivation",
                candidate.get("motivation", "").strip() or "N/A",
                "",
                "### Novelty",
                candidate.get("novelty", "").strip() or "N/A",
                "",
                "### Background",
                candidate.get("background", "").strip() or "N/A",
                "",
                "### Proposed Method",
                candidate.get("proposed_method", "").strip() or "N/A",
                "",
                "### Validation Plan",
                candidate.get("validation_plan", "").strip() or "N/A",
                "",
                "### Risks",
                candidate.get("risks", "").strip() or "N/A",
                "",
                "### Related Evidence And Research Results",
            ]
        )
        for item in candidate.get("research_results", []) or []:
            lines.append(f"- {item}")
        evidence_urls = candidate.get("evidence_urls", []) or []
        if evidence_urls:
            lines.append("")
            lines.append("### Evidence URLs")
            for url in evidence_urls:
                lines.append(f"- {url}")
        lines.append("")
    return "\n".join(lines)


@tool(parse_docstring=True)
def parse_idea_request(request_text: str) -> str:
    """Parse a free-form idea request into structured query and seed inputs.

    Args:
        request_text: User message containing query, requirements, and URLs

    Returns:
        JSON string containing normalized fields
    """
    return json.dumps(parse_idea_request_text(request_text), ensure_ascii=False, indent=2)


@tool(parse_docstring=True)
def build_idea_brief(
    idea_title: str,
    idea_description: str,
    request_text: str = "",
    query: str = "",
    requirements: list[str] | None = None,
    evidence_urls: list[str] | None = None,
    notes: list[str] | None = None,
    max_evidence: int = 6,
    output_dir: str = "",
) -> str:
    """Build a structured idea brief markdown artifact from evidence.jsonl.

    Args:
        idea_title: Human-readable title for the idea
        idea_description: Idea summary, motivation, or hypothesis
        request_text: Optional free-form request in the /idea start format
        query: Optional explicit query; overrides the parsed query when set
        requirements: Optional list of user requirements
        evidence_urls: Optional specific evidence URLs to include
        notes: Optional extra notes
        max_evidence: Maximum number of evidence rows to include
        output_dir: Optional output directory for this brief

    Returns:
        Short summary plus the saved markdown path
    """
    parsed = parse_idea_request_text(request_text) if request_text else {
        "query": "",
        "requirements": [],
        "seed_urls": [],
        "notes": [],
        "raw_text": "",
    }
    final_query = query.strip() or parsed["query"]
    final_requirements = _normalize_list(requirements) or parsed["requirements"]
    final_notes = _normalize_list(notes) or parsed["notes"]
    chosen_urls = _normalize_list(evidence_urls) or parsed["seed_urls"]

    evidence_path = Path.cwd() / "artifacts" / "lit_review" / "evidence.jsonl"
    evidence_records = _load_jsonl(evidence_path) if evidence_path.exists() else []
    selected = _select_evidence(evidence_records, final_query, chosen_urls, max_evidence)

    markdown = _render_idea_brief_markdown(
        title=idea_title,
        query=final_query,
        idea_description=idea_description,
        requirements=final_requirements,
        notes=final_notes,
        evidence_records=selected,
    )

    root = Path(output_dir) if output_dir else _idea_root()
    root.mkdir(parents=True, exist_ok=True)
    brief_path = root / f"{_slugify(idea_title)}.md"
    brief_path.write_text(markdown, encoding="utf-8")

    index_path = root / "index.json"
    index_payload = {
        "title": idea_title,
        "query": final_query,
        "requirements": final_requirements,
        "notes": final_notes,
        "evidence_urls": [record.get("url", "") for record in selected],
        "brief_path": _display_path(brief_path),
    }
    existing = []
    if index_path.exists():
        existing = json.loads(index_path.read_text(encoding="utf-8"))
    existing = [item for item in existing if item.get("title") != idea_title]
    existing.append(index_payload)
    index_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")

    return (
        f"Built idea brief '{idea_title}'.\n"
        f"Saved markdown: {_display_path(brief_path)}\n"
        f"Included evidence rows: {len(selected)}"
    )


@tool(parse_docstring=True)
async def publish_idea_brief_to_feishu_doc(
    markdown_path: str,
    title: str = "",
    folder_token: str = "",
    record_key: str = "",
) -> str:
    """Publish a local idea brief markdown file as a Feishu doc.

    Args:
        markdown_path: Local markdown artifact path
        title: Optional Feishu doc title; defaults to file stem
        folder_token: Optional Feishu folder token; falls back to config or root folder
        record_key: Optional logical key used to track the latest published doc

    Returns:
        Published document metadata summary
    """
    path = Path(markdown_path)
    if not path.exists():
        return f"Markdown file not found: {markdown_path}"

    cfg = get_effective_config()
    if not cfg.feishu_app_id or not cfg.feishu_app_secret:
        return "Feishu credentials are missing. Configure feishu_app_id and feishu_app_secret first."

    doc_title = title.strip() or path.stem
    target_folder = folder_token.strip() or getattr(cfg, "feishu_doc_folder_token", "").strip()
    client = FeishuIdeaDocClient(
        app_id=cfg.feishu_app_id,
        app_secret=cfg.feishu_app_secret,
        domain=cfg.feishu_domain,
    )
    try:
        result = await client.publish_markdown_doc(
            title=doc_title,
            markdown_content=path.read_text(encoding="utf-8"),
            folder_token=target_folder,
        )
    except Exception as exc:
        return f"Failed to publish Feishu doc for {markdown_path}: {exc}"
    finally:
        await client.aclose()

    state = _load_doc_state()
    logical_key = record_key.strip() or hashlib.sha1(path.as_posix().encode("utf-8")).hexdigest()[:12]
    state[logical_key] = {
        "title": doc_title,
        "markdown_path": _display_path(path),
        "document_token": result.get("document_token", ""),
        "url": result.get("url", ""),
        "folder_token": result.get("folder_token", ""),
    }
    _save_doc_state(state)

    return (
        f"Published idea brief to Feishu doc.\n"
        f"Title: {doc_title}\n"
        f"Document token: {result.get('document_token', '')}\n"
        f"URL: {result.get('url', '')}\n"
        f"State key: {logical_key}"
    )


@tool(parse_docstring=True)
async def run_idea_pipeline(
    request_text: str,
    max_sources: int = 4,
    max_ideas: int = 3,
    publish_to_feishu_doc: bool = True,
) -> str:
    """Run the first end-to-end idea discovery pipeline.

    The pipeline parses the request, collects sources, reads and extracts
    evidence, drafts candidate ideas, saves markdown artifacts, and can publish
    the candidates to a Feishu doc.

    Args:
        request_text: User request containing query, requirements, and optional URLs
        max_sources: Maximum number of source URLs to read deeply
        max_ideas: Number of idea candidates to draft
        publish_to_feishu_doc: Whether to publish the candidate markdown to Feishu

    Returns:
        Summary of generated artifacts and, when enabled, the Feishu doc URL
    """
    parsed = parse_idea_request_text(request_text)
    query = parsed["query"]
    requirements = parsed["requirements"]
    notes = parsed["notes"]
    seed_urls = parsed["seed_urls"]
    site_urls = parsed["site_urls"]
    max_sources = int(parsed.get("max_sources", max_sources))
    max_ideas = int(parsed.get("max_ideas", max_ideas))
    run_id, run_dir = _new_run_dir(query)
    logger = IdeaPipelineLogger(query=query, request_text=request_text, run_dir=run_dir)
    logger.add(
        "Parse Request",
        "ok",
        (
            f"Parsed query='{query}', requirements={len(requirements)}, "
            f"notes={len(notes)}, seed_urls={len(seed_urls)}, site_urls={len(site_urls)}, "
            f"max_sources={max_sources}, max_ideas={max_ideas}, run_id={run_id}"
        ),
    )

    crawled_urls: list[str] = []
    if site_urls:
        crawl_summary = await crawl_site_articles.ainvoke(
            {
                "site_urls": site_urls,
                "keywords": requirements or [query],
                "max_articles_per_site": max_sources,
            }
        )
        logger.add("Crawl Site Articles", "ok", crawl_summary)
        crawl_index_path = Path.cwd() / "artifacts" / "lit_review" / "site_crawl_index.json"
        if crawl_index_path.exists():
            crawl_index = json.loads(crawl_index_path.read_text(encoding="utf-8"))
            crawled_urls = [item.get("url", "") for item in crawl_index.get("articles", []) if item.get("url")]

    merged_seed_urls = seed_urls + crawled_urls

    collect_summary = await collect_sources.ainvoke(
        {
            "query": query,
            "seed_urls": merged_seed_urls,
            "max_results": max_sources,
        }
    )
    logger.add("Collect Sources", "ok", collect_summary)

    source_index_path = Path.cwd() / "artifacts" / "lit_review" / "source_index.json"
    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    chosen_sources = source_index.get("sources", [])[:max_sources]
    evidence_urls: list[str] = []
    root = run_dir
    source_index_md_path = root / "source_index.md"
    crawl_report_md_path = root / "site_crawl_report.md"
    shared_crawl_report = Path.cwd() / "artifacts" / "lit_review" / "site_crawl_report.md"
    if shared_crawl_report.exists():
        crawl_report_md_path.write_text(shared_crawl_report.read_text(encoding="utf-8"), encoding="utf-8")
    source_index_md_path.write_text(
        _render_source_index_markdown(query, source_index.get("sources", [])),
        encoding="utf-8",
    )
    logger.add(
        "Select Sources",
        "ok",
        "\n".join(
            f"{idx}. {source.get('title', source.get('url', ''))} - {source.get('url', '')}"
            for idx, source in enumerate(chosen_sources, start=1)
        )
        or "No sources selected.",
    )

    for source in chosen_sources:
        url = source.get("url", "")
        if not url:
            continue
        evidence_urls.append(url)
        read_summary = await read_paper_source.ainvoke(
            {"url": url, "keywords": requirements or [query]}
        )
        logger.add("Read Source", "ok", read_summary)
        claim_summary = await extract_claims.ainvoke(
            {"url": url, "keywords": requirements or [query]}
        )
        logger.add("Extract Claims", "ok", claim_summary)

    evidence_path = Path.cwd() / "artifacts" / "lit_review" / "evidence.jsonl"
    evidence_records = _load_jsonl(evidence_path) if evidence_path.exists() else []
    selected_evidence = _select_evidence(
        evidence_records,
        query=query,
        evidence_urls=evidence_urls,
        max_evidence=max_sources,
    )
    evidence_md_path = root / "evidence_report.md"
    evidence_md_path.write_text(
        _render_evidence_markdown(query, selected_evidence),
        encoding="utf-8",
    )
    logger.add(
        "Select Evidence",
        "ok",
        f"Selected {len(selected_evidence)} evidence record(s) from {len(evidence_records)} stored row(s).",
    )

    candidates = await _generate_candidate_ideas(
        query=query,
        requirements=requirements,
        notes=notes,
        evidence_records=selected_evidence,
        max_ideas=max_ideas,
    )
    logger.add(
        "Generate Candidates",
        "ok",
        "\n".join(
            f"{idx}. {candidate.get('title', f'Idea {idx}')}"
            for idx, candidate in enumerate(candidates, start=1)
        )
        or "No candidates generated.",
    )

    candidates_json_path = root / "idea_candidates.json"
    candidates_md_path = root / "idea_candidates.md"
    candidates_json_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    candidates_md_path.write_text(
        _render_candidate_ideas_markdown(
            query=query,
            requirements=requirements,
            notes=notes,
            candidates=candidates,
        ),
        encoding="utf-8",
    )

    first_candidate = candidates[0] if candidates else {
        "title": "Idea Brief",
        "idea_description": f"Research direction for {query}",
        "evidence_urls": evidence_urls,
    }
    brief_result = build_idea_brief.invoke(
        {
            "idea_title": first_candidate.get("title", "Idea Brief"),
            "idea_description": first_candidate.get(
                "idea_description",
                f"Research direction for {query}",
            ),
            "query": query,
            "requirements": requirements,
            "evidence_urls": first_candidate.get("evidence_urls", evidence_urls),
            "notes": notes,
            "max_evidence": max_sources,
            "output_dir": str(run_dir),
        }
    )
    logger.add("Build First Brief", "ok", brief_result)

    publish_result = ""
    log_publish_result = ""
    if publish_to_feishu_doc:
        publish_result = await publish_idea_brief_to_feishu_doc.ainvoke(
            {
                "markdown_path": str(candidates_md_path),
                "title": f"Idea Candidates - {query[:60]}",
                "record_key": f"idea-candidates-{_slugify(query)[:40]}",
            }
        )
        logger.add("Publish Candidate Doc", "ok", publish_result)
        log_publish_result = await publish_idea_brief_to_feishu_doc.ainvoke(
            {
                "markdown_path": str(logger.latest_path),
                "title": f"Idea Pipeline Log - {query[:60]}",
                "record_key": f"idea-log-{_slugify(query)[:40] or 'idea-run'}",
            }
        )
        logger.add("Publish Log Doc", "ok", log_publish_result)

    run_state = {
        "run_id": run_id,
        "run_dir": _display_path(run_dir),
        "query": query,
        "seed_urls": merged_seed_urls,
        "site_urls": site_urls,
        "max_sources": max_sources,
        "max_ideas": max_ideas,
        "candidates_json_path": _display_path(candidates_json_path),
        "candidates_markdown_path": _display_path(candidates_md_path),
        "source_index_markdown_path": _display_path(source_index_md_path),
        "crawl_report_markdown_path": _display_path(crawl_report_md_path) if crawl_report_md_path.exists() else "",
        "evidence_markdown_path": _display_path(evidence_md_path),
        "log_path": _display_path(logger.path),
        "latest_log_path": _display_path(logger.latest_path),
        "brief_result": brief_result,
        "publish_result": publish_result,
        "log_publish_result": log_publish_result,
    }
    _save_last_run_state(run_state)
    _append_run_index(
        {
            "run_id": run_id,
            "query": query,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "run_dir": _display_path(run_dir),
            "candidates_json_path": _display_path(candidates_json_path),
            "log_path": _display_path(logger.path),
        }
    )

    lit_root = Path.cwd() / "artifacts" / "lit_review"
    sources_dir = lit_root / "sources"
    if sources_dir.exists():
        for child in sources_dir.iterdir():
            if child.is_file():
                try:
                    child.unlink()
                except OSError:
                    pass

    candidate_lines = [
        f"{idx}. {candidate.get('title', f'Idea {idx}')}"
        for idx, candidate in enumerate(candidates, start=1)
    ]
    response_lines = [
        f"Finished idea pipeline for query: {query}",
        f"Run ID: {run_id}",
        f"Parsed seed URLs: {len(seed_urls)}",
        f"Deep-read sources: {len(chosen_sources)}",
        f"Source index markdown: {_display_path(source_index_md_path)}",
        f"Site crawl report: {_display_path(crawl_report_md_path) if crawl_report_md_path.exists() else 'N/A'}",
        f"Evidence markdown: {_display_path(evidence_md_path)}",
        f"Candidate markdown: {_display_path(candidates_md_path)}",
        f"Candidate json: {_display_path(candidates_json_path)}",
        f"Pipeline log: {_display_path(logger.latest_path)}",
        brief_result,
        "Candidates:",
        *candidate_lines,
    ]
    if publish_result:
        response_lines.extend(["", publish_result])
    if log_publish_result:
        response_lines.extend(["", log_publish_result])
    return "\n".join(line for line in response_lines if line)


__all__ = [
    "FeishuIdeaDocClient",
    "build_idea_brief",
    "parse_idea_request",
    "parse_idea_request_text",
    "publish_idea_brief_to_feishu_doc",
    "run_idea_pipeline",
]
