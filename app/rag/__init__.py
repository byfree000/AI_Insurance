from langchain_milvus import BM25BuiltInFunction, Milvus

from app.core.config import settings
from app.rag.pipeline import RAGPipeline
from app.rag.retriever import ParentChunkRetriever

from langchain_ollama import OllamaEmbeddings
from langchain_milvus import Milvus, BM25BuiltInFunction
from app.core.config import settings
import os
from dotenv import load_dotenv
from langchain_community.embeddings import DashScopeEmbeddings

load_dotenv()

_embeddings = DashScopeEmbeddings(
    model="text-embedding-v4",
    dashscope_api_key=os.getenv("DASHSCOPE_API_KEY")
)


# 2.初始化VectorStore
_vector_store = Milvus(
    embedding_function=_embeddings,
    collection_name="insurance_collection",
    builtin_function=BM25BuiltInFunction(
        analyzer_params={"type": "chinese"}
    ),
    vector_field=["dense", "sparse"],
    connection_args={"uri": settings.rag.milvus_url},
    auto_id=True,
)

# 3.创建模块级Pipeline和Retriever
pipeline = RAGPipeline(_vector_store)
retriever = ParentChunkRetriever(_vector_store)


def close_rag() -> None:
    """关闭RAG组件"""
    pipeline.close()
    _vector_store.client.close()

__all__ = ['pipeline', 'retriever', 'close_rag']