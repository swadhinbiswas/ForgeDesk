import threading
import time

import requests

import forge


def worker_loop(app: forge.App):
    # Fetch data every 30 seconds
    last_prices = {}

    while True:
        try:
            # CoinGecko ids
            coins = "bitcoin,ethereum,solana"
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coins, "vs_currencies": "usd", "include_24hr_change": "true"},
                timeout=5,
            )

            data = r.json()

            # Simple alert logic
            for coin, info in data.items():
                if coin in last_prices:
                    old_price = last_prices[coin]["usd"]
                    new_price = info["usd"]

                    # 5% change alert
                    if abs(new_price - old_price) / old_price > 0.05:
                        forge.notification(
                            title="Crypto Price Alert",
                            body=f"{coin.capitalize()} moved significantly! Now ${new_price}",
                        )
                last_prices[coin] = info

            # Emit to frontend (ipc/events depending on Forge version)
            # Standard forge events emit
            if hasattr(forge, "events") and hasattr(forge.events, "emit"):
                forge.events.emit("market-update", data)
            elif hasattr(app, "emit"):
                app.emit("market-update", data)

        except Exception:
            pass

        time.sleep(30)


def start_worker(app: forge.App):
    thread = threading.Thread(target=worker_loop, args=(app,), daemon=True)
    thread.start()
