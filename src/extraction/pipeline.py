"""
pipeline.py — 抽取总调度器
将 PDF抽取 → 文本预处理 → NER → RE 串联为完整管线。
设计模式：模板方法（Pipeline基类） + 策略（可替换各阶段）
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import yaml
from tqdm import tqdm

from src.extraction.pdf_extractor import PDFExtractor, TextChunk
from src.extraction.text_preprocessor import TextPreprocessor
from src.extraction.ner_extractor import Entity, NERExtractor
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

    @property
    def entity_count(self): return len(self.entities)
    @property
    def triple_count(self): return len(self.triples)


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

        # Step 1: PDF → TextChunk
        all_chunks: List[TextChunk] = self._pdf_extractor.extract_files(files)
        result.chunks_total = len(all_chunks)
        logger.info("Step1 PDF抽取完成：%d 个文本块", result.chunks_total)

        # Step 2~4: Chunk → Sentence → NER → RE
        all_entities: List[Entity] = []
        all_triples: List[Triple]  = []

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
