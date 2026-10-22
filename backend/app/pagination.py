from collections.abc import Sequence

from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


class PaginatedResponse[T](BaseModel):
    items: Sequence[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = {"from_attributes": True}
