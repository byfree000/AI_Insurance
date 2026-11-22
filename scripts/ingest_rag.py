import asyncio
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_milvus import BM25BuiltInFunction, Milvus


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from app.core.config import settings
from app.core.logging import get_logger
from app.infra.database import AsyncSessionFactory, close_database
from app.modules.product.service import ProductService
from app.rag.pipeline import RAGPipeline


logger = get_logger(__name__)


async def ingest_rag() -> None:
    load_dotenv(APP_ROOT / ".env")

    embeddings = DashScopeEmbeddings(
        model="text-embedding-v4",
        dashscope_api_key=os.getenv("DASHSCOPE_API_KEY"),
    )
    vector_store = Milvus(
        embedding_function=embeddings,
        collection_name="insurance_collection",
        builtin_function=BM25BuiltInFunction(
            analyzer_params={"type": "chinese"},
        ),
        vector_field=["dense", "sparse"],
        connection_args={"uri": settings.rag.milvus_url},
        auto_id=True,
    )
    pipeline = RAGPipeline(vector_store)

    try:
        async with AsyncSessionFactory() as session:
            service = ProductService(session)
            products = await service.list_products()

        logger.info("开始构建RAG知识库", product_count=len(products))
        for index, product in enumerate(products, start=1):
            logger.info(
                "正在处理保险产品",
                index=index,
                product_count=len(products),
                product_id=product.id,
                clause_name=product.clause_name,
            )
            await pipeline.ingest(product)

        logger.info("RAG知识库构建完成", product_count=len(products))
    finally:
        pipeline.close()
        await close_database()


if __name__ == "__main__":
    asyncio.run(ingest_rag())