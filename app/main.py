import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.routes import router
from app.core.database import init_db

# 让 app.* 下所有模块的 INFO 日志在 uvicorn 终端中可见
logging.getLogger("app").setLevel(logging.INFO)
logging.getLogger("app").addHandler(logging.StreamHandler())

# 确保目录在模块导入时就存在（mount 需要目录预先存在）
Path("uploads").mkdir(exist_ok=True)
Path("outputs").mkdir(exist_ok=True)
Path("static").mkdir(exist_ok=True)

app = FastAPI(
    title="Policy Documents Summary",
    description="政策文档智能摘要工具 API",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# API 路由优先注册，确保不被静态文件挂载覆盖
app.include_router(router, prefix="/api/v1")

# 挂载 outputs/ 目录供直接访问（可选，download 接口已覆盖）
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# 挂载前端静态文件，html=True 使 / 自动服务 index.html
app.mount("/", StaticFiles(directory="static", html=True), name="frontend")
