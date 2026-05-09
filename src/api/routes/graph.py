"""
graph.py — 图谱核心查询路由
提供：概览图、子图、节点列表接口
"""
from typing import Optional
from fastapi import APIRouter, Request, Query, HTTPException

router = APIRouter()


def _get_db(request: Request):
    return request.app.state.db


@router.get("/overview")
async def get_overview(
    request: Request,
    limit: int = Query(5000, ge=10, le=10000, description="返回最大节点数"),
):
    """获取图谱概览（随机采样，用于首屏展示）。"""
    db = _get_db(request)
    return db.get_overview_graph(limit=limit)


@router.get("/subgraph/{node_name}")
async def get_subgraph(
    node_name: str,
    request: Request,
    hops: int = Query(2, ge=1, le=4, description="跳数"),
    max_nodes: int = Query(100, ge=10, le=300),
):
    """以指定节点为中心展开 N 跳子图。"""
    db = _get_db(request)
    data = db.get_subgraph(node_name=node_name, hops=hops, max_nodes=max_nodes)
    if not data["nodes"]:
        raise HTTPException(status_code=404, detail=f"节点 '{node_name}' 不存在")
    return data


@router.get("/nodes")
async def get_nodes(
    request: Request,
    label: Optional[str] = Query(None, description="节点类型过滤"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    """分页获取节点列表。"""
    db = _get_db(request)
    return db.get_all_nodes_paginated(label=label, skip=skip, limit=limit)
