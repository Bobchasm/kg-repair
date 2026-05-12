"""
PDF 文本抽取
"""
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Tuple

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    """单页文本结构体"""
    page_no: int
    raw_text: str
    source_file: str


@dataclass
class TextChunk:
    """连续文本块（跨段落合并后）"""
    chunk_id: str
    text: str
    page_no: int
    source_file: str


@dataclass
class TableRecord:
    """从 PDF 表格中抽取的一行数据"""
    row_id: str
    headers: List[str]   # 表头行（可能为空）
    cells: List[str]     # 数据行各格内容
    page_no: int
    source_file: str


# 噪声过滤正则（页码、版权、空行等）
_NOISE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                    # 纯数字行（页码）
    re.compile(r"^[\-\─\—]{3,}$"),                 # 分割线
    re.compile(r"^图\s*\d+[\-—]\d+"),              # 图注行
    re.compile(r"^表\s*\d+[\-—]\d+"),              # 表注行
    re.compile(r"^©|版权所有|all rights reserved", re.I),
]

# 段落结束标志（不做跨段合并）
_PARA_END = re.compile(r"[。！？…]+\s*$")


class PDFExtractor:
    """
    PDF 文本抽取器
    """

    def __init__(self, max_pages: int = -1):
        """
        Args:
            max_pages: 每个 PDF 最多处理页数，-1 表示全部。
        """
        self._max_pages = max_pages

    def extract_file(self, pdf_path: str) -> List[TextChunk]:
        """抽取单个 PDF，返回文本块列表。"""
        path = Path(pdf_path)
        if not path.exists():
            logger.warning("文件不存在：%s", pdf_path)
            return []
        logger.info("开始抽取：%s", path.name)
        pages = list(self._iter_pages(str(path)))
        chunks = self._pages_to_chunks(pages)
        logger.info("抽取完成：%s → %d 个文本块", path.name, len(chunks))
        return chunks

    def extract_files(self, pdf_paths: List[str]) -> List[TextChunk]:
        """抽取多个 PDF，合并返回。"""
        all_chunks: List[TextChunk] = []
        for p in pdf_paths:
            all_chunks.extend(self.extract_file(p))
        return all_chunks

    def extract_file_tables(self, pdf_path: str) -> List[TableRecord]:
        """抽取单个 PDF 中的所有表格行，返回 TableRecord 列表。"""
        path = Path(pdf_path)
        if not path.exists():
            return []
        source_name = Path(pdf_path).stem
        records: List[TableRecord] = []
        row_idx = 0
        try:
            doc = fitz.open(str(path))
            total = len(doc)
            limit = total if self._max_pages < 0 else min(self._max_pages, total)
            for page_no in range(limit):
                page = doc[page_no]
                try:
                    finder = page.find_tables()
                except Exception:
                    continue
                for tab in finder:
                    try:
                        data = tab.extract()
                    except Exception:
                        continue
                    if not data or len(data) < 2:
                        continue
                    headers = [str(c or "").strip() for c in data[0]]
                    for row in data[1:]:
                        cells = [str(c or "").strip() for c in row]
                        if not any(cells):  # 跳过空行
                            continue
                        records.append(TableRecord(
                            row_id=f"{source_name}_r{row_idx:05d}",
                            headers=headers,
                            cells=cells,
                            page_no=page_no + 1,
                            source_file=source_name,
                        ))
                        row_idx += 1
            doc.close()
        except Exception as e:
            logger.warning("表格抽取失败 [%s]: %s", pdf_path, e)
        logger.info("表格抽取完成：%s → %d 行", Path(pdf_path).name, len(records))
        return records

    def extract_files_tables(self, pdf_paths: List[str]) -> List[TableRecord]:
        """抽取多个 PDF 的所有表格行。"""
        all_records: List[TableRecord] = []
        for p in pdf_paths:
            all_records.extend(self.extract_file_tables(p))
        return all_records

    def _iter_pages(self, pdf_path: str) -> Iterator[PageText]:
        """逐页读取 PDF，过滤噪声。"""
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error("无法打开 PDF：%s — %s", pdf_path, e)
            return

        total = len(doc)
        limit = total if self._max_pages < 0 else min(self._max_pages, total)
        source_name = Path(pdf_path).stem

        sample_pages = min(5, total)
        sample_text = "".join(
            doc[i].get_text("text") for i in range(sample_pages)
        ).strip()
        if len(sample_text) < 50:
            doc.close()
            return

        for page_no in range(limit):
            page = doc[page_no]
            text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            clean = self._clean_page(text)
            if len(clean.strip()) < 20:
                continue
            yield PageText(page_no=page_no + 1, raw_text=clean, source_file=source_name)
        doc.close()

    def _clean_page(self, text: str) -> str:
        """清理单页文本：去噪、规范化空白。"""
        lines = text.splitlines()
        kept = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if any(p.match(stripped) for p in _NOISE_PATTERNS):
                continue
            if len(stripped) < 4:
                continue
            kept.append(stripped)
        return "\n".join(kept)

    def _pages_to_chunks(self, pages: List[PageText]) -> List[TextChunk]:
        """
        将多页文本合并为语义段落块。
        """
        chunks: List[TextChunk] = []
        buffer: List[str] = []
        buf_page = 1
        buf_src = ""
        chunk_idx = 0

        def flush():
            nonlocal chunk_idx
            text = " ".join(buffer).strip()
            if len(text) >= 15:
                chunks.append(TextChunk(
                    chunk_id=f"{buf_src}_c{chunk_idx:05d}",
                    text=text,
                    page_no=buf_page,
                    source_file=buf_src,
                ))
                chunk_idx += 1
            buffer.clear()

        for page in pages:
            buf_src = page.source_file
            for line in page.raw_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                buffer.append(line)
                buf_page = page.page_no
                if _PARA_END.search(line) or len("".join(buffer)) > 512:
                    flush()

        flush()
        return chunks
