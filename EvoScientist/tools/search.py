"""Search and source-ingestion tools for research workflows.

This module keeps the original Tavily search helper while adding the first
Phase B building blocks for literature collection:

- ``collect_sources``: gather candidate URLs from search + seed URLs
- ``read_paper_source``: fetch one source and persist a normalized evidence row
- ``extract_claims``: extract claim-like sentences and update the evidence store
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import InjectedToolArg, tool
from markdownify import markdownify
from tavily import TavilyClient
from typing_extensions import Annotated

# Lazy initialization - only create client when needed
_tavily_client = None

DEFAULT_LIT_REVIEW_DIR = Path("artifacts") / "lit_review"
DEFAULT_SOURCE_DIR = DEFAULT_LIT_REVIEW_DIR / "sources"


def _get_tavily_client() -> TavilyClient:
    """Get or create the Tavily client (lazy initialization)."""
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient()
    return _tavily_client


def _get_artifact_paths() -> tuple[Path, Path, Path]:
    """Return the literature review artifact paths rooted at the cwd."""
    root = Path.cwd() / DEFAULT_LIT_REVIEW_DIR
    source_dir = Path.cwd() / DEFAULT_SOURCE_DIR
    evidence_path = root / "evidence.jsonl"
    root.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    return root, source_dir, evidence_path


def _normalize_keywords(raw: str | list[str] | None) -> list[str]:
    """Normalize free-form keyword input into a lowercase unique list."""
    if raw is None:
        return []
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            try:
                decoded = json.loads(stripped)
            except json.JSONDecodeError:
                decoded = None
            if isinstance(decoded, list):
                parts = decoded
            else:
                parts = re.split(r"[,;\n]+", raw)
        else:
            parts = re.split(r"[,;\n]+", raw)
    else:
        parts = list(raw)

    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        cleaned = str(part).strip().lower()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _slugify(value: str) -> str:
    """Build a stable ASCII-ish slug for artifact filenames."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    if cleaned:
        return cleaned[:80]
    return "source"


def _strip_markdown(text: str) -> str:
    """Reduce markdown-ish content to plain text for heuristic extraction."""
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    text = re.sub(r"^[#>\-*+\d.\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str) -> list[str]:
    """Split free text into sentence-like chunks."""
    plain = _strip_markdown(text)
    if not plain:
        return []
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", plain)
        if sentence.strip()
    ]


def _score_relevance(text: str, keywords: list[str]) -> float:
    """Return a coarse keyword relevance score in the [0, 1] range."""
    if not keywords:
        return 0.0
    haystack = text.lower()
    hits = sum(1 for keyword in keywords if keyword in haystack)
    return round(hits / len(keywords), 3)


def _build_summary(text: str, max_sentences: int = 3) -> str:
    """Create a short extractive summary from the source text."""
    sentences = _split_sentences(text)
    if not sentences:
        return ""
    return " ".join(sentences[:max_sentences])


def _extract_claims_from_text(text: str, max_claims: int = 5) -> list[str]:
    """Heuristically extract claim-like sentences from source text."""
    cues = (
        "we ",
        "our ",
        "results",
        "result",
        "show",
        "shows",
        "find",
        "found",
        "demonstrate",
        "demonstrates",
        "suggest",
        "suggests",
        "improve",
        "improves",
        "outperform",
        "outperforms",
        "achieve",
        "achieves",
        "conclude",
        "concludes",
        "indicate",
        "indicates",
    )
    claims: list[str] = []
    for sentence in _split_sentences(text):
        lower = sentence.lower()
        if len(sentence) < 40:
            continue
        if any(cue in lower for cue in cues):
            claims.append(sentence)
        if len(claims) >= max_claims:
            break
    if claims:
        return claims
    return _split_sentences(text)[:max_claims]


def _infer_source_type(url: str, content_type: str | None = None) -> str:
    """Infer whether a source is an HTML page or a PDF."""
    parsed_path = urlparse(url).path.lower()
    header = (content_type or "").lower()
    if parsed_path.endswith(".pdf") or "application/pdf" in header:
        return "pdf"
    return "webpage"


def _normalize_urls(raw: str | list[str] | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,;\n]+", raw)
    else:
        parts = list(raw)
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        candidate = str(part).strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return normalized


def _looks_like_article_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    article_cues = (
        "/abs/",
        "/pdf/",
        "/article/",
        "/paper/",
        "/papers/",
        "/publication/",
        "/publications/",
        "/doi/",
    )
    return any(cue in path for cue in article_cues) or path.endswith(".pdf")


def _extract_title_from_html(html: str, url: str) -> str:
    """Extract a best-effort title from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title
    return Path(urlparse(url).path).stem or url


def _normalize_published_at(value: str | None) -> str | None:
    """Normalize a best-effort publication date into YYYY-MM-DD."""
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip().strip(",")
    if not text:
        return None

    direct_match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", text)
    if direct_match:
        year, month, day = direct_match.groups()
        try:
            return datetime(int(year), int(month), int(day)).strftime("%Y-%m-%d")
        except ValueError:
            return None

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _extract_published_at_from_html(html: str) -> str | None:
    """Extract a best-effort publication date from HTML metadata."""
    soup = BeautifulSoup(html, "html.parser")
    meta_candidates = (
        ("meta", {"name": "citation_publication_date"}),
        ("meta", {"name": "citation_date"}),
        ("meta", {"name": "dc.date"}),
        ("meta", {"name": "dc.date.issued"}),
        ("meta", {"property": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "publish_date"}),
        ("meta", {"name": "pubdate"}),
        ("meta", {"itemprop": "datePublished"}),
        ("time", {"datetime": True}),
    )

    for tag_name, attrs in meta_candidates:
        node = soup.find(tag_name, attrs=attrs)
        if node is None:
            continue
        raw_value = node.get("content") or node.get("datetime") or node.get_text(" ", strip=True)
        published_at = _normalize_published_at(raw_value)
        if published_at:
            return published_at

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    regexes = (
        r"Submitted on (\d{1,2} [A-Za-z]+ \d{4})",
        r"Published[:\s]+([A-Za-z]+ \d{1,2}, \d{4})",
        r"Published[:\s]+(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
        r"(\d{4}[-/.]\d{1,2}[-/.]\d{1,2})",
    )
    for pattern in regexes:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        published_at = _normalize_published_at(match.group(1))
        if published_at:
            return published_at
    return None


def _extract_pdf_text(pdf_bytes: bytes) -> tuple[str, str | None]:
    """Extract text from PDF bytes when an optional parser is available."""
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return "", "PDF parser dependency 'pypdf' is not installed."

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append(page_text.strip())
        text = "\n\n".join(pages)
        if not text.strip():
            return "", "No extractable text was found in the PDF."
        return text, None
    except Exception as exc:  # pragma: no cover - defensive path
        return "", f"PDF extraction failed: {exc}"


async def _fetch_source_content(url: str, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch one source and normalize it into a common structure."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        source_type = _infer_source_type(url, content_type)
        final_url = str(response.url)

        if source_type == "pdf":
            text, warning = await asyncio.to_thread(_extract_pdf_text, response.content)
            title = Path(urlparse(final_url).path).stem or final_url
            return {
                "title": title,
                "url": final_url,
                "source_type": source_type,
                "content": text,
                "warning": warning,
                "content_type": content_type,
                "final_url": final_url,
                "raw_bytes": response.content,
                "published_at": None,
            }

        html = response.text
        title = _extract_title_from_html(html, final_url)
        return {
            "title": title,
            "url": final_url,
            "source_type": source_type,
            "content": markdownify(html),
            "warning": None,
            "content_type": content_type,
            "final_url": final_url,
            "raw_html": html,
            "published_at": _extract_published_at_from_html(html),
        }


async def _search_tavily_results(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> dict[str, Any]:
    """Run a Tavily search in a worker thread."""

    def _sync_search() -> dict[str, Any]:
        return _get_tavily_client().search(
            query,
            max_results=max_results,
            topic=topic,
        )

    return await asyncio.to_thread(_sync_search)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL records from disk, skipping blank lines."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    """Write JSONL records back to disk."""
    if not records:
        path.write_text("", encoding="utf-8")
        return
    payload = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    path.write_text(payload + "\n", encoding="utf-8")


def _upsert_evidence_record(path: Path, record: dict[str, Any]) -> None:
    """Upsert one evidence row by URL."""
    records = _load_jsonl(path)
    updated = False
    for idx, existing in enumerate(records):
        if existing.get("url") == record.get("url"):
            merged = dict(existing)
            merged.update(record)
            records[idx] = merged
            updated = True
            break
    if not updated:
        records.append(record)
    _write_jsonl(path, records)


def _load_existing_evidence(path: Path, url: str) -> dict[str, Any] | None:
    """Return one existing evidence row by URL if present."""
    for record in _load_jsonl(path):
        if record.get("url") == url:
            return record
    return None


def _source_artifact_path(source_dir: Path, title: str, url: str, source_type: str) -> Path:
    """Return a stable file path for source text artifacts."""
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    suffix = ".txt" if source_type == "pdf" else ".md"
    filename = f"{_slugify(title)}-{url_hash}{suffix}"
    return source_dir / filename


def _write_source_artifact(
    source_dir: Path,
    title: str,
    url: str,
    source_type: str,
    content: str,
) -> Path:
    """Persist normalized source text to disk."""
    path = _source_artifact_path(source_dir, title, url, source_type)
    path.write_text(content or "", encoding="utf-8")
    return path


async def fetch_webpage_content(url: str, timeout: float = 10.0) -> str:
    """Fetch and convert webpage content to markdown.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Webpage content as markdown
    """
    try:
        source = await _fetch_source_content(url, timeout=timeout)
        warning = source.get("warning")
        if warning and not source.get("content"):
            return f"Warning for {url}: {warning}"
        return source.get("content", "")
    except Exception as exc:
        return f"Error fetching content from {url}: {exc}"


@tool(parse_docstring=True)
async def crawl_site_articles(
    site_urls: str | list[str],
    keywords: str | list[str] | None = None,
    max_articles_per_site: int = 20,
    max_depth: int = 1,
    max_pages_per_site: int = 5,
) -> str:
    """Crawl one or more literature website pages and extract article links.

    Args:
        site_urls: Website index/listing URLs to crawl
        keywords: Optional keywords used to filter article titles and URLs
        max_articles_per_site: Maximum article links to retain per site
        max_depth: Maximum recursive depth for same-domain listing pages
        max_pages_per_site: Maximum pages to visit per site

    Returns:
        Summary of discovered article links and saved crawl index path
    """
    sites = _normalize_urls(site_urls)
    keyword_list = _normalize_keywords(keywords)
    root, _, evidence_path = _get_artifact_paths()
    crawl_index_path = root / "site_crawl_index.json"
    crawl_report_path = root / "site_crawl_report.md"

    discovered_sites: list[dict[str, Any]] = []
    all_articles: list[dict[str, Any]] = []

    async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
        for site_url in sites:
            host = urlparse(site_url).netloc
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/91.0.4472.124 Safari/537.36"
                )
            }
            queue: list[tuple[str, int]] = [(site_url, 0)]
            visited_pages: set[str] = set()
            seen_urls: set[str] = set()
            retained: list[dict[str, Any]] = []
            page_count = 0

            while queue and page_count < max_pages_per_site:
                current_url, depth = queue.pop(0)
                if current_url in visited_pages:
                    continue
                visited_pages.add(current_url)
                page_count += 1

                response = await client.get(current_url, headers=headers)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

                for anchor in soup.find_all("a", href=True):
                    href = str(anchor.get("href", "")).strip()
                    text = anchor.get_text(" ", strip=True)
                    if not href:
                        continue
                    absolute = urljoin(current_url, href)
                    parsed = urlparse(absolute)
                    if parsed.scheme not in ("http", "https"):
                        continue
                    if parsed.netloc != host:
                        continue

                    score_haystack = f"{text}\n{absolute}"
                    relevance = _score_relevance(score_haystack, keyword_list)
                    article_like = _looks_like_article_url(absolute)

                    if article_like:
                        if absolute in seen_urls:
                            continue
                        seen_urls.add(absolute)
                        if keyword_list and relevance <= 0.0 and not text:
                            continue
                        retained.append(
                            {
                                "site_url": site_url,
                                "discovered_from": current_url,
                                "title": text or Path(parsed.path).stem or absolute,
                                "url": absolute,
                                "source_type": _infer_source_type(absolute),
                                "relevance_score": relevance,
                            }
                        )
                        continue

                    if depth >= max_depth:
                        continue
                    if absolute in visited_pages:
                        continue
                    listing_cues = ("/papers", "/paper", "/archive", "/list", "/proceedings", "/issue", "/vol")
                    if keyword_list and relevance <= 0.0 and not any(cue in parsed.path.lower() for cue in listing_cues):
                        continue
                    queue.append((absolute, depth + 1))

            retained = sorted(
                retained,
                key=lambda item: (item.get("relevance_score", 0.0), _looks_like_article_url(item["url"])),
                reverse=True,
            )[:max_articles_per_site]

            discovered_sites.append(
                {
                    "site_url": site_url,
                    "visited_pages": sorted(visited_pages),
                    "article_count": len(retained),
                    "articles": retained,
                }
            )
            all_articles.extend(retained)

    crawl_index_path.write_text(
        json.dumps(
            {
                "site_urls": sites,
                "keywords": keyword_list,
                "sites": discovered_sites,
                "articles": all_articles,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_lines = [
        "# Site Crawl Report",
        "",
        f"- Site Count: {len(discovered_sites)}",
        f"- Article Count: {len(all_articles)}",
        "",
    ]
    for site in discovered_sites:
        report_lines.extend(
            [
                f"## {site.get('site_url', '')}",
                f"- Visited Pages: {len(site.get('visited_pages', []))}",
                f"- Retained Articles: {site.get('article_count', 0)}",
                "",
            ]
        )
        for article in site.get("articles", []):
            report_lines.extend(
                [
                    f"### {article.get('title', article.get('url', 'Untitled'))}",
                    f"- URL: {article.get('url', '')}",
                    f"- Discovered From: {article.get('discovered_from', '')}",
                    f"- Relevance Score: {article.get('relevance_score', 0.0)}",
                    "",
                ]
            )
    crawl_report_path.write_text("\n".join(report_lines).rstrip() + "\n", encoding="utf-8")

    return (
        f"Crawled {len(discovered_sites)} site(s) and discovered {len(all_articles)} article link(s).\n"
        f"Saved crawl index to {crawl_index_path.as_posix()}\n"
        f"Saved crawl report to {crawl_report_path.as_posix()}"
    )


@tool(parse_docstring=True)
async def tavily_search(
    query: str,
    max_results: Annotated[int, InjectedToolArg] = 3,
    topic: Annotated[
        Literal["general", "news", "finance"], InjectedToolArg
    ] = "general",
) -> str:
    """Search the web for information on a given query.

    Uses Tavily to discover relevant URLs, then fetches and returns
    full webpage content as markdown for comprehensive research.

    Args:
        query: Search query to execute

    Returns:
        Formatted search results with full webpage content in markdown
    """
    try:
        search_results = await _search_tavily_results(
            query=query,
            max_results=max_results,
            topic=topic,
        )

        results = search_results.get("results", [])
        if not results:
            return f"No results found for '{query}'"

        fetch_tasks = [fetch_webpage_content(result["url"]) for result in results]
        contents = await asyncio.gather(*fetch_tasks)

        result_texts = []
        for result, content in zip(results, contents):
            result_text = f"""## {result["title"]}
**URL:** {result["url"]}

{content}

---
"""
            result_texts.append(result_text)

        return f"""Found {len(result_texts)} result(s) for '{query}':

{"".join(result_texts)}"""

    except Exception as exc:
        return f"Search failed: {exc}"


@tool(parse_docstring=True)
async def collect_sources(
    query: str,
    seed_urls: list[str] | None = None,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
) -> str:
    """Collect candidate literature sources and save them as an index.

    Args:
        query: Research query or topic keywords
        seed_urls: Optional URLs supplied by the user
        max_results: Maximum Tavily results to collect
        topic: Tavily topic namespace

    Returns:
        A short summary and the saved source index path
    """
    seed_urls = seed_urls or []
    _, _, evidence_path = _get_artifact_paths()
    source_index_path = evidence_path.parent / "source_index.json"

    results: list[dict[str, Any]] = []
    search_warning: str | None = None
    if query.strip():
        if os.getenv("TAVILY_API_KEY", "").strip():
            try:
                search_results = await _search_tavily_results(
                    query=query,
                    max_results=max_results,
                    topic=topic,
                )
                results = list(search_results.get("results", []))
            except Exception as exc:
                search_warning = f"Tavily search unavailable: {exc}"
        else:
            search_warning = (
                "Tavily search skipped because TAVILY_API_KEY is not configured."
            )

    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    rank = 1

    for result in results:
        url = result.get("url", "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(
            {
                "rank": rank,
                "title": result.get("title") or url,
                "url": url,
                "snippet": result.get("content", ""),
                "source_type": _infer_source_type(url),
                "query": query,
            }
        )
        rank += 1

    for url in seed_urls:
        normalized = url.strip()
        if not normalized or normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        records.append(
            {
                "rank": rank,
                "title": Path(urlparse(normalized).path).stem or normalized,
                "url": normalized,
                "snippet": "",
                "source_type": _infer_source_type(normalized),
                "query": query,
            }
        )
        rank += 1

    source_index_path.write_text(
        json.dumps({"query": query, "sources": records}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if not records:
        message = (
            f"No sources collected for '{query}'. "
            f"Saved empty index to {source_index_path.as_posix()}"
        )
        if search_warning:
            message += f"\n{search_warning}"
        return message

    preview_lines = [
        f"{item['rank']}. {item['title']} ({item['source_type']}) - {item['url']}"
        for item in records[:5]
    ]
    message = (
        f"Collected {len(records)} source(s) for '{query}'.\n"
        f"Saved index: {source_index_path.as_posix()}\n"
        + "\n".join(preview_lines)
    )
    if search_warning:
        message += f"\nNote: {search_warning}"
    return message


@tool(parse_docstring=True)
async def read_paper_source(
    url: str,
    keywords: str | list[str] | None = None,
    timeout: float = 20.0,
) -> str:
    """Read one paper or article source and persist a normalized evidence row.

    Args:
        url: Source URL to fetch
        keywords: Optional relevance keywords
        timeout: Request timeout in seconds

    Returns:
        A short source digest plus artifact paths
    """
    keywords = _normalize_keywords(keywords)
    _, source_dir, evidence_path = _get_artifact_paths()

    try:
        source = await _fetch_source_content(url, timeout=timeout)
    except Exception as exc:
        return f"Failed to read source {url}: {exc}"

    content = source.get("content", "")
    title = source.get("title") or url
    source_type = source.get("source_type") or _infer_source_type(url)
    warning = source.get("warning")

    source_path = _write_source_artifact(source_dir, title, url, source_type, content)
    summary = _build_summary(content)
    evidence_record = {
        "title": title,
        "url": url,
        "source_type": source_type,
        "summary": summary,
        "claims": [],
        "keywords": keywords,
        "relevance_score": _score_relevance(
            f"{title}\n{summary}\n{content}",
            keywords,
        ),
        "content_path": source_path.as_posix(),
        "warning": warning,
    }
    _upsert_evidence_record(evidence_path, evidence_record)

    preview = summary or "No summary could be extracted yet."
    lines = [
        f"Read source: {title}",
        f"Type: {source_type}",
        f"Evidence: {evidence_path.as_posix()}",
        f"Content artifact: {source_path.as_posix()}",
        f"Relevance score: {evidence_record['relevance_score']}",
        f"Summary: {preview}",
    ]
    if warning:
        lines.append(f"Warning: {warning}")
    return "\n".join(lines)


@tool(parse_docstring=True)
async def extract_claims(
    url: str,
    keywords: str | list[str] | None = None,
    max_claims: int = 5,
    timeout: float = 20.0,
) -> str:
    """Extract claim-like statements from one source and update evidence.jsonl.

    Args:
        url: Source URL to process
        keywords: Optional relevance keywords
        max_claims: Maximum number of claims to return
        timeout: Request timeout used only when source content must be refetched

    Returns:
        Extracted claims and the evidence artifact path
    """
    keywords = _normalize_keywords(keywords)
    _, _, evidence_path = _get_artifact_paths()
    record = _load_existing_evidence(evidence_path, url)
    content = ""
    title = url
    source_type = _infer_source_type(url)
    warning = None
    content_path = ""

    if record is not None:
        title = record.get("title") or title
        source_type = record.get("source_type") or source_type
        warning = record.get("warning")
        content_path = record.get("content_path", "")
        if content_path and Path(content_path).exists():
            content = Path(content_path).read_text(encoding="utf-8")

    if not content:
        try:
            source = await _fetch_source_content(url, timeout=timeout)
        except Exception as exc:
            return f"Failed to load source for claim extraction {url}: {exc}"

        title = source.get("title") or title
        source_type = source.get("source_type") or source_type
        warning = source.get("warning")
        content = source.get("content", "")
        _, source_dir, _ = _get_artifact_paths()
        content_path = _write_source_artifact(
            source_dir,
            title,
            url,
            source_type,
            content,
        ).as_posix()

    claims = _extract_claims_from_text(content, max_claims=max_claims)
    summary = _build_summary(content)
    evidence_record = {
        "title": title,
        "url": url,
        "source_type": source_type,
        "summary": summary,
        "claims": claims,
        "keywords": keywords or (record.get("keywords") if record else []),
        "relevance_score": _score_relevance(
            f"{title}\n{summary}\n{content}",
            keywords or (record.get("keywords") if record else []),
        ),
        "content_path": content_path,
        "warning": warning,
    }
    _upsert_evidence_record(evidence_path, evidence_record)

    if not claims:
        return (
            f"No claim-like sentences were extracted from {title}.\n"
            f"Evidence: {evidence_path.as_posix()}"
        )

    bullet_list = "\n".join(f"- {claim}" for claim in claims)
    return (
        f"Extracted {len(claims)} claim(s) from {title}.\n"
        f"Evidence: {evidence_path.as_posix()}\n"
        f"{bullet_list}"
    )


__all__ = [
    "collect_sources",
    "extract_claims",
    "fetch_webpage_content",
    "read_paper_source",
    "tavily_search",
    "_build_summary",
    "_extract_claims_from_text",
    "_score_relevance",
    "_upsert_evidence_record",
]
