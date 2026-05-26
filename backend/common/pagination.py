"""通用分页参数 — 所有列表接口使用统一的 PaginationParams。"""

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """通用分页参数。

    Usage:
        @app.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """
    page: int = Field(1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(20, ge=1, le=100, description="每页条数，最大 100")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginatedResponse(BaseModel):
    """分页响应包装器。"""
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int = 0

    def model_post_init(self, __context):
        if self.total_pages == 0:
            self.total_pages = max(1, (self.total + self.page_size - 1) // self.page_size)
