from __future__ import annotations

import html
import re
from zipfile import ZipFile


def extract_docx_text(content_bytes: bytes) -> str:
    from io import BytesIO
    from xml.etree import ElementTree

    with ZipFile(BytesIO(content_bytes)) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def extract_simple_pdf_text(content_bytes: bytes) -> str:
    raw = content_bytes.decode("latin-1", errors="ignore")
    matches = re.findall(r"\((.*?)\)\s*Tj", raw, flags=re.DOTALL)
    if not matches:
        matches = [
            item
            for array in re.findall(r"\[(.*?)\]\s*TJ", raw, flags=re.DOTALL)
            for item in re.findall(r"\((.*?)\)", array, flags=re.DOTALL)
        ]
    text = "\n".join(_unescape_pdf_text(match) for match in matches)
    return html.unescape(text).strip()


def _unescape_pdf_text(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )
