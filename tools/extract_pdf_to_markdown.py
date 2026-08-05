from __future__ import annotations

import argparse
import hashlib
from datetime import date
from pathlib import Path

from pypdf import PdfReader


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.splitlines()]
    output: list[str] = []
    empty = False
    for line in lines:
        if not line:
            if not empty:
                output.append("")
            empty = True
        else:
            output.append(line)
            empty = False
    return "\n".join(output).strip()


def extract_pdf(source: Path, output: Path, title: str | None = None) -> Path:
    reader = PdfReader(source)
    heading = title or source.stem
    parts = [
        f"# {heading} - 原始文本提取",
        "",
        f"- 源文件：`{source.name}`",
        f"- PDF 页数：{len(reader.pages)}",
        f"- SHA-256：`{file_sha256(source)}`",
        f"- 提取日期：{date.today().isoformat()}",
        "- 说明：本文件由 PDF 文本层机械提取，用于全文检索；表格、图形和上下标可能错位，关键参数请以专题知识库和源 PDF 原页为准。",
        "",
    ]
    for index, page in enumerate(reader.pages, start=1):
        parts.extend(
            [
                f'<a id="pdf-page-{index:03d}"></a>',
                "",
                f"## PDF 第 {index} 页",
                "",
                normalize_text(page.extract_text() or "") or "_本页没有可提取的文本层。_",
                "",
            ]
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts), encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract page-indexed PDF text to Markdown")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title")
    args = parser.parse_args(argv)
    result = extract_pdf(args.source, args.output, args.title)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
