"""Paper search workflow helpers for Feishu-triggered literature collection."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import tool

from ..config import get_effective_config
from .idea import FeishuIdeaDocClient
from .search import (
    _build_summary,
    _extract_claims_from_text,
    _fetch_source_content,
    _infer_source_type,
    _normalize_keywords,
    _normalize_urls,
    _score_relevance,
    _slugify,
    collect_sources,
    crawl_site_articles,
)

DEFAULT_PAPER_DIR = Path("artifacts") / "paper_search"
DEFAULT_PAPER_METADATA_PATH = DEFAULT_PAPER_DIR / "invocations.jsonl"


def _paper_root() -> Path:
    root = Path.cwd() / DEFAULT_PAPER_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root


def _display_path(path: Path | str) -> str:
    candidate = Path(path)
    try:
        return candidate.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except Exception:
        return candidate.as_posix()


def _new_run_id(query: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = _slugify(query or "paper-search")
    return f"{timestamp}-{slug}"


def _metadata_log_path() -> Path:
    root = _paper_root()
    return root / DEFAULT_PAPER_METADATA_PATH.name


def _append_invocation_metadata(payload: dict[str, Any]) -> None:
    path = _metadata_log_path()
    line = json.dumps(payload, ensure_ascii=False)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _load_invocation_metadata() -> list[dict[str, Any]]:
    path = _metadata_log_path()
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _save_invocation_metadata(rows: list[dict[str, Any]]) -> None:
    path = _metadata_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = [
        json.dumps(row, ensure_ascii=False)
        for row in rows
        if isinstance(row, dict)
    ]
    content = "\n".join(rendered)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


@contextmanager
def _temporary_workdir(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _normalize_time_selector(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits[:14]


def _run_timestamp_prefix(value: str) -> str:
    digits = _normalize_time_selector(value)
    if len(digits) <= 8:
        return digits
    return f"{digits[:8]}-{digits[8:]}"


def _entry_time_values(entry: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("run_id", "feishu_folder_name", "called_at"):
        candidate = str(entry.get(key, "") or "").strip()
        if candidate:
            values.append(candidate)
    return values


def _match_invocation_entries(
    entries: list[dict[str, Any]],
    selector: str,
) -> list[tuple[int, dict[str, Any]]]:
    selector_raw = selector.strip()
    selector_norm = _normalize_time_selector(selector_raw)
    matches: list[tuple[int, dict[str, Any]]] = []

    for idx, entry in enumerate(entries):
        matched = False
        for candidate in _entry_time_values(entry):
            if selector_raw and (
                candidate == selector_raw
                or candidate.startswith(selector_raw)
            ):
                matched = True
                break

            candidate_norm = _normalize_time_selector(candidate)
            if selector_norm and candidate_norm.startswith(selector_norm):
                matched = True
                break

        if matched:
            matches.append((idx, entry))

    return matches


def _render_invocation_ref(entry: dict[str, Any]) -> str:
    called_at = str(entry.get("called_at", "") or "unknown-time").strip()
    run_id = str(entry.get("run_id", "") or "").strip()
    query = str(entry.get("query", "") or "N/A").strip()
    if run_id:
        return f"{called_at} | {run_id} | {query}"
    return f"{called_at} | {query}"


def parse_delete_request_text(text: str) -> dict[str, str]:
    """Parse a `/delete` request into a normalized selector."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    selector = ""
    if lines:
        first = lines[0]
        if first.lower().startswith("/delete"):
            selector = first[len("/delete") :].strip()
            if not selector and len(lines) > 1:
                selector = lines[1]
        else:
            selector = first

    if not selector:
        raise ValueError("/delete requires a time selector.")

    return {
        "selector": selector,
        "normalized_selector": _normalize_time_selector(selector),
    }


def _safe_int(value: str, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _normalize_text_list(value: str | list[str] | None) -> list[str]:
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


def parse_search_request_text(text: str) -> dict[str, Any]:
    """Parse a `/search` request into structured paper-search parameters."""
    lines = [line.rstrip() for line in text.splitlines()]
    data: dict[str, list[str] | str] = {
        "query": "",
        "keywords": [],
        "seed_urls": [],
        "site_urls": [],
        "date_from": "",
        "date_to": "",
        "sort": "relevance",
        "max_papers": "5",
        "max_results": "8",
        "max_depth": "1",
        "max_pages_per_site": "5",
        "max_articles_per_site": "20",
        "notes": [],
    }
    current_key: str | None = None
    key_map = {
        "query": "query",
        "关键词": "keywords",
        "keyword": "keywords",
        "keywords": "keywords",
        "种子网址": "seed_urls",
        "seed_urls": "seed_urls",
        "seed_url": "seed_urls",
        "seeds": "seed_urls",
        "urls": "seed_urls",
        "url": "seed_urls",
        "站点": "site_urls",
        "站点网址": "site_urls",
        "site_urls": "site_urls",
        "site_url": "site_urls",
        "sites": "site_urls",
        "开始时间": "date_from",
        "date_from": "date_from",
        "published_after": "date_from",
        "结束时间": "date_to",
        "date_to": "date_to",
        "published_before": "date_to",
        "排序": "sort",
        "sort": "sort",
        "order": "sort",
        "数量": "max_papers",
        "max_papers": "max_papers",
        "limit": "max_papers",
        "max_results": "max_results",
        "max_depth": "max_depth",
        "max_pages_per_site": "max_pages_per_site",
        "max_articles_per_site": "max_articles_per_site",
        "notes": "notes",
        "备注": "notes",
    }

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            current_key = None
            continue
        if line.lower().startswith("/search"):
            remainder = line[7:].strip()
            if remainder and not data["query"]:
                data["query"] = remainder
            continue

        key_match = re.match(r"^([^:：]+)\s*[:：]\s*(.*)$", line)
        if key_match:
            raw_key = key_match.group(1).strip()
            if raw_key in key_map:
                mapped_key = key_map[raw_key]
                current_key = mapped_key
                value = key_match.group(2).strip()
                if value:
                    if mapped_key == "query":
                        data["query"] = value
                    elif mapped_key in (
                        "date_from",
                        "date_to",
                        "sort",
                        "max_papers",
                        "max_results",
                        "max_depth",
                        "max_pages_per_site",
                        "max_articles_per_site",
                    ):
                        data[mapped_key] = value
                    elif mapped_key in ("seed_urls", "site_urls"):
                        cast_list = data[mapped_key]
                        assert isinstance(cast_list, list)
                        cast_list.extend(_extract_urls(value) or [value])
                    elif mapped_key == "keywords":
                        cast_list = data[mapped_key]
                        assert isinstance(cast_list, list)
                        cast_list.extend(_normalize_keywords(value))
                    else:
                        cast_list = data[mapped_key]
                        assert isinstance(cast_list, list)
                        cast_list.extend(_normalize_text_list(value))
                continue

        if line.startswith("- ") or line.startswith("* "):
            item = line[2:].strip()
            if current_key in ("seed_urls", "site_urls"):
                cast_list = data[current_key]
                assert isinstance(cast_list, list)
                cast_list.extend(_extract_urls(item) or [item])
            elif current_key == "keywords":
                cast_list = data[current_key]
                assert isinstance(cast_list, list)
                cast_list.extend(_normalize_keywords(item))
            elif current_key in ("notes",):
                cast_list = data[current_key]
                assert isinstance(cast_list, list)
                cast_list.append(item)
            elif current_key == "query":
                data["query"] = f"{data['query']} {item}".strip()
            elif current_key is not None:
                data[current_key] = item
            continue

        if current_key in ("seed_urls", "site_urls"):
            cast_list = data[current_key]
            assert isinstance(cast_list, list)
            cast_list.extend(_extract_urls(line) or [line])
        elif current_key == "keywords":
            cast_list = data[current_key]
            assert isinstance(cast_list, list)
            cast_list.extend(_normalize_keywords(line))
        elif current_key in ("notes",):
            cast_list = data[current_key]
            assert isinstance(cast_list, list)
            cast_list.extend(_normalize_text_list(line))
        elif current_key == "query":
            data["query"] = f"{data['query']} {line}".strip()
        elif current_key is not None:
            data[current_key] = line
        elif not data["query"]:
            data["query"] = line
        else:
            cast_list = data["notes"]
            assert isinstance(cast_list, list)
            cast_list.append(line)

    if not data["query"]:
        non_url_text = re.sub(r"https?://[^\s<>\]\)]+", " ", text)
        non_url_text = re.sub(r"\s+", " ", non_url_text).strip()
        non_url_text = re.sub(r"^/search\s*", "", non_url_text, flags=re.IGNORECASE).strip()
        data["query"] = non_url_text

    sort_value = str(data["sort"]).strip().lower()
    if sort_value not in {"relevance", "newest", "oldest", "title"}:
        sort_value = "relevance"

    merged_seed_urls = list(data["seed_urls"])
    if not merged_seed_urls:
        merged_seed_urls = [
            url for url in _extract_urls(text) if url not in set(_normalize_urls(data["site_urls"]))
        ]
    keyword_list = _normalize_keywords(list(data["keywords"]) or str(data["query"]))

    return {
        "query": str(data["query"]).strip(),
        "keywords": keyword_list,
        "seed_urls": _normalize_urls(merged_seed_urls),
        "site_urls": _normalize_urls(data["site_urls"]),
        "date_from": str(data["date_from"]).strip(),
        "date_to": str(data["date_to"]).strip(),
        "sort": sort_value,
        "max_papers": max(1, min(_safe_int(str(data["max_papers"]), 5), 20)),
        "max_results": max(1, min(_safe_int(str(data["max_results"]), 8), 30)),
        "max_depth": max(0, min(_safe_int(str(data["max_depth"]), 1), 3)),
        "max_pages_per_site": max(1, min(_safe_int(str(data["max_pages_per_site"]), 5), 20)),
        "max_articles_per_site": max(1, min(_safe_int(str(data["max_articles_per_site"]), 20), 50)),
        "notes": _normalize_text_list(data["notes"]),
        "raw_text": text.strip(),
    }


def _merge_discovered_sources(
    *,
    source_index: dict[str, Any],
    crawl_index: dict[str, Any],
) -> list[dict[str, Any]]:
    crawl_by_url = {
        str(item.get("url", "")).strip(): item
        for item in crawl_index.get("articles", []) or []
        if str(item.get("url", "")).strip()
    }
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    next_rank = 1

    for item in source_index.get("sources", []) or []:
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        merged = dict(item)
        crawl_match = crawl_by_url.get(url)
        if crawl_match:
            if crawl_match.get("title"):
                merged["title"] = crawl_match["title"]
            if crawl_match.get("relevance_score") is not None:
                merged["relevance_score"] = crawl_match["relevance_score"]
        merged["rank"] = int(merged.get("rank", next_rank) or next_rank)
        records.append(merged)
        next_rank = max(next_rank, merged["rank"] + 1)

    for url, crawl_match in crawl_by_url.items():
        if url in seen:
            continue
        seen.add(url)
        records.append(
            {
                "rank": next_rank,
                "title": crawl_match.get("title") or Path(urlparse(url).path).stem or url,
                "url": url,
                "snippet": "",
                "source_type": crawl_match.get("source_type") or _infer_source_type(url),
                "relevance_score": crawl_match.get("relevance_score", 0.0),
            }
        )
        next_rank += 1

    return records


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _matches_date_range(record: dict[str, Any], *, date_from: str, date_to: str) -> bool:
    published_at = str(record.get("published_at", "") or "").strip()
    if not published_at:
        return True
    published_dt = _parse_date(published_at)
    if published_dt is None:
        return True
    start_dt = _parse_date(date_from)
    end_dt = _parse_date(date_to)
    if start_dt and published_dt < start_dt:
        return False
    if end_dt and published_dt > end_dt:
        return False
    return True


def _sort_papers(records: list[dict[str, Any]], sort_mode: str) -> list[dict[str, Any]]:
    if sort_mode == "title":
        return sorted(records, key=lambda item: str(item.get("title", "")).lower())
    if sort_mode == "newest":
        return sorted(
            records,
            key=lambda item: (
                bool(item.get("published_at")),
                str(item.get("published_at", "")),
                float(item.get("relevance_score", 0.0)),
            ),
            reverse=True,
        )
    if sort_mode == "oldest":
        return sorted(
            records,
            key=lambda item: (
                not bool(item.get("published_at")),
                str(item.get("published_at", "9999-12-31")),
                -float(item.get("relevance_score", 0.0)),
            ),
        )
    return sorted(
        records,
        key=lambda item: (
            float(item.get("relevance_score", 0.0)),
            -int(item.get("rank", 9999) or 9999),
        ),
        reverse=True,
    )


def _artifact_basename(title: str, url: str) -> str:
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"{_slugify(title or url)}-{url_hash}"


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _write_bytes(path: Path, content: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


async def _fetch_paper_record(
    candidate: dict[str, Any],
    *,
    run_dir: Path,
    keywords: list[str],
) -> dict[str, Any]:
    source = await _fetch_source_content(str(candidate.get("url", "")).strip())
    final_url = str(source.get("url", "") or candidate.get("url", "")).strip()
    source_type = str(source.get("source_type") or candidate.get("source_type") or _infer_source_type(final_url))
    title = str(candidate.get("title") or source.get("title") or final_url).strip()
    if not title or title == final_url:
        title = str(source.get("title") or Path(urlparse(final_url).path).stem or final_url)

    basename = _artifact_basename(title, final_url)
    content = str(source.get("content", "") or "")
    raw_dir = run_dir / "raw"
    extracted_dir = run_dir / "extracted"

    raw_path: Path | None = None
    if source_type == "pdf" and source.get("raw_bytes"):
        raw_path = _write_bytes(raw_dir / f"{basename}.pdf", source["raw_bytes"])
    elif source.get("raw_html"):
        raw_path = _write_text(raw_dir / f"{basename}.html", str(source["raw_html"]))

    extracted_path: Path | None = None
    if content:
        suffix = ".txt" if source_type == "pdf" else ".md"
        extracted_path = _write_text(extracted_dir / f"{basename}{suffix}", content)

    relevance_score = max(
        float(candidate.get("relevance_score", 0.0) or 0.0),
        _score_relevance(
            "\n".join(
                [
                    title,
                    content[:4000],
                    str(candidate.get("snippet", "")),
                ]
            ),
            keywords,
        ),
    )

    return {
        "rank": int(candidate.get("rank", 9999) or 9999),
        "title": title,
        "url": final_url,
        "source_type": source_type,
        "summary": _build_summary(content),
        "claims": _extract_claims_from_text(content, max_claims=3),
        "relevance_score": round(relevance_score, 3),
        "published_at": source.get("published_at"),
        "warning": source.get("warning"),
        "raw_path": _display_path(raw_path) if raw_path else "",
        "extracted_path": _display_path(extracted_path) if extracted_path else "",
    }


def _render_search_summary_markdown(
    *,
    run_id: str,
    query: str,
    parsed: dict[str, Any],
    selected_papers: list[dict[str, Any]],
    failed_urls: list[str],
) -> str:
    lines = [
        "# Paper Search Summary",
        "",
        f"- Run ID: {run_id}",
        f"- Query: {query or 'N/A'}",
        f"- Keywords: {', '.join(parsed['keywords']) if parsed['keywords'] else 'N/A'}",
        f"- Sort: {parsed['sort']}",
        f"- Max Papers: {parsed['max_papers']}",
        f"- Date Range: {parsed['date_from'] or 'open'} -> {parsed['date_to'] or 'open'}",
        "",
        "## Selected Papers",
    ]
    if not selected_papers:
        lines.append("- No papers matched the request.")
    else:
        for idx, paper in enumerate(selected_papers, start=1):
            lines.extend(
                [
                    f"### {idx}. {paper.get('title', 'Untitled')}",
                    f"- URL: {paper.get('url', '')}",
                    f"- Published At: {paper.get('published_at') or 'unknown'}",
                    f"- Source Type: {paper.get('source_type', 'unknown')}",
                    f"- Relevance Score: {paper.get('relevance_score', 0.0)}",
                    f"- Raw Artifact: {paper.get('raw_path') or 'N/A'}",
                    f"- Extracted Artifact: {paper.get('extracted_path') or 'N/A'}",
                    f"- Summary: {paper.get('summary') or 'N/A'}",
                    "",
                ]
            )
    if failed_urls:
        lines.extend(["## Failed URLs", *[f"- {url}" for url in failed_urls], ""])
    return "\n".join(lines).rstrip() + "\n"


@tool(parse_docstring=True)
def parse_search_request(request_text: str) -> str:
    """Parse a free-form `/search` request into structured search fields.

    Args:
        request_text: User message containing `/search` parameters

    Returns:
        JSON string containing normalized fields
    """
    return json.dumps(parse_search_request_text(request_text), ensure_ascii=False, indent=2)


@tool(parse_docstring=True)
async def run_paper_search(request_text: str) -> str:
    """Run a Feishu-oriented paper collection workflow from a `/search` request.

    Args:
        request_text: User message containing `/search` and its parameters

    Returns:
        Short task summary with folder information and paper titles
    """
    parsed = parse_search_request_text(request_text)
    query = parsed["query"]
    run_id = _new_run_id(query or "paper-search")
    called_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cfg = get_effective_config()
    if cfg.tavily_api_key and not os.environ.get("TAVILY_API_KEY", "").strip():
        os.environ["TAVILY_API_KEY"] = cfg.tavily_api_key

    selected_papers: list[dict[str, Any]] = []
    failed_urls: list[str] = []
    folder_url = ""
    folder_token = ""
    folder_name = ""
    uploaded_count = 0
    upload_error = ""
    failure_reason = ""

    try:
        with tempfile.TemporaryDirectory(prefix=f"evosci-paper-search-{run_id}-") as tmpdir:
            run_dir = Path(tmpdir)
            with _temporary_workdir(run_dir):
                request_path = _write_text(run_dir / "request.txt", request_text.strip() + "\n")

                crawl_index: dict[str, Any] = {"articles": []}
                if parsed["site_urls"]:
                    await crawl_site_articles.ainvoke(
                        {
                            "site_urls": parsed["site_urls"],
                            "keywords": parsed["keywords"] or ([query] if query else []),
                            "max_articles_per_site": parsed["max_articles_per_site"],
                            "max_depth": parsed["max_depth"],
                            "max_pages_per_site": parsed["max_pages_per_site"],
                        }
                    )
                    crawl_index_path = run_dir / "artifacts" / "lit_review" / "site_crawl_index.json"
                    if crawl_index_path.exists():
                        crawl_index = json.loads(crawl_index_path.read_text(encoding="utf-8"))

                await collect_sources.ainvoke(
                    {
                        "query": query,
                        "seed_urls": parsed["seed_urls"] + [
                            item.get("url", "")
                            for item in crawl_index.get("articles", []) or []
                            if item.get("url")
                        ],
                        "max_results": parsed["max_results"],
                    }
                )
                source_index_path = run_dir / "artifacts" / "lit_review" / "source_index.json"
                source_index = (
                    json.loads(source_index_path.read_text(encoding="utf-8"))
                    if source_index_path.exists()
                    else {"sources": []}
                )
                candidates = _merge_discovered_sources(
                    source_index=source_index,
                    crawl_index=crawl_index,
                )

                probe_limit = min(max(parsed["max_papers"] * 3, parsed["max_results"]), 30)
                for candidate in candidates[:probe_limit]:
                    try:
                        selected = await _fetch_paper_record(
                            candidate,
                            run_dir=run_dir,
                            keywords=parsed["keywords"],
                        )
                        selected_papers.append(selected)
                    except Exception:
                        failed_urls.append(str(candidate.get("url", "")).strip())

                filtered_records = [
                    record
                    for record in selected_papers
                    if _matches_date_range(
                        record,
                        date_from=parsed["date_from"],
                        date_to=parsed["date_to"],
                    )
                ]
                selected_papers = _sort_papers(filtered_records, parsed["sort"])[: parsed["max_papers"]]

                summary_markdown = _render_search_summary_markdown(
                    run_id=run_id,
                    query=query,
                    parsed=parsed,
                    selected_papers=selected_papers,
                    failed_urls=failed_urls,
                )
                summary_path = _write_text(run_dir / "summary.md", summary_markdown)
                manifest_path = _write_text(
                    run_dir / "papers.json",
                    json.dumps(
                        {
                            "run_id": run_id,
                            "papers": selected_papers,
                            "failed_urls": failed_urls,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                )

                if cfg.feishu_app_id and cfg.feishu_app_secret:
                    client = FeishuIdeaDocClient(
                        app_id=cfg.feishu_app_id,
                        app_secret=cfg.feishu_app_secret,
                        domain=cfg.feishu_domain,
                    )
                    try:
                        root_token = cfg.feishu_doc_folder_token.strip() or await client._root_folder_token()
                        papers_folder = await client.ensure_child_folder(
                            parent_folder_token=root_token,
                            name="papers",
                        )
                        run_folder = await client.create_folder(
                            parent_folder_token=papers_folder["token"],
                            name=run_id,
                        )
                        folder_token = str(run_folder.get("token", "") or "")
                        folder_name = str(run_folder.get("name", "") or run_id)
                        folder_url = run_folder.get("url", "")

                        upload_targets = [summary_path, manifest_path, request_path]
                        for paper in selected_papers:
                            raw_path = str(paper.get("raw_path", "")).strip()
                            extracted_path = str(paper.get("extracted_path", "")).strip()
                            if raw_path:
                                upload_targets.append(run_dir / raw_path)
                            elif extracted_path:
                                upload_targets.append(run_dir / extracted_path)

                        for target in upload_targets:
                            await client.upload_drive_file(
                                file_path=str(target),
                                parent_folder_token=run_folder["token"],
                            )
                            uploaded_count += 1
                    except Exception as exc:
                        upload_error = str(exc)
                    finally:
                        await client.aclose()
                else:
                    upload_error = "Feishu credentials are missing."
    except Exception as exc:
        failure_reason = str(exc)

    completed = not failure_reason and not upload_error
    _append_invocation_metadata(
        {
            "called_at": called_at,
            "command": request_text.strip(),
            "query": query,
            "completed": completed,
            "status": "completed" if completed else "failed",
            "run_id": run_id,
            "paper_count": len(selected_papers),
            "uploaded_count": uploaded_count,
            "feishu_folder_token": folder_token,
            "feishu_folder_name": folder_name,
            "feishu_folder_url": folder_url,
            "error": upload_error or failure_reason,
        }
    )

    if failure_reason:
        return "\n".join(
            [
                "牢大执行 /search 失败。",
                f"查询: {query or 'N/A'}",
                f"错误: {failure_reason}",
            ]
        )

    response_lines = [
        "牢大已完成论文抓取任务。" if completed else "牢大已完成论文抓取，但结果未完全成功。",
        f"查询: {query or 'N/A'}",
        f"论文数量: {len(selected_papers)}",
        "本地仅记录元数据: artifacts/paper_search/invocations.jsonl",
    ]
    if folder_url:
        response_lines.append(f"飞书文件夹: {folder_url}")
    if uploaded_count:
        response_lines.append(f"已上传文件数: {uploaded_count}")
    if upload_error:
        response_lines.append(f"飞书上传告警: {upload_error}")
    if failed_urls:
        response_lines.append(f"抓取失败链接数: {len(failed_urls)}")
    response_lines.append("论文标题：")
    if selected_papers:
        for idx, paper in enumerate(selected_papers, start=1):
            date_suffix = f" ({paper['published_at']})" if paper.get("published_at") else ""
            response_lines.append(f"{idx}. {paper.get('title', 'Untitled')}{date_suffix}")
    else:
        response_lines.append("1. 没有找到符合条件的论文。")
    return "\n".join(response_lines)


async def _find_remote_run_folder(
    *,
    client: FeishuIdeaDocClient,
    cfg: Any,
    entry: dict[str, Any],
    selector: str,
) -> dict[str, Any] | None:
    folder_token = str(entry.get("feishu_folder_token", "") or "").strip()
    folder_name = str(
        entry.get("feishu_folder_name", "")
        or entry.get("run_id", "")
        or ""
    ).strip()
    if folder_token:
        return {
            "token": folder_token,
            "name": folder_name,
        }

    root_token = str(getattr(cfg, "feishu_doc_folder_token", "") or "").strip()
    if not root_token:
        root_token = await client._root_folder_token()

    papers_folder = await client.find_child_folder(
        parent_folder_token=root_token,
        name="papers",
    )
    if not papers_folder:
        return None

    exact_candidates = {
        candidate.strip()
        for candidate in (
            str(entry.get("feishu_folder_name", "") or ""),
            str(entry.get("run_id", "") or ""),
        )
        if candidate and candidate.strip()
    }
    prefix_candidates = {
        candidate
        for candidate in (
            _run_timestamp_prefix(str(entry.get("called_at", "") or "")),
            _run_timestamp_prefix(selector),
        )
        if candidate
    }

    children = await client.list_child_folders(parent_folder_token=papers_folder["token"])
    for child in children:
        child_name = str(child.get("name", "") or "").strip()
        if child_name and child_name in exact_candidates:
            return child

    prefix_matches = [
        child
        for child in children
        if any(
            str(child.get("name", "") or "").strip().startswith(prefix)
            for prefix in prefix_candidates
        )
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]
    if len(prefix_matches) > 1:
        candidates = ", ".join(
            str(child.get("name", "") or "").strip()
            for child in prefix_matches[:5]
        )
        raise RuntimeError(
            f"Multiple Feishu folders matched this time selector: {candidates}"
        )
    return None


@tool(parse_docstring=True)
async def delete_paper_search_run(request_text: str) -> str:
    """Delete one `/search` invocation by time and remove its Feishu folder.

    Args:
        request_text: User message containing `/delete <time>`

    Returns:
        Short deletion summary for the matched invocation
    """
    try:
        parsed = parse_delete_request_text(request_text)
    except ValueError:
        return (
            "\u7262\u5927\u8fd8\u9700\u8981\u4e00\u4e2a\u65f6\u95f4\u9009\u62e9\u5668\u3002\n"
            "\u7528\u6cd5\uff1a/delete 20260404-123456"
        )

    selector = parsed["selector"]
    entries = _load_invocation_metadata()
    if not entries:
        return (
            "\u7262\u5927\u8fd8\u6ca1\u627e\u5230\u4efb\u4f55 /search \u5143\u6570\u636e\u8bb0\u5f55\u3002"
        )

    matches = _match_invocation_entries(entries, selector)
    if not matches:
        return (
            "\u6ca1\u6709\u627e\u5230\u5bf9\u5e94\u65f6\u95f4\u7684 /search \u8bb0\u5f55\u3002\n"
            f"\u65f6\u95f4\u9009\u62e9\u5668: {selector}"
        )
    if len(matches) > 1:
        preview = "\n".join(
            f"{offset + 1}. {_render_invocation_ref(entry)}"
            for offset, (_, entry) in enumerate(matches[:5])
        )
        return (
            "\u8fd9\u4e2a\u65f6\u95f4\u9009\u62e9\u5668\u547d\u4e2d\u4e86\u591a\u6761 /search \u8bb0\u5f55\uff0c"
            "\u8bf7\u518d\u5177\u4f53\u4e00\u70b9\u3002\n"
            f"{preview}"
        )

    idx, entry = matches[0]
    remote_deleted = False
    remote_missing = False
    cfg = get_effective_config()
    needs_remote_delete = any(
        str(entry.get(key, "") or "").strip()
        for key in ("feishu_folder_token", "feishu_folder_url", "feishu_folder_name", "run_id")
    )

    if needs_remote_delete:
        if not cfg.feishu_app_id or not cfg.feishu_app_secret:
            return (
                "\u627e\u5230\u4e86\u8fd9\u6761 /search \u8bb0\u5f55\uff0c"
                "\u4f46\u5f53\u524d\u6ca1\u6709\u98de\u4e66\u51ed\u636e\uff0c\u6240\u4ee5\u6682\u65f6\u4e0d\u4f1a\u5220\u9664\u672c\u5730\u5143\u6570\u636e\u3002\n"
                f"\u8bb0\u5f55: {_render_invocation_ref(entry)}"
            )

        client = FeishuIdeaDocClient(
            app_id=cfg.feishu_app_id,
            app_secret=cfg.feishu_app_secret,
            domain=cfg.feishu_domain,
        )
        try:
            remote_folder = await _find_remote_run_folder(
                client=client,
                cfg=cfg,
                entry=entry,
                selector=selector,
            )
            if remote_folder:
                await client.delete_drive_file(
                    file_token=str(remote_folder.get("token", "") or ""),
                    file_type="folder",
                )
                remote_deleted = True
            else:
                remote_missing = True
        except Exception as exc:
            return (
                "\u627e\u5230\u4e86\u8fd9\u6761 /search \u8bb0\u5f55\uff0c"
                "\u4f46\u5220\u9664\u98de\u4e66\u6587\u4ef6\u5939\u5931\u8d25\uff0c\u6240\u4ee5\u672c\u5730\u5143\u6570\u636e\u4e5f\u672a\u5220\u9664\u3002\n"
                f"\u8bb0\u5f55: {_render_invocation_ref(entry)}\n"
                f"\u539f\u56e0: {exc}"
            )
        finally:
            await client.aclose()

    updated_entries = entries[:idx] + entries[idx + 1 :]
    _save_invocation_metadata(updated_entries)

    response_lines = [
        "\u7262\u5927\u5df2\u5b8c\u6210 /delete\u3002",
        f"\u8bb0\u5f55: {_render_invocation_ref(entry)}",
        f"\u672c\u5730\u5143\u6570\u636e: {_display_path(_metadata_log_path())}",
    ]
    if remote_deleted:
        response_lines.append(
            "\u98de\u4e66\u6587\u4ef6\u5939: \u5df2\u5220\u9664"
        )
    elif remote_missing:
        response_lines.append(
            "\u98de\u4e66\u6587\u4ef6\u5939: \u672a\u627e\u5230\uff0c\u5df2\u4ec5\u6e05\u7406\u672c\u5730\u8bb0\u5f55"
        )
    else:
        response_lines.append(
            "\u98de\u4e66\u6587\u4ef6\u5939: \u65e0\u9700\u5220\u9664"
        )
    return "\n".join(response_lines)


__all__ = [
    "delete_paper_search_run",
    "parse_search_request",
    "parse_search_request_text",
    "parse_delete_request_text",
    "run_paper_search",
]
