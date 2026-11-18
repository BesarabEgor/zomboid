from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Iterator


class ZomboidError(Exception):
    pass


class UnsupportedFormatError(ZomboidError):
    pass


class InvalidDataError(ZomboidError):
    pass


@dataclass(frozen=True)
class Item:
    id: int
    name: str
    type: str
    condition: str
    amount: int


@dataclass(frozen=True)
class Page:
    items: tuple[Item, ...]
    page: int
    page_size: int
    total_items: int

    @property
    def total_pages(self) -> int:
        if self.total_items == 0:
            return 0
        return -(-self.total_items // self.page_size)


class ItemReader(ABC):
    extensions: tuple[str, ...] = ()

    @abstractmethod
    def read(self, path: str) -> Iterator[Item]:
        pass


class CsvItemReader(ItemReader):
    extensions = (".csv",)
    REQUIRED_COLUMNS = ("id", "name", "type", "condition", "amount")

    def __init__(self, delimiter: str = ",", encoding: str = "utf-8-sig"):
        self.delimiter = delimiter
        self.encoding = encoding

    def read(self, path: str) -> Iterator[Item]:
        with open(path, newline="", encoding=self.encoding) as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            if reader.fieldnames is None:
                return
            columns = {name.strip().lower(): name for name in reader.fieldnames}
            missing = [c for c in self.REQUIRED_COLUMNS if c not in columns]
            if missing:
                raise InvalidDataError(
                    f"У файлі відсутні колонки: {', '.join(missing)}"
                )
            for row in reader:
                line = reader.line_num
                try:
                    yield Item(
                        id=int(row[columns["id"]]),
                        name=row[columns["name"]].strip(),
                        type=row[columns["type"]].strip(),
                        condition=row[columns["condition"]].strip(),
                        amount=int(row[columns["amount"]]),
                    )
                except (ValueError, TypeError, AttributeError) as exc:
                    raise InvalidDataError(
                        f"Некоректний рядок {line}: {dict(row)}"
                    ) from exc


_REGISTRY: dict[str, ItemReader] = {}


def register_reader(reader: ItemReader) -> None:
    for ext in reader.extensions:
        _REGISTRY[ext.lower()] = reader


def get_reader(path: str) -> ItemReader:
    ext = os.path.splitext(path)[1].lower()
    try:
        return _REGISTRY[ext]
    except KeyError:
        raise UnsupportedFormatError(f"Непідтримуваний формат файлу: {ext!r}")


register_reader(CsvItemReader())


class ItemCatalog:
    def __init__(self, items: Iterable[Item] = ()):
        self._items: list[Item] = []
        self._by_id: dict[int, list[Item]] = defaultdict(list)
        for item in items:
            self._items.append(item)
            self._by_id[item.id].append(item)

    @classmethod
    def from_file(cls, path: str, reader: ItemReader | None = None) -> "ItemCatalog":
        reader = reader or get_reader(path)
        return cls(reader.read(path))

    def __len__(self) -> int:
        return len(self._items)

    def get_page(self, page: int = 1, page_size: int = 20) -> Page:
        if page < 1:
            raise ValueError("Номер сторінки має бути >= 1")
        if page_size < 1:
            raise ValueError("Розмір сторінки має бути >= 1")
        start = (page - 1) * page_size
        chunk = self._items[start:start + page_size]
        return Page(tuple(chunk), page, page_size, len(self._items))

    def iter_pages(self, page_size: int = 20) -> Iterator[Page]:
        total = len(self._items)
        page = 1
        while (page - 1) * page_size < total:
            yield self.get_page(page, page_size)
            page += 1

    def get_by_id(self, item_id: int) -> list[Item]:
        return list(self._by_id.get(item_id, ()))

    def search_by_name(self, query: str, exact: bool = False) -> list[Item]:
        q = query.strip().lower()
        if not q:
            return []
        if exact:
            return [i for i in self._items if i.name.lower() == q]
        return [i for i in self._items if q in i.name.lower()]

    def condition_percentages(
        self, name: str | None = None, exact: bool = False
    ) -> dict[str, float]:
        items = self._items if name is None else self.search_by_name(name, exact)
        totals: dict[str, int] = defaultdict(int)
        for item in items:
            totals[item.condition] += item.amount
        grand_total = sum(totals.values())
        if grand_total == 0:
            return {}
        shares = {cond: amount * 100 / grand_total for cond, amount in totals.items()}
        return dict(sorted(shares.items(), key=lambda kv: -kv[1]))
