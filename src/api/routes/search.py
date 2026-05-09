"""
search.py — 实体搜索路由
支持：模糊搜索、自动补全
"""
from fastapi import APIRouter, Request, Query

router = APIRouter()


@router.get("/")
async def search_entities(
    request: Request,
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(30, ge=1, le=100),
):
    """
    按名称模糊搜索实体。
    返回：[{neo4j_id, name, label, props}]
    """
    db = request.app.state.db
    results = db.search_nodes(keyword=q, limit=limit)
    return {"query": q, "results": results, "total": len(results)}
