"""Feishu document helpers for command usage guides."""

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

DEFAULT_IDEA_DIR = Path("artifacts") / "ideas"
DEFAULT_DOC_STATE = DEFAULT_IDEA_DIR / "feishu_docs.json"
DEFAULT_USAGE_GUIDE_DIR = Path("artifacts") / "usage"
DEFAULT_USAGE_GUIDE_MARKDOWN = DEFAULT_USAGE_GUIDE_DIR / "command_usage.md"


def _idea_root() -> Path:
    root = Path.cwd() / DEFAULT_IDEA_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _usage_guide_root() -> Path:
    root = Path.cwd() / DEFAULT_USAGE_GUIDE_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _display_path(path: Path | str) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        return candidate.as_posix()


def parse_update_request_text(text: str) -> dict[str, str]:
    """Parse a `/update` request into folder-token and title fields."""
    lines = [line.rstrip() for line in text.splitlines()]
    data = {
        "folder_token": "",
        "title": "牢大使用说明",
    }
    current_key: str | None = None
    key_map = {
        "folder_token": "folder_token",
        "token": "folder_token",
        "title": "title",
        "标题": "title",
    }

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            current_key = None
            continue
        if line.lower().startswith("/update"):
            remainder = line[7:].strip()
            if remainder:
                data["folder_token"] = remainder
            continue

        key_match = re.match(r"^([^:：]+)\s*[:：]\s*(.*)$", line)
        if key_match:
            raw_key = key_match.group(1).strip().lower()
            mapped_key = key_map.get(raw_key)
            if mapped_key is None:
                current_key = None
                continue
            current_key = mapped_key
            value = key_match.group(2).strip()
            if value:
                data[mapped_key] = value
            continue

        if current_key in ("folder_token", "title"):
            data[current_key] = line

    return {
        "folder_token": str(data["folder_token"]).strip(),
        "title": str(data["title"]).strip() or "牢大使用说明",
        "raw_text": text.strip(),
    }


def _hard_route_usage_specs() -> list[dict[str, Any]]:
    return [
        {
            "command": "/search",
            "summary": "抓取论文来源、整理结果并上传到飞书 `papers/<调用时间>` 文件夹。",
            "usage": [
                "/search",
                "query: agent benchmark",
                "keywords:",
                "- multi-agent",
                "- benchmark",
                "date_from: 2023-01-01",
                "date_to: 2025-12-31",
                "sort: relevance",
                "max_papers: 3",
                "max_results: 8",
                "site_urls:",
                "- https://arxiv.org/list/cs.AI/recent",
                "seed_urls:",
                "- https://arxiv.org/abs/2308.08155",
                "max_depth: 1",
                "max_pages_per_site: 5",
                "max_articles_per_site: 20",
            ],
            "parameters": [
                {
                    "name": "query",
                    "required": True,
                    "format": "单行文本",
                    "meaning": "检索主题或论文问题描述。",
                },
                {
                    "name": "keywords",
                    "required": False,
                    "format": "列表；支持多行 `- item`",
                    "meaning": "显式关键词；未提供时会基于 query 自动生成。",
                },
                {
                    "name": "seed_urls",
                    "required": False,
                    "format": "列表 URL",
                    "meaning": "显式给定的论文或网页种子链接。",
                },
                {
                    "name": "site_urls",
                    "required": False,
                    "format": "列表 URL",
                    "meaning": "站点递归起点，用于额外发现候选文章。",
                },
                {
                    "name": "date_from / date_to",
                    "required": False,
                    "format": "`YYYY-MM-DD`",
                    "meaning": "论文发表时间范围筛选。",
                },
                {
                    "name": "sort",
                    "required": False,
                    "format": "`relevance | newest | oldest | title`",
                    "meaning": "最终结果排序方式。",
                },
                {
                    "name": "max_papers",
                    "required": False,
                    "format": "整数，1-20",
                    "meaning": "最终保留并上传的论文数量上限。",
                },
                {
                    "name": "max_results",
                    "required": False,
                    "format": "整数，1-30",
                    "meaning": "候选来源池大小；通常应大于等于 max_papers。",
                },
                {
                    "name": "max_depth",
                    "required": False,
                    "format": "整数，0-3",
                    "meaning": "每个站点的递归深度上限。",
                },
                {
                    "name": "max_pages_per_site",
                    "required": False,
                    "format": "整数，1-20",
                    "meaning": "每个站点最多翻页数量。",
                },
                {
                    "name": "max_articles_per_site",
                    "required": False,
                    "format": "整数，1-50",
                    "meaning": "每个站点最多保留的文章数。",
                },
                {
                    "name": "notes",
                    "required": False,
                    "format": "列表或单行文本",
                    "meaning": "附加说明字段，目前主要用于保留备注。",
                },
            ],
            "notes": [
                "本地只记录一次元数据，不长期保存整批抓取文件。",
                "未知字段会被直接忽略，不会自动并入 query。",
            ],
        },
        {
            "command": "/delete",
            "summary": "删除一次 `/search` 的本地元数据，并删除对应的飞书文件夹。",
            "usage": [
                "/delete 20260404-123456",
            ],
            "parameters": [
                {
                    "name": "时间选择器",
                    "required": True,
                    "format": "完整时间或前缀，例如 `20260404-123456`",
                    "meaning": "匹配一次 `/search` 调用记录。",
                },
            ],
            "notes": [
                "如果命中多条记录，机器人会要求给出更具体的时间。",
                "删除远端文件夹前需要飞书凭据仍然有效。",
            ],
        },
        {
            "command": "/update",
            "summary": "在指定 folder token 下刷新当前这份使用说明文档。",
            "usage": [
                "/update fldcnxxxxxxxxxxxx",
                "/update",
                "folder_token: fldcnxxxxxxxxxxxx",
                "title: 牢大使用说明",
            ],
            "parameters": [
                {
                    "name": "folder_token / token",
                    "required": True,
                    "format": "飞书 folder token",
                    "meaning": "说明文档要写入的目标文件夹。",
                },
                {
                    "name": "title",
                    "required": False,
                    "format": "单行文本",
                    "meaning": "说明文档标题；默认是 `牢大使用说明`。",
                },
            ],
            "notes": [
                "重复调用会刷新同一个逻辑记录，并尝试删除旧版说明文档。",
                "如果没有显式提供 folder token，会退回配置里的 `feishu_doc_folder_token`。",
            ],
        },
    ]


def _render_command_usage_markdown(*, title: str, folder_token: str) -> str:
    lines = [
        f"# {title}",
        "",
        "- 机器人名称: 牢大",
        f"- 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 目标 Folder Token: {folder_token}",
        "- 维护方式: 本文档由 `/update` 命令自动刷新。",
        "",
        "## 当前硬路由命令总览",
    ]
    specs = _hard_route_usage_specs()
    for spec in specs:
        lines.append(f"- `{spec['command']}`: {spec['summary']}")

    for spec in specs:
        lines.extend(
            [
                "",
                f"## {spec['command']}",
                f"- 功能: {spec['summary']}",
                "",
                "### 触发格式",
            ]
        )
        for item in spec["usage"]:
            lines.append(f"- `{item}`")
        lines.extend(["", "### 参数说明"])
        for param in spec["parameters"]:
            required_text = "必填" if param["required"] else "可选"
            lines.append(
                f"- `{param['name']}`: {required_text}；格式 {param['format']}；{param['meaning']}"
            )
        if spec.get("notes"):
            lines.extend(["", "### 补充说明"])
            for note in spec["notes"]:
                lines.append(f"- {note}")
    return "\n".join(lines).rstrip() + "\n"


def _command_usage_record_key(folder_token: str) -> str:
    return f"command-usage-{hashlib.sha1(folder_token.encode('utf-8')).hexdigest()[:12]}"


def _write_command_usage_markdown(*, title: str, folder_token: str) -> Path:
    path = _usage_guide_root() / DEFAULT_USAGE_GUIDE_MARKDOWN.name
    path.write_text(
        _render_command_usage_markdown(title=title, folder_token=folder_token),
        encoding="utf-8",
    )
    return path


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


@tool(parse_docstring=True)
async def update_command_usage_guide(request_text: str) -> str:
    """Refresh the hard-route usage guide under a target Feishu folder.

    Args:
        request_text: User message containing `/update`, `folder_token`, and optional `title`

    Returns:
        Short update summary including the local markdown path and doc metadata
    """
    parsed = parse_update_request_text(request_text)
    cfg = get_effective_config()
    target_folder = parsed["folder_token"] or getattr(cfg, "feishu_doc_folder_token", "").strip()
    if not target_folder:
        return (
            "牢大还需要一个 folder token。\n"
            "用法：/update fldcnxxxxxxxxxxxx\n"
            "或\n"
            "/update\n"
            "folder_token: fldcnxxxxxxxxxxxx"
        )
    if not cfg.feishu_app_id or not cfg.feishu_app_secret:
        return (
            "牢大还缺少飞书凭据。\n"
            "请先配置 feishu_app_id 和 feishu_app_secret。"
        )

    doc_title = parsed["title"] or "牢大使用说明"
    markdown_path = _write_command_usage_markdown(title=doc_title, folder_token=target_folder)
    logical_key = _command_usage_record_key(target_folder)
    state = _load_doc_state()
    previous = state.get(logical_key, {}) if isinstance(state.get(logical_key), dict) else {}
    previous_token = str(previous.get("document_token", "") or "").strip()
    delete_warning = ""

    client = FeishuIdeaDocClient(
        app_id=cfg.feishu_app_id,
        app_secret=cfg.feishu_app_secret,
        domain=cfg.feishu_domain,
    )
    try:
        if previous_token:
            try:
                await client.delete_drive_file(file_token=previous_token, file_type="docx")
            except Exception as exc:
                delete_warning = str(exc)
        result = await client.publish_markdown_doc(
            title=doc_title,
            markdown_content=markdown_path.read_text(encoding="utf-8"),
            folder_token=target_folder,
        )
    except Exception as exc:
        return (
            "牢大更新使用说明文档失败。\n"
            f"原因: {exc}\n"
            f"本地 Markdown: {_display_path(markdown_path)}"
        )
    finally:
        await client.aclose()

    state[logical_key] = {
        "kind": "command_usage_guide",
        "title": doc_title,
        "markdown_path": _display_path(markdown_path),
        "document_token": result.get("document_token", ""),
        "url": result.get("url", ""),
        "folder_token": result.get("folder_token", "") or target_folder,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_doc_state(state)

    response_lines = [
        "牢大已更新使用说明文档。",
        f"标题: {doc_title}",
        f"目标 Folder Token: {target_folder}",
        f"本地 Markdown: {_display_path(markdown_path)}",
        f"Document token: {result.get('document_token', '')}",
    ]
    if result.get("url"):
        response_lines.append(f"URL: {result.get('url', '')}")
    if delete_warning:
        response_lines.append(f"旧版文档删除告警: {delete_warning}")
    response_lines.append("已写入命令: /search, /delete, /update")
    return "\n".join(response_lines)


__all__ = [
    "FeishuIdeaDocClient",
    "parse_update_request_text",
    "update_command_usage_guide",
]
