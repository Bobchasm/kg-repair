"""
评估结果接口
"""
import json
import logging
import os

from fastapi import APIRouter, HTTPException

router = APIRouter()
logger = logging.getLogger(__name__)

_METRICS_PATH = "output/eval_metrics.json"


@router.get("/metrics", summary="获取评估指标（NER + RE P/R/F1）")
async def get_eval_metrics():
    if not os.path.exists(_METRICS_PATH):
        return {
            "status":  "not_ready",
            "message": "尚未运行评估，请先执行：python scripts/evaluate.py",
        }
    try:
        with open(_METRICS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = "ready"
        return data
    except Exception as e:
        logger.error("读取评估指标文件失败: %s", e)
        raise HTTPException(status_code=500, detail=f"读取评估文件失败: {e}")