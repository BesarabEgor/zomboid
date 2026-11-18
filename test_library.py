import pytest
from fastapi.testclient import TestClient

from api import create_app
from cli import main
from zomboid import (
    CsvItemReader, InvalidDataError, Item, ItemCatalog, ItemReader,
    UnsupportedFormatError, get_reader, register_reader,
)


SAMPLE = """ID,Name,Type,Condition,Amount
1,Hummer,Tool,Mint,10
2,Nails,Fasteners,Good,450
2,Nails,Fasteners,Bad,100
3,Canned Beans,Food,Good,80
4,Bandage,Medicine,Average,35
5,Water Bottle,Drink,Mint,60
"""


@pytest.fixture
def csv_path(tmp_path):
    path = tmp_path / "items.csv"
    path.write_text(SAMPLE, encoding="utf-8")
    return str(path)


@pytest.fixture
def catalog(csv_path):
    return ItemCatalog.from_file(csv_path)


def test_reads_all_rows(csv_path):
    items = list(CsvItemReader().read(csv_path))
    assert len(items) == 6
    assert items[0] == Item(1, "Hummer", "Tool", "Mint", 10)


def test_handles_bom_and_header_case(tmp_path):
    path = tmp_path / "bom.csv"
    path.write_text("id,NAME,Type,Condition,amount\n7,Axe,Tool,Good,3\n", encoding="utf-8-sig")
    assert list(CsvItemReader().read(str(path))) == [Item(7, "Axe", "Tool", "Good", 3)]


def test_missing_column_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("ID,Name\n1,Axe\n", encoding="utf-8")
    with pytest.raises(InvalidDataError, match="відсутні колонки"):
        list(CsvItemReader().read(str(path)))


def test_non_numeric_amount_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("ID,Name,Type,Condition,Amount\n1,Axe,Tool,Good,many\n", encoding="utf-8")
    with pytest.raises(InvalidDataError, match="рядок 2"):
        list(CsvItemReader().read(str(path)))


def test_empty_file_gives_no_items(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8")
    assert list(CsvItemReader().read(str(path))) == []


def test_get_reader_by_extension():
    assert isinstance(get_reader("x.CSV"), CsvItemReader)


def test_unknown_extension_raises():
    with pytest.raises(UnsupportedFormatError):
        get_reader("items.json")


def test_len(catalog):
    assert len(catalog) == 6


def test_first_page(catalog):
    page = catalog.get_page(1, 4)
    assert [i.id for i in page.items] == [1, 2, 2, 3]
    assert page.total_items == 6
    assert page.total_pages == 2


def test_last_partial_page(catalog):
    page = catalog.get_page(2, 4)
    assert [i.id for i in page.items] == [4, 5]


def test_page_out_of_range_is_empty(catalog):
    assert catalog.get_page(99, 4).items == ()


@pytest.mark.parametrize("page,size", [(0, 10), (-1, 10), (1, 0)])
def test_invalid_page_args(catalog, page, size):
    with pytest.raises(ValueError):
        catalog.get_page(page, size)


def test_iter_pages_covers_everything(catalog):
    pages = list(catalog.iter_pages(page_size=4))
    assert len(pages) == 2
    assert sum(len(p.items) for p in pages) == 6


def test_empty_catalog_pagination():
    page = ItemCatalog().get_page(1, 10)
    assert page.items == () and page.total_pages == 0


def test_large_catalog_pagination():
    items = (Item(i, f"Item {i}", "T", "Good", 1) for i in range(150_000))
    catalog = ItemCatalog(items)
    page = catalog.get_page(1500, 100)
    assert page.total_pages == 1500
    assert page.items[0].id == 149_900


def test_get_by_id_single(catalog):
    assert [i.name for i in catalog.get_by_id(1)] == ["Hummer"]


def test_get_by_id_returns_all_conditions(catalog):
    assert {i.condition for i in catalog.get_by_id(2)} == {"Good", "Bad"}


def test_get_by_id_missing(catalog):
    assert catalog.get_by_id(999) == []


def test_search_case_insensitive_substring(catalog):
    assert {i.id for i in catalog.search_by_name("NAIL")} == {2}


def test_search_exact(catalog):
    assert catalog.search_by_name("nail", exact=True) == []
    assert len(catalog.search_by_name("nails", exact=True)) == 2


def test_search_blank_query(catalog):
    assert catalog.search_by_name("   ") == []


def test_custom_reader_can_be_plugged_in(tmp_path):
    class FakeJsonReader(ItemReader):
        extensions = (".fake",)

        def read(self, path):
            yield Item(1, "Fake", "Test", "Mint", 1)

    register_reader(FakeJsonReader())
    path = tmp_path / "data.fake"
    path.write_text("")
    catalog = ItemCatalog.from_file(str(path))
    assert catalog.get_by_id(1)[0].name == "Fake"


def test_percentages_all_items(catalog):
    shares = catalog.condition_percentages()
    assert shares["Good"] == pytest.approx(530 * 100 / 735)
    assert shares["Mint"] == pytest.approx(70 * 100 / 735)
    assert sum(shares.values()) == pytest.approx(100)


def test_percentages_sorted_descending(catalog):
    values = list(catalog.condition_percentages().values())
    assert values == sorted(values, reverse=True)


def test_percentages_by_name(catalog):
    shares = catalog.condition_percentages(name="Nails")
    assert shares == {"Good": pytest.approx(450 * 100 / 550), "Bad": pytest.approx(100 * 100 / 550)}


def test_percentages_by_name_exact(catalog):
    assert catalog.condition_percentages(name="nail", exact=True) == {}


def test_percentages_empty():
    assert ItemCatalog().condition_percentages() == {}


def test_cli_list(csv_path, capsys):
    assert main(["list", csv_path, "--page", "2", "--page-size", "4"]) == 0
    out = capsys.readouterr().out
    assert "Bandage" in out and "Hummer" not in out
    assert "Сторінка 2 з 2" in out


def test_cli_get(csv_path, capsys):
    assert main(["get", csv_path, "2"]) == 0
    out = capsys.readouterr().out
    assert out.count("Nails") == 2


def test_cli_get_missing(csv_path, capsys):
    assert main(["get", csv_path, "999"]) == 0
    assert "не знайдено" in capsys.readouterr().out


def test_cli_search(csv_path, capsys):
    assert main(["search", csv_path, "bean"]) == 0
    assert "Canned Beans" in capsys.readouterr().out


def test_cli_percent_all(csv_path, capsys):
    assert main(["percent", csv_path]) == 0
    out = capsys.readouterr().out
    assert "Good — 72.1%" in out


def test_cli_percent_by_name(csv_path, capsys):
    assert main(["percent", csv_path, "--name", "Nails"]) == 0
    out = capsys.readouterr().out
    assert "Good — 81.8%" in out and "Bad — 18.2%" in out


def test_cli_missing_file_returns_error(capsys):
    assert main(["list", "no_such_file.csv"]) == 1
    assert "Помилка" in capsys.readouterr().err


def test_cli_unknown_format_returns_error(tmp_path, capsys):
    path = tmp_path / "items.xyz"
    path.write_text("")
    assert main(["list", str(path)]) == 1
    assert "Помилка" in capsys.readouterr().err


@pytest.fixture
def client(csv_path):
    return TestClient(create_app(csv_path))


def test_api_list_default(client):
    r = client.get("/items")
    assert r.status_code == 200
    body = r.json()
    assert body["total_items"] == 6 and body["page"] == 1 and body["total_pages"] == 1
    assert body["items"][0] == {
        "id": 1, "name": "Hummer", "type": "Tool", "condition": "Mint", "amount": 10
    }


def test_api_list_pagination(client):
    body = client.get("/items", params={"page": 2, "page_size": 4}).json()
    assert [i["id"] for i in body["items"]] == [4, 5]
    assert body["total_pages"] == 2


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 5000}])
def test_api_list_invalid_params(client, params):
    assert client.get("/items", params=params).status_code == 422


def test_api_get_by_id(client):
    r = client.get("/items/2")
    assert r.status_code == 200
    assert {i["condition"] for i in r.json()} == {"Good", "Bad"}


def test_api_get_by_id_not_found(client):
    r = client.get("/items/999")
    assert r.status_code == 404
    assert "999" in r.json()["detail"]


def test_api_search(client):
    r = client.get("/items/search", params={"name": "NAIL"})
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_api_search_exact_no_match(client):
    r = client.get("/items/search", params={"name": "nail", "exact": "true"})
    assert r.status_code == 200 and r.json() == []


def test_api_search_requires_name(client):
    assert client.get("/items/search").status_code == 422


def test_api_condition_stats_all(client):
    r = client.get("/stats/conditions")
    assert r.status_code == 200
    assert r.json()["Good"] == 72.1


def test_api_condition_stats_by_name(client):
    assert client.get("/stats/conditions", params={"name": "Nails"}).json() == {
        "Good": 81.8, "Bad": 18.2
    }


def test_api_missing_data_file_fails_fast():
    with pytest.raises(OSError):
        create_app("no_such_file.csv")
