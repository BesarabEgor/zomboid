from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from zomboid import Item, ItemCatalog

INDEX_HTML = Path(__file__).with_name("index.html")


class ItemSchema(BaseModel):
    id: int
    name: str
    type: str
    condition: str
    amount: int


class PageSchema(BaseModel):
    items: list[ItemSchema]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _to_schema(item: Item) -> ItemSchema:
    return ItemSchema(**asdict(item))


def create_app(data_file: str) -> FastAPI:
    catalog = ItemCatalog.from_file(data_file)
    app = FastAPI(title="Zomboid Accounting System", version="1.0")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(INDEX_HTML)

    @app.get("/items", response_model=PageSchema, summary="Предмети посторінково")
    def list_items(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=1000),
    ):
        result = catalog.get_page(page, page_size)
        return PageSchema(
            items=[_to_schema(i) for i in result.items],
            page=result.page,
            page_size=result.page_size,
            total_items=result.total_items,
            total_pages=result.total_pages,
        )

    @app.get("/items/search", response_model=list[ItemSchema],
             summary="Пошук предметів за назвою")
    def search_items(
        name: str = Query(..., min_length=1),
        exact: bool = False,
    ):
        return [_to_schema(i) for i in catalog.search_by_name(name, exact=exact)]

    @app.get("/items/{item_id}", response_model=list[ItemSchema],
             summary="Предмет за ID (усі стани)")
    def get_item(item_id: int):
        items = catalog.get_by_id(item_id)
        if not items:
            raise HTTPException(status_code=404, detail=f"Предмет з ID {item_id} не знайдено")
        return [_to_schema(i) for i in items]

    @app.get("/stats/conditions", response_model=dict[str, float],
             summary="Відсоткове співвідношення за станом")
    def condition_stats(name: str | None = Query(None, min_length=1), exact: bool = False):
        shares = catalog.condition_percentages(name, exact=exact)
        return {cond: round(share, 1) for cond, share in shares.items()}

    return app


if __name__ == "__main__":
    import uvicorn

    if len(sys.argv) != 2:
        sys.exit("Використання: python api.py items.csv")
    uvicorn.run(create_app(sys.argv[1]), host="127.0.0.1", port=8000)
