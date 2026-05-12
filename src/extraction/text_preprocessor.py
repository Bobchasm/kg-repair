"""
文本预处理
"""
import logging
import os
import re
from pathlib import Path
from typing import List, Tuple

import jieba
import jieba.posseg as pseg

logger = logging.getLogger(__name__)

# 分句正则
_SENT_SPLIT = re.compile(r"(?<=[。！？；\n])")


@staticmethod
def _default_domain_dict() -> str:
    return str(Path(__file__).parents[2] / "dicts" / "auto_repair_dict.txt")


class TextPreprocessor:
    """
    文本预处理器
    """

    def __init__(self, domain_dict_path: str = ""):
        self._dict_loaded = False
        dict_path = domain_dict_path or _default_domain_dict()
        self._load_domain_dict(dict_path)

    # 词典加载
    def _load_domain_dict(self, dict_path: str):
        if os.path.exists(dict_path):
            jieba.load_userdict(dict_path)
            logger.info("已加载领域词典：%s", dict_path)
            self._dict_loaded = True
        else:
            logger.warning("领域词典不存在，将使用默认词典：%s", dict_path)
        _FORCE_WORDS = [
            "活塞环", "气缸盖", "曲轴箱", "凸轮轴", "正时链条",
            "点火线圈", "节气门", "喷油嘴", "燃油泵", "变速箱",
            "差速器", "传动轴", "半轴", "减震器", "刹车片",
            "制动鼓", "制动钳", "防抱死系统", "电子控制单元",
            "故障码", "OBD", "扭矩扳手", "活塞销", "连杆轴承",
            "空气滤清器", "机油滤清器", "冷却液", "防冻液",
            "液压油", "润滑油", "火花塞", "缸压", "油压",
        ]
        for w in _FORCE_WORDS:
            jieba.add_word(w, freq=10000)

    def normalize(self, text: str) -> str:
        """规范化文本：全角转半角、多余空白合并。"""
        result = []
        for ch in text:
            code = ord(ch)
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            elif ch == "\u3000":
                result.append(" ")
            else:
                result.append(ch)
        text = "".join(result)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def sentence_split(self, text: str) -> List[str]:
        """将文本切分为句子列表，过滤过短句。"""
        text = self.normalize(text)
        parts = _SENT_SPLIT.split(text)
        sentences = []
        for s in parts:
            s = s.strip()
            if len(s) >= 8:
                sentences.append(s)
        return sentences

    def tokenize(self, text: str) -> List[Tuple[str, str]]:
        pairs = pseg.cut(self.normalize(text))
        return [(w, f) for w, f in pairs if w.strip()]

    def get_words(self, text: str) -> List[str]:
        return [w for w, _ in self.tokenize(text)]
