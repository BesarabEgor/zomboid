# Zomboid Accounting System

Облік предметів першої необхідності з `.csv` таблиць.

| Файл | Що це |
|---|---|
| `zomboid.py` | Бібліотека: читає CSV, шукає, рахує відсотки |
| `cli.py` | Те саме через термінал |
| `api.py` | Сервер (REST API), який також показує сайт |
| `index.html` | Сайт (React) |
| `items.csv` | Приклад даних |
| `test_library.py` | Тести |
| `class-diagram.md` | Діаграма класів |

## Що потрібно

Python 3 і:

```bash
pip install fastapi uvicorn httpx pytest
```

Сайт працює в браузері з інтернетом (React підключається з cdnjs).

## Як користуватись

### Командний рядок

```bash
python cli.py list items.csv                   # всі предмети по сторінках
python cli.py get items.csv 2                  # предмет за ID
python cli.py search items.csv nail            # пошук за назвою
python cli.py percent items.csv                # відсотки за станом для всіх
python cli.py percent items.csv --name Nails   # відсотки для одного предмета
```

### Сервер і сайт

```bash
python api.py items.csv
```

Сайт: http://127.0.0.1:8000

### Тести

```bash
python -m pytest
```
