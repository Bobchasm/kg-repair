"""
图谱统计信息路由
"""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def get_stats(request: Request):
    """
    返回图谱统计信息。
    {
      node_count, rel_count,
      node_labels: [{label, cnt}],
      rel_types:   [{rel, cnt}]
    }
    """
    db = request.app.state.db
    return db.get_stats()
