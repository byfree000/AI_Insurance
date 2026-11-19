
import asyncio
import sys

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

# Windows 使用支持异步子进程的事件循环
if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsProactorEventLoopPolicy()
    )

load_dotenv()


async def main():

    # 1. 初始化模型
    model = init_chat_model(
        model="deepseek-v4-flash",
        extra_body={"thinking": {"type": "disabled"}}
    )

    # 2. 初始化 MCP Client
    client = MultiServerMCPClient(
        {
            "time-mcp": {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "time-mcp"],
            },
            "12306-mcp": {
                "transport": "streamable_http",
                "url": "https://mcp.api-inference.modelscope.net/50719920b4f24d/mcp"
            }
        }
    )

    # 3. 获取 MCP 工具
    print("正在获取 MCP 工具...")

    tools = await client.get_tools()

    print("成功获取工具：")
    for tool in tools:
        print(tool.name, tool.description)

    # 4. 创建 Agent
    agent = create_agent(
        model=model,
        tools=tools
    )

    # 5. 调用 Agent
    print("正在调用 Agent...")

    response = await agent.ainvoke(
        {
            "messages": [
                HumanMessage(
                    content="帮我查一下下周四从北京到杭州的高铁"
                )
            ]
        }
    )

    print(response)


if __name__ == "__main__":
    asyncio.run(main())
