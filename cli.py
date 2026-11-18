from __future__ import annotations

import argparse
import sys
from typing import Sequence

from zomboid import Item, ItemCatalog, ZomboidError


def print_items(items: Sequence[Item]) -> None:
    headers = ("ID", "Name", "Type", "Condition", "Amount")
    rows = [(str(i.id), i.name, i.type, i.condition, str(i.amount)) for i in items]
    widths = [max(len(h), *(len(r[n]) for r in rows)) if rows else len(h)
              for n, h in enumerate(headers)]
    line = lambda cells: "  ".join(c.ljust(w) for c, w in zip(cells, widths))
    print(line(headers))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print(line(row))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py", description="Zomboid Accounting System - облік предметів"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="вивести предмети посторінково")
    p.add_argument("file")
    p.add_argument("--page", type=int, default=1, help="номер сторінки (з 1)")
    p.add_argument("--page-size", type=int, default=20, help="предметів на сторінці")

    p = sub.add_parser("get", help="знайти предмети за ID")
    p.add_argument("file")
    p.add_argument("id", type=int)

    p = sub.add_parser("search", help="пошук предметів за назвою")
    p.add_argument("file")
    p.add_argument("query")
    p.add_argument("--exact", action="store_true", help="точний збіг назви")

    p = sub.add_parser("percent", help="відсоткове співвідношення за станом")
    p.add_argument("file")
    p.add_argument("--name", help="лише для предметів з цією назвою")
    p.add_argument("--exact", action="store_true", help="точний збіг назви")

    return parser


def run(args: argparse.Namespace) -> None:
    catalog = ItemCatalog.from_file(args.file)

    if args.command == "list":
        page = catalog.get_page(args.page, args.page_size)
        print_items(page.items)
        print(f"\nСторінка {page.page} з {page.total_pages} "
              f"(всього предметів: {page.total_items})")

    elif args.command == "get":
        items = catalog.get_by_id(args.id)
        if items:
            print_items(items)
        else:
            print(f"Предмет з ID {args.id} не знайдено")

    elif args.command == "search":
        items = catalog.search_by_name(args.query, exact=args.exact)
        if items:
            print_items(items)
        else:
            print(f"Нічого не знайдено за запитом '{args.query}'")

    elif args.command == "percent":
        shares = catalog.condition_percentages(args.name, exact=args.exact)
        if not shares:
            print("Немає даних для підрахунку")
        for condition, share in shares.items():
            print(f"{condition} — {share:.1f}%")


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(args)
    except (ZomboidError, OSError, ValueError) as exc:
        print(f"Помилка: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
