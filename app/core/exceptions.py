class ApplicationError(Exception):
    """应用业务异常基类"""

    status_code: int = 500                # 默认状态码
    code: str = "APPLICATION_ERROR"       # 默认异常code
    message: str = "服务器内部错误"        # 默认异常提示





class ChatThreadNotFoundError(ApplicationError):
    """会话不存在或不属于当前用户"""

    status_code = 400
    code = "CHAT_THREAD_NOT_FOUND"
    message = "会话不存在或不属于当前用户"