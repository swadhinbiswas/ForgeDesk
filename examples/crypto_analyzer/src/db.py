# In-memory DB for demonstration without locking complexities
# In a real app, use sqlite3 or SQLAlchemy

_portfolio = []
_id_counter = 1


def init_db():
    global _portfolio, _id_counter
    _portfolio = [
        {"id": 1, "symbol": "BTC", "amount": 0.5, "buy_price": 50000},
        {"id": 2, "symbol": "ETH", "amount": 10.0, "buy_price": 2500},
    ]
    _id_counter = 3


def get_portfolio_items():
    return _portfolio


def add_item(symbol: str, amount: float, buy_price: float):
    global _id_counter, _portfolio
    item = {"id": _id_counter, "symbol": symbol.upper(), "amount": amount, "buy_price": buy_price}
    _portfolio.append(item)
    _id_counter += 1
    return item["id"]


def remove_item(item_id: int):
    global _portfolio
    _portfolio = [item for item in _portfolio if item["id"] != item_id]
