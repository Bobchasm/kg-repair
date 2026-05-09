"""
pipeline.py — 抽取总调度器
将 PDF抽取 → 文本预处理 → NER → RE 串联为完整管线。
设计模式：模板方法（Pipeline基类） + 策略（可替换各阶段）
"""
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml
from tqdm import tqdm

from src.extraction.pdf_extractor import PDFExtractor, TextChunk, TableRecord
from src.extraction.text_preprocessor import TextPreprocessor
from src.extraction.ner_extractor import Entity, NERExtractor, _DICT_ENTITIES
from src.extraction.re_extractor import REExtractor
from src.graph.schema import Triple

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """管线输出汇总"""
    chunks_total: int = 0
    sentences_total: int = 0
    entities: List[Entity] = field(default_factory=list)
    triples: List[Triple] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    extra_nodes: Dict[str, List[Dict]] = field(default_factory=dict)  # label → 直写节点字典

    @property
    def entity_count(self): return len(self.entities)
    @property
    def triple_count(self): return len(self.triples)


# 故障码正则：大写字母 + 3~5 位数字
_FAULT_CODE_RE = re.compile(r"^[A-Z]\d{3,5}$")
_HEADER_KEYWORDS = {
    "item", "items", "项目", "名称", "零件", "故障码",
    "描述", "原因", "说明", "规格", "标准", "no.", "no",
}


class ExtractionPipeline:
    """
    知识抽取主管线：
      PDF → Chunk → Sentence → NER → RE → Triple
    """

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        ext_cfg = cfg.get("extraction", {})
        self._pdf_extractor  = PDFExtractor(max_pages=ext_cfg.get("max_pages", -1))
        self._preprocessor   = TextPreprocessor(
            domain_dict_path=ext_cfg.get("domain_dict_path", "")
        )
        self._ner            = NERExtractor(
            crf_model_path=ext_cfg.get("crf_model_path", "models/crf_ner.pkl")
        )
        self._re             = REExtractor()
        self._pdf_files      = ext_cfg.get("pdf_files", [])
        self._min_sent_len   = ext_cfg.get("min_sentence_len", 10)

    # ── 主入口 ────────────────────────────────────────────────────
    def run(self, pdf_files: Optional[List[str]] = None) -> ExtractionResult:
        """
        完整运行抽取管线。
        Args:
            pdf_files: 覆盖 config.yaml 中的 pdf_files（调试用）
        """
        files = pdf_files or self._pdf_files
        result = ExtractionResult()

        logger.info("=== 开始知识抽取管线，共 %d 个文件 ===", len(files))

        # Step 0: 表格抽取（优先）
        table_records = self._pdf_extractor.extract_files_tables(files)
        tbl_entities, tbl_triples, tbl_extra = self._process_table_records(table_records)
        all_entities: List[Entity] = list(tbl_entities)
        all_triples:  List[Triple] = list(tbl_triples)
        for lbl, nodes in tbl_extra.items():
            result.extra_nodes.setdefault(lbl, []).extend(nodes)

        # Step 1: PDF → TextChunk
        all_chunks: List[TextChunk] = self._pdf_extractor.extract_files(files)
        result.chunks_total = len(all_chunks)
        logger.info("Step1 PDF抽取完成：%d 个文本块", result.chunks_total)

        # Step 2~4: Chunk → Sentence → NER → RE
        for chunk in tqdm(all_chunks, desc="处理文本块"):
            try:
                chunk_entities, chunk_triples = self._process_chunk(chunk)
                all_entities.extend(chunk_entities)
                all_triples.extend(chunk_triples)
                result.sentences_total += len(self._preprocessor.sentence_split(chunk.text))
            except Exception as e:
                logger.warning("块处理异常 [%s]：%s", chunk.chunk_id, e)
                result.errors.append(str(e))

        result.entities = all_entities
        result.triples  = all_triples

        logger.info(
            "=== 抽取完成 | 句子:%d | 实体:%d | 三元组:%d | 错误:%d ===",
            result.sentences_total, result.entity_count,
            result.triple_count, len(result.errors),
        )
        return result

    # ── 单块处理 ──────────────────────────────────────────────────
    # ── 表格行处理 ──────────────────────────────────────────
    def _process_table_records(
        self,
        records: List[TableRecord],
    ) -> Tuple[List[Entity], List[Triple], Dict[str, List[Dict]]]:
        """阶段1：全量扫描故障码行到fault_registry。阶段2：建Fault节点。其他行走NER+RE。"""
        entities:    List[Entity]          = []
        triples:     List[Triple]          = []
        extra_nodes: Dict[str, List[Dict]] = defaultdict(list)

        fault_registry: Dict[str, Dict] = {}
        normal_rows:    List[TableRecord] = []

        for rec in records:
            if not rec.cells:
                continue
            cells   = [str(c).strip() for c in rec.cells]
            headers = [str(h).strip() for h in rec.headers] if rec.headers else []

            code_idx: Optional[int] = None
            code_val: Optional[str] = None
            for i, cell in enumerate(cells):
                if _FAULT_CODE_RE.match(cell):
                    code_idx = i
                    code_val = cell
                    break

            if code_idx is None:
                normal_rows.append(rec)
                continue

            best_name = ""
            for i, cell in enumerate(cells):
                if i == code_idx or not cell:
                    continue
                if _FAULT_CODE_RE.match(cell) or cell.isdigit():
                    continue
                if len(cell) > len(best_name):
                    best_name = cell

            if not best_name or len(best_name) < 2:
                best_name = code_val or ""

            code_key: str = code_val or ""
            node: Dict = {
                "name":       best_name[:100],
                "fault_code": code_key,
                "source_doc": rec.source_file,
                "description": f"故障码 {code_key}：{best_name[:100]}",
            }
            for i, cell in enumerate(cells):
                if not cell or i == code_idx or cell == best_name:
                    continue
                if _FAULT_CODE_RE.match(cell) or cell.isdigit():
                    continue
                h = (headers[i] if i < len(headers) and headers[i] else f"info{i}")
                node[h] = cell[:200]

            if code_key not in fault_registry:
                fault_registry[code_key] = node
            else:
                existing = fault_registry[code_key]
                for k, v in node.items():
                    if k not in existing and k not in ("name", "fault_code"):
                        existing[k] = v

        for code, node in fault_registry.items():
            extra_nodes["Fault"].append(node)
            entities.append(Entity(
                text=node["name"], label="Fault",
                start=0, end=len(node["name"]),
                confidence=0.95, method="table",
                props={},
            ))

        logger.info("表格抽取：处理 %d 行，建立 %d 个 Fault 节点", len(records), len(fault_registry))

        for rec in normal_rows:
            cells = [str(c).strip() for c in rec.cells]
            if not cells[0] or len(cells[0]) < 2 or cells[0].lower() in _HEADER_KEYWORDS:
                continue
            first = cells[0]
            row_headers = [str(h).strip() for h in rec.headers] if rec.headers else []
            first_ent: Optional[Entity] = None  # 第一列实体（若有效）

            # 直接从第一列创建实体（也写入 extra_nodes，确保进入 Neo4j）
            if (2 <= len(first) <= 50
                    and not first.isdigit()
                    and not re.match(r'^[\d\s.\-/]+$', first)):
                # 优先从词典判断类型，否则默认 Component
                tbl_label = "Component"
                for term, lbl in _DICT_ENTITIES.items():
                    if term in first:
                        tbl_label = lbl
                        break

                # 构建节点字典，包含其余列作为属性和 description
                node_dict: Dict = {"name": first[:50], "source_doc": rec.source_file}
                desc_parts: List[str] = []
                for i, cell in enumerate(cells[1:], 1):
                    if not cell or cell == first:
                        continue
                    hdr = (row_headers[i].strip() if i < len(row_headers) and row_headers[i] else f"col{i}")
                    hdr_key = hdr[:20]
                    if hdr_key.lower() not in _HEADER_KEYWORDS:
                        node_dict[hdr_key] = cell[:200]
                        desc_parts.append(f"{hdr_key}: {cell[:80]}")
                if desc_parts:
                    node_dict["description"] = "; ".join(desc_parts)[:400]

                extra_nodes[tbl_label].append(node_dict)
                # 将第一列实体加入 ents，让它能和该行其他 NER 实体建立关系
                first_ent = Entity(
                    text=first[:50], label=tbl_label,
                    start=0, end=len(first),
                    confidence=0.78, method="table_row",
                    props={},
                )
                entities.append(first_ent)

            pseudo = " ".join(c for c in cells if c and not c.isdigit())
            if len(pseudo) < 6:
                continue
            try:
                tp       = self._preprocessor.tokenize(pseudo)
                words    = [w for w, _ in tp]
                pos_tags = [p for _, p in tp]
                ents     = self._ner.recognize(pseudo, words, pos_tags)
                # 将表格第一列实体也加入，让它能参与共现 RE
                if first_ent is not None:
                    # 避免重复（NER 可能已经识别了这个词）
                    already = any(e.text == first_ent.text for e in ents)
                    if not already:
                        ents = [first_ent] + ents
                entities.extend(ents)
                if len(ents) >= 2:
                    triples.extend(self._re.extract(pseudo, ents, source_doc=rec.source_file))
            except Exception as e:
                logger.debug("表格行 NER 失败：%s", e)

        return entities, triples, dict(extra_nodes)

    def _process_chunk(
        self, chunk: TextChunk
    ) -> tuple[List[Entity], List[Triple]]:
        sentences = self._preprocessor.sentence_split(chunk.text)
        chunk_entities: List[Entity] = []
        chunk_triples: List[Triple]  = []

        for sent in sentences:
            if len(sent) < self._min_sent_len:
                continue
            # 分词 + 词性
            token_pairs = self._preprocessor.tokenize(sent)
            words    = [w for w, _ in token_pairs]
            pos_tags = [p for _, p in token_pairs]

            # NER
            ents = self._ner.recognize(sent, words, pos_tags)
            chunk_entities.extend(ents)

            # RE
            if len(ents) >= 2:
                triples = self._re.extract(sent, ents, source_doc=chunk.source_file)
                chunk_triples.extend(triples)

        return chunk_entities, chunk_triples

    # ── 采样句子（供标注生成使用）────────────────────────────────
    def sample_sentences(
        self,
        pdf_files: Optional[List[str]] = None,
        n: int = 300,
    ) -> List[Dict[str, Any]]:
        """采样 N 条句子，附带初步 NER 结果，用于人工标注校正。"""
        import random
        files = pdf_files or self._pdf_files
        chunks = self._pdf_extractor.extract_files(files)

        samples = []
        all_sents = []
        for chunk in chunks:
            for sent in self._preprocessor.sentence_split(chunk.text):
                if len(sent) >= self._min_sent_len:
                    all_sents.append((sent, chunk.source_file))

        chosen = random.sample(all_sents, min(n, len(all_sents)))
        for idx, (sent, src) in enumerate(chosen):
            token_pairs = self._preprocessor.tokenize(sent)
            words    = [w for w, _ in token_pairs]
            pos_tags = [p for _, p in token_pairs]
            ents = self._ner.recognize(sent, words, pos_tags)
            samples.append({
                "doc_id":   f"sample_{idx:05d}",
                "source":   src,
                "text":     sent,
                "entities": [
                    {"id": f"E{i}", "start": e.start, "end": e.end,
                     "text": e.text, "type": e.label}
                    for i, e in enumerate(ents)
                ],
                "relations": [],  # 人工填写
            })
        return samples
