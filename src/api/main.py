"""
FastAPI 应用入口
"""
import logging
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.graph.neo4j_connector import Neo4jConnector
from src.api.routes import graph, search, path, stats, eval as eval_route

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _load_config(path: str = "config.yaml"):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时连接 Neo4j，关闭时断开。"""
    cfg = _load_config()
    connector = Neo4jConnector.from_config()
    app.state.db = connector
    logger.info("Neo4j 连接已建立")
    yield
    connector.close()
    logger.info("Neo4j 连接已关闭")


app = FastAPI(
    title="汽车维修知识图谱 API",
    description="提供图谱查询、搜索、路径分析等接口",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
cfg = _load_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg["api"].get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由注册
app.include_router(graph.router,        prefix="/api/graph",  tags=["graph"])
app.include_router(search.router,       prefix="/api/search", tags=["search"])
app.include_router(path.router,         prefix="/api/path",   tags=["path"])
app.include_router(stats.router,        prefix="/api/stats",  tags=["stats"])
app.include_router(eval_route.router,   prefix="/api/eval",   tags=["eval"])


@app.get("/", tags=["health"])
async def health():
    return {"status": "ok", "service": "kg-repair-api"}
