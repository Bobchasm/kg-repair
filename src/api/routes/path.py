"""
最短路径查询路由
"""
from fastapi import APIRouter, Request, Query, HTTPException

router = APIRouter()


@router.get("/shortest")
async def shortest_path(
    request: Request,
    from_node: str = Query(..., description="起始节点名称"),
    to_node: str   = Query(..., description="目标节点名称"),
):
    """
    查询两个实体之间的最短路径。
    返回：路径节点和关系的交替列表 [{type:node/relation, ...}]
    """
    db = request.app.state.db
    result = db.get_shortest_path(from_name=from_node, to_name=to_node)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 '{from_node}' 到 '{to_node}' 的路径",
        )
    return {"from": from_node, "to": to_node, "path": result, "length": len(result) // 2}
