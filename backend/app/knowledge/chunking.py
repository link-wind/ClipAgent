from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ChunkDraft:
    chunk_type: str
    title_path: str
    content: str
    token_count: int


def _token_count(content: str) -> int:
    return len(content.split())


def chunk_text(content: str) -> list[ChunkDraft]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
    return [
        ChunkDraft(
            chunk_type="paragraph",
            title_path="",
            content=paragraph,
            token_count=_token_count(paragraph),
        )
        for paragraph in paragraphs
    ]


def chunk_markdown_text(content: str) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    heading_stack: list[str] = []
    paragraph_lines: list[str] = []
    list_lines: list[str] = []
    code_lines: list[str] = []
    in_code_block = False
    code_fence = ""

    def current_title_path() -> str:
        return " / ".join(heading_stack)

    def flush_paragraph() -> None:
        if paragraph_lines:
            paragraph = "\n".join(paragraph_lines).strip()
            if paragraph:
                chunks.append(
                    ChunkDraft(
                        chunk_type="paragraph",
                        title_path=current_title_path(),
                        content=paragraph,
                        token_count=_token_count(paragraph),
                    )
                )
            paragraph_lines.clear()

    def flush_list_block() -> None:
        if list_lines:
            block = "\n".join(list_lines).strip()
            if block:
                chunks.append(
                    ChunkDraft(
                        chunk_type="list_block",
                        title_path=current_title_path(),
                        content=block,
                        token_count=_token_count(block),
                    )
                )
            list_lines.clear()

    def flush_code_block() -> None:
        if code_lines:
            block = "\n".join(code_lines).rstrip()
            if block:
                chunks.append(
                    ChunkDraft(
                        chunk_type="code_block",
                        title_path=current_title_path(),
                        content=block,
                        token_count=_token_count(block),
                    )
                )
            code_lines.clear()

    def flush_text_blocks() -> None:
        flush_paragraph()
        flush_list_block()

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()

        if in_code_block:
            if stripped.startswith(code_fence):
                flush_code_block()
                in_code_block = False
                code_fence = ""
            else:
                code_lines.append(raw_line)
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*?)\s*$", stripped)
        if heading_match:
            flush_text_blocks()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_stack[:] = heading_stack[: level - 1]
            heading_stack.append(title)
            continue

        fence_match = re.match(r"^(```|~~~)\s*.*$", stripped)
        if fence_match:
            flush_text_blocks()
            in_code_block = True
            code_fence = fence_match.group(1)
            continue

        if not stripped:
            flush_text_blocks()
            continue

        if re.match(r"^\s*(?:[-*+]|\d+\.)\s+", line):
            flush_paragraph()
            list_lines.append(line)
            continue

        flush_list_block()
        paragraph_lines.append(line)

    if in_code_block:
        flush_code_block()
    flush_text_blocks()

    return chunks
