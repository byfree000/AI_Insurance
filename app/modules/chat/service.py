from asyncio import Lock
from collections.abc import AsyncIterator
from aiostream import stream as astream
from langgraph.graph.state import CompiledStateGraph
from fastapi.sse import ServerSentEvent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.stream import CustomTransformer
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import InsuranceAgentContext
from app.modules.chat.schemas import ChatRequest
from app.modules.chat_thread.exception import ChatThreadNotFoundError
from app.modules.chat_thread.repository import ChatThreadRepository


class ChatService:
    _thread_locks: dict[str, Lock] = {}

    def __init__(self, session: AsyncSession, agent: CompiledStateGraph,):
        self.repository = ChatThreadRepository(session)
        self.agent = agent

    async def _repair_unanswered_tool_calls(
        self,
        config: RunnableConfig,
    ) -> None:
        snapshot = await self.agent.aget_state(config)
        messages = snapshot.values.get("messages", [])
        pending: dict[str, str | None] = {}

        for message in messages:
            if isinstance(message, AIMessage):
                for tool_call in message.tool_calls:
                    tool_call_id = tool_call.get("id")
                    if tool_call_id:
                        pending[tool_call_id] = tool_call.get("name")
            elif isinstance(message, ToolMessage):
                pending.pop(message.tool_call_id, None)

        if pending:
            repair_messages = [
                ToolMessage(
                    tool_call_id=tool_call_id,
                    name=name,
                    status="error",
                    content=(
                        "工具执行状态未知：请求可能在执行过程中被中断。"
                        "请向用户确认是否需要重试，不要重复保存。"
                    ),
                )
                for tool_call_id, name in pending.items()
            ]
            snapshot = await self.agent.aget_state(config)

            print("========== Agent State ==========")
            print("Next:", snapshot.next)
            print("Metadata:", snapshot.metadata)
            print("Tasks:", snapshot.tasks)

            print("========== Messages ==========")
            for message in snapshot.values.get("messages", []):
                print(
                    type(message).__name__,
                    "id:", getattr(message, "id", None),
                    "tool_calls:", getattr(message, "tool_calls", None),
                    "tool_call_id:", getattr(message, "tool_call_id", None),
                )
            await self.agent.aupdate_state(
                config,
                {"messages": repair_messages},
                as_node="tools",
            )

    async def chat_stream(
        self,
        user_id: int,
        request: ChatRequest,
    ) -> AsyncIterator[ServerSentEvent]:
        # 1.校验会话是否属于当前用户
        thread = await self.repository.find_owned(
            request.thread_id,
            user_id,
        )
        if thread is None:
            raise ChatThreadNotFoundError

        # 2.校验通过后，调用Agent

        # 2.1.准备Agent输入
        _input = {"messages": [HumanMessage(content=request.message)]}
        config: RunnableConfig = {
            "configurable": {"thread_id": str(request.thread_id)}
        }
        context = InsuranceAgentContext(user_id=user_id)
        lock = self._thread_locks.setdefault(
            str(request.thread_id),
            Lock(),
        )

        async with lock:
            await self._repair_unanswered_tool_calls(config)

            # 2.2.使用v3协议获取异步事件流
            stream = await self.agent.astream_events(
                _input,
                config=config,
                context=context,
                version="v3",
                transformers=(CustomTransformer,),
            )
            # # 2.3.只读取消息中的文本增量
            # async def stream_messages():
            #     async for message in stream.messages:
            #         async for text in message.text:
            #             yield ServerSentEvent(data=text, event="message")

            # # 2.4.判断是否有custom事件
            # async def stream_custom():
            #     async for event in stream.extensions['custom']:
            #         if event.get('type') == 'additional_info':
            #             yield ServerSentEvent(data=event.get('data'), event="additional_info")
           
            async for event in stream:
                method = event['method']
                # 判断事件类型，可以是messages、interrupts等等
                if method == 'messages':
                    data = event['params']['data'][0]
                    if isinstance(data, AIMessage):
                        yield ServerSentEvent(data=data.text, event="message")
                    elif data.get('delta') and data['delta'].get('text'):
                        yield ServerSentEvent(data=data['delta'].get('text'), event="message")


            # # 2.5.合并Message处理和custom事件处理
            # merged = astream.merge(stream_messages(), stream_custom())
            # async with merged.stream() as streamer:
            #     async for event in streamer:
            #         yield event
        # 2.4.返回结束标识
        yield ServerSentEvent(data="[DONE]", event="done")