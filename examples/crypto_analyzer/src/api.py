import db


def register_routes(app):

    @app.command("get_portfolio")
    def get_portfolio():
        return db.get_portfolio_items()

    @app.command("add_portfolio_item")
    def add_portfolio_item(symbol: str, amount: float, buy_price: float):
        id = db.add_item(symbol, amount, buy_price)
        return {"success": True, "id": id}

    @app.command("remove_portfolio_item")
    def remove_portfolio_item(id: int):
        db.remove_item(id)
        return {"success": True}

    @app.command("get_market_snapshot")
    def get_market_snapshot():
        import requests

        try:
            # Using CoinGecko public API
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    "ids": "bitcoin,ethereum,solana,cardano,ripple",
                    "vs_currencies": "usd",
                    "include_24hr_change": "true",
                },
                timeout=5,
            )
            return r.json()
        except Exception as e:
            return {"error": str(e)}
