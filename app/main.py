from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.agents.insurance_advisor import init_insurance_agent
from app.core.config import settings
from app.core.exceptions import ApplicationError
from app.modules.chat.router import router as chat_router
from app.core.logging import configure_logging, get_logger
import uvicorn
import sys
from app.agents.orchestrator import init_insurance_orchestrator
from app.infra.checkpointer import (
    close_checkpointer,
    init_checkpointer,
)

# 初始化日志系统
configure_logging(settings.logging.level)
logger = get_logger(__name__)


from contextlib import asynccontextmanager

# 生命周期管理（预留）
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"【{settings.app.name}】应用启动中...")

    from app.infra.database import check_database, close_database
    from app.rag import close_rag # 导入模块就会初始化
    try:
        # 1.检查业务数据库连接
        await check_database()
        # 2.初始化Checkpointer
        checkpointer = await init_checkpointer()
          # 3.初始化保险顾问Agent
        app.state.agent = init_insurance_orchestrator(checkpointer)

        yield
    finally:
        logger.info("应用关闭中... ")
        # 关闭RAG组件
        close_rag()
        # 3.关闭Checkpointer连接池
        await close_checkpointer()
        # 4.关闭SQLAlchemy连接池
        await close_database()
         # 4.关闭RAG资源
        

app = FastAPI(
    title=settings.app.name,
    debug=settings.app.debug,
    lifespan=lifespan,
)

@app.exception_handler(ApplicationError)
async def handle_application_error(
    request: Request,
    exc: ApplicationError, # 捕获到的异常（这里用自定义异常基类捕获，所有业务异常都会匹配到）
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code, # 异常中自带status
        content={
            "code": exc.code,        # 异常中自带code
            "message": exc.message,  # 异常中自带message
        },
    )
from app.modules.product.router import router as product_router

# 创建 app 后注册路由
app.include_router(product_router)

@app.get("/health", summary="健康检测接口")
async def health_check() -> dict[str, str]:
    logger.info("执行健康检查")
    return {"status": "ok"}

from app.modules.chat_thread.router import router as chat_thread_router

app.include_router(chat_thread_router)


app.include_router(chat_router)

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=False,
        loop= "asyncio:SelectorEventLoop" if sys.platform == "win32" else "auto",
    )