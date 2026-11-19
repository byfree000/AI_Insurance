
import asyncio
import selectors
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings


async def main():

    pool = AsyncConnectionPool(
        conninfo=settings.db.checkpoint_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )

    try:
        await pool.open()
        await pool.wait()

        print("数据库连接池初始化成功！")

        checkpointer = AsyncPostgresSaver(pool)

        await checkpointer.setup()

        print("LangGraph Checkpointer 初始化成功！")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(
        main(),
        loop_factory=lambda: asyncio.SelectorEventLoop(
            selectors.SelectSelector()
        )
    )
