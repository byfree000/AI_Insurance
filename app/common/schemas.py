

from typing import Generic, TypeVar

from pydantic import BaseModel


class BaseSchema(BaseModel):
    """基础响应结果"""


T=TypeVar("T", bound=BaseModel)


class PageResult(BaseSchema, Generic[T]):
    """分页响应结果"""

 
    items: list[T]
    page:int 
    page_size:int
    total:int