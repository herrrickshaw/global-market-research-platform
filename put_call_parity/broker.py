"""
broker.py
=========
Broker adapter layer.  Provides a unified interface over Zerodha Kite,
Upstox v2, and Angel SmartAPI so the strategy code stays broker-agnostic.

Install:
    pip install kiteconnect upstox-python-sdk smartapi-python
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------
class BrokerBase(ABC):
    """Minimal interface required by the strategy."""

    @abstractmethod
    def login(self) -> None: ...

    @abstractmethod
    def get_quote(self, instruments: List[str]) -> Dict[str, Any]: ...

    @abstractmethod
    def get_option_chain(self, underlying: str, expiry: str, exchange: str) -> List[Dict]: ...

    @abstractmethod
    def place_order(
        self,
        tradingsymbol: str,
        exchange: str,
        transaction_type: str,   # "BUY" | "SELL"
        quantity: int,
        order_type: str,          # "MARKET" | "LIMIT" | "SL"
        price: float = 0.0,
        trigger_price: float = 0.0,
        product: str = "NRML",
        tag: str = "",
    ) -> str: ...                 # returns order_id

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]: ...

    # 🔴 NOT abstract, deliberately — this closes a hole rather than opening one.
    #
    # strategy.py did `broker.kite.instruments(seg) if hasattr(broker, "kite") else []`
    # in BOTH _get_futures_quote and _get_futures_symbol. That reach-through is why
    # UpstoxBroker and AngelBroker have never been able to price a parity trade:
    # they have no `.kite`, so the list was silently [], fut_list came back empty,
    # and _get_futures_quote returned None. Parity needs F in (C-P) = (F-K)e^(-rT),
    # so "no futures price" means the whole signal cannot be computed — a failure
    # that looked like "no opportunities found" rather than "this broker is unwired".
    #
    # Made concrete with an empty default ON PURPOSE: an abstractmethod here would
    # break Upstox/Angel at import, converting a silent gap into an outage. The
    # default returns exactly what those two already got, so nothing regresses,
    # while Kite and OpenAlgo now return real contracts.
    def get_futures_contracts(self, underlying: str, exchange: str) -> List[Dict[str, Any]]:
        """Futures contracts for `underlying`, newest expiry first.

        Each row must carry at least: name, instrument_type ("FUT"), expiry
        (YYYY-MM-DD string), tradingsymbol. That is the subset strategy.py
        filters on; returning anything less will silently drop the contract.
        """
        log.warning("%s does not implement get_futures_contracts — futures "
                    "lookup will find nothing and parity cannot be priced",
                    type(self).__name__)
        return []

    def get_expiries(self, underlying: str, exchange: str,
                     instrument_type: str = "options") -> List[str]:
        """Available expiries as YYYY-MM-DD strings, nearest first.

        🔴 THE MOST LOAD-BEARING OF THE THREE. _nearest_expiries() feeds the
        whole scan loop: an empty list here means there is nothing to iterate,
        so no chain is ever fetched and no signal can exist. This was the third
        `broker.kite` reach-through, and the reason a non-Kite broker produced
        an entirely empty run rather than a wrong one.

        Empty default for the same reason as get_futures_contracts: matches what
        Upstox/Angel already get, so nothing regresses.
        """
        log.warning("%s does not implement get_expiries — the scan loop has "
                    "nothing to iterate and will find no opportunities",
                    type(self).__name__)
        return []


# ---------------------------------------------------------------------------
# Zerodha Kite Connect adapter
# ---------------------------------------------------------------------------
class KiteBroker(BrokerBase):
    def __init__(self):
        from kiteconnect import KiteConnect
        api_key   = os.environ.get("KITE_API_KEY", "")
        api_secret = os.environ.get("KITE_API_SECRET", "")
        access_token = os.environ.get("KITE_ACCESS_TOKEN", "")

        self.kite = KiteConnect(api_key=api_key)
        if access_token:
            self.kite.set_access_token(access_token)
        self._api_secret = api_secret

    def login(self) -> None:
        """Interactive login — generates and sets access token."""
        import webbrowser
        url = self.kite.login_url()
        print(f"Open this URL and complete login:\n{url}")
        webbrowser.open(url)
        request_token = input("Paste the request_token from the redirect URL: ").strip()
        data = self.kite.generate_session(request_token, api_secret=self._api_secret)
        self.kite.set_access_token(data["access_token"])
        os.environ["KITE_ACCESS_TOKEN"] = data["access_token"]
        log.info("Kite login successful")

    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        return self.kite.quote(instruments)

    def get_option_chain(self, underlying: str, expiry: str, exchange: str) -> List[Dict]:
        """
        Fetch all option strikes for given underlying and expiry.
        Returns list of dicts with keys: strike, instrument_type, tradingsymbol,
        last_price, bid, ask, oi, volume, instrument_token.
        """
        instruments = self.kite.instruments(exchange)
        chain = [
            i for i in instruments
            if i["name"] == underlying
            and i["expiry"].strftime("%Y-%m-%d") == expiry
            and i["instrument_type"] in ("CE", "PE")
        ]
        if not chain:
            return []
        # Enrich with live quotes
        tokens = [f"{exchange}:{i['tradingsymbol']}" for i in chain]
        quotes = {}
        # Kite quote API accepts max 500 instruments
        for batch_start in range(0, len(tokens), 500):
            batch = tokens[batch_start: batch_start + 500]
            quotes.update(self.kite.quote(batch))
        result = []
        for inst in chain:
            sym = f"{exchange}:{inst['tradingsymbol']}"
            q = quotes.get(sym, {})
            depth = q.get("depth", {})
            bid = depth.get("buy", [{}])[0].get("price", 0.0)
            ask = depth.get("sell", [{}])[0].get("price", 0.0)
            result.append({
                "strike": inst["strike"],
                "instrument_type": inst["instrument_type"],
                "tradingsymbol": inst["tradingsymbol"],
                "last_price": q.get("last_price", 0.0),
                "bid": bid,
                "ask": ask,
                "oi": q.get("oi", 0),
                "volume": q.get("volume", 0),
                "instrument_token": inst["instrument_token"],
                "exchange": exchange,
            })
        return result

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity,
                    order_type, price=0.0, trigger_price=0.0,
                    product="NRML", tag="") -> str:
        from kiteconnect import KiteConnect
        kwargs = dict(
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            transaction_type=transaction_type,
            quantity=quantity,
            order_type=order_type,
            product=product,
            tag=tag,
        )
        if order_type in ("LIMIT", "SL"):
            kwargs["price"] = price
        if order_type == "SL":
            kwargs["trigger_price"] = trigger_price
        order_id = self.kite.place_order(variety=KiteConnect.VARIETY_REGULAR, **kwargs)
        log.info("Order placed: %s %s %s x%d -> %s", transaction_type, tradingsymbol, order_type, quantity, order_id)
        return str(order_id)

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        orders = self.kite.orders()
        for o in orders:
            if str(o["order_id"]) == order_id:
                return o
        return {}

    def cancel_order(self, order_id: str) -> None:
        from kiteconnect import KiteConnect
        self.kite.cancel_order(variety=KiteConnect.VARIETY_REGULAR, order_id=order_id)

    def get_positions(self) -> List[Dict[str, Any]]:
        pos = self.kite.positions()
        return pos.get("net", [])

    def get_futures_contracts(self, underlying: str, exchange: str) -> List[Dict[str, Any]]:
        """The instrument-master lookup strategy.py used to do by reaching into
        `.kite` directly. Same query, now behind the interface so every broker
        can answer it — and so Kite keeps working unchanged after the call site
        moved off the reach-through.

        Expiry is normalised to a YYYY-MM-DD string here rather than at the call
        site: kiteconnect returns a datetime.date, other brokers return text, and
        comparing those two forms is what the old inline `hasattr(expiry,
        'strftime')` dance existed to paper over.
        """
        rows = []
        for i in self.kite.instruments(exchange):
            if i.get("name") != underlying or i.get("instrument_type") != "FUT":
                continue
            exp = i.get("expiry")
            rows.append({
                "name": i.get("name"),
                "instrument_type": "FUT",
                "tradingsymbol": i.get("tradingsymbol"),
                "expiry": exp.strftime("%Y-%m-%d") if hasattr(exp, "strftime") else str(exp),
                "instrument_token": i.get("instrument_token"),
                "lot_size": i.get("lot_size"),
                "exchange": exchange,
            })
        rows.sort(key=lambda x: x["expiry"])
        return rows

    def get_expiries(self, underlying: str, exchange: str,
                     instrument_type: str = "options") -> List[str]:
        want = {"options": ("CE", "PE"), "futures": ("FUT",)}[instrument_type]
        seen = set()
        for i in self.kite.instruments(exchange):
            if i.get("name") != underlying or i.get("instrument_type") not in want:
                continue
            exp = i.get("expiry")
            seen.add(exp.strftime("%Y-%m-%d") if hasattr(exp, "strftime") else str(exp))
        return sorted(seen)


# ---------------------------------------------------------------------------
# Upstox v2 adapter
# ---------------------------------------------------------------------------
class UpstoxBroker(BrokerBase):
    def __init__(self):
        import upstox_client
        self._client = upstox_client
        cfg = upstox_client.Configuration()
        cfg.access_token = os.environ.get("UPSTOX_ACCESS_TOKEN", "")
        self._api_client = upstox_client.ApiClient(cfg)

    def login(self) -> None:
        raise NotImplementedError("Complete Upstox OAuth2 flow in a browser, then set UPSTOX_ACCESS_TOKEN env var.")

    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        import upstox_client
        api = upstox_client.MarketQuoteApi(self._api_client)
        symbol_str = ",".join(instruments)
        resp = api.get_full_market_quote(symbol_str, "v2")
        return resp.data or {}

    def get_option_chain(self, underlying: str, expiry: str, exchange: str) -> List[Dict]:
        import upstox_client
        api = upstox_client.OptionsApi(self._api_client)
        resp = api.get_option_contracts(underlying, expiry, "v2")
        if not resp or not resp.data:
            return []
        result = []
        for item in resp.data:
            result.append({
                "strike": item.strike_price,
                "instrument_type": item.instrument_type,
                "tradingsymbol": item.tradingsymbol,
                "last_price": item.last_price or 0.0,
                "bid": 0.0,
                "ask": 0.0,
                "oi": item.oi or 0,
                "volume": item.volume or 0,
                "instrument_token": item.instrument_key,
                "exchange": exchange,
            })
        return result

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity,
                    order_type, price=0.0, trigger_price=0.0,
                    product="NRML", tag="") -> str:
        import upstox_client
        api = upstox_client.OrderApi(self._api_client)
        body = upstox_client.PlaceOrderRequest(
            quantity=quantity,
            product=product,
            validity="DAY",
            price=price,
            tag=tag,
            instrument_token=tradingsymbol,
            order_type=order_type,
            transaction_type=transaction_type,
            disclosed_quantity=0,
            trigger_price=trigger_price,
            is_amo=False,
        )
        resp = api.place_order(body, "v2")
        return resp.data.order_id

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        import upstox_client
        api = upstox_client.OrderApi(self._api_client)
        resp = api.get_order_details(order_id, "v2")
        return resp.data.__dict__ if resp.data else {}

    def cancel_order(self, order_id: str) -> None:
        import upstox_client
        upstox_client.OrderApi(self._api_client).cancel_order(order_id, "v2")

    def get_positions(self) -> List[Dict[str, Any]]:
        import upstox_client
        resp = upstox_client.PortfolioApi(self._api_client).get_positions("v2")
        return [p.__dict__ for p in (resp.data or [])]


# ---------------------------------------------------------------------------
# Angel SmartAPI adapter
# ---------------------------------------------------------------------------
class AngelBroker(BrokerBase):
    def __init__(self):
        import pyotp
        from SmartApi import SmartConnect
        api_key   = os.environ.get("ANGEL_API_KEY", "")
        client_id = os.environ.get("ANGEL_CLIENT_ID", "")
        password  = os.environ.get("ANGEL_PASSWORD", "")
        totp_secret = os.environ.get("ANGEL_TOTP_SECRET", "")

        self.obj = SmartConnect(api_key=api_key)
        totp = pyotp.TOTP(totp_secret).now()
        data = self.obj.generateSession(client_id, password, totp)
        self._token = data["data"]["jwtToken"]

    def login(self) -> None:
        log.info("Angel login handled in __init__ via TOTP.")

    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        # instruments expected as list of "exchange:symbol"
        payload = [{"exchange": s.split(":")[0], "symboltoken": s.split(":")[1], "interval": "ONE_MINUTE"} for s in instruments]
        resp = self.obj.getMarketData("FULL", payload)
        return resp.get("data", {})

    def get_option_chain(self, underlying: str, expiry: str, exchange: str) -> List[Dict]:
        resp = self.obj.getOptionChainByExpiry(underlying, exchange, expiry)
        if not resp or not resp.get("data"):
            return []
        result = []
        for row in resp["data"]:
            for opt_type in ("CE", "PE"):
                d = row.get(opt_type, {})
                if not d:
                    continue
                result.append({
                    "strike": row["strikePrice"],
                    "instrument_type": opt_type,
                    "tradingsymbol": d.get("tradingsymbol", ""),
                    "last_price": d.get("ltp", 0.0),
                    "bid": d.get("bidprice", 0.0),
                    "ask": d.get("askprice", 0.0),
                    "oi": d.get("opnInterest", 0),
                    "volume": d.get("volume", 0),
                    "instrument_token": d.get("symboltoken", ""),
                    "exchange": exchange,
                })
        return result

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity,
                    order_type, price=0.0, trigger_price=0.0,
                    product="NRML", tag="") -> str:
        params = {
            "variety": "NORMAL",
            "tradingsymbol": tradingsymbol,
            "symboltoken": tradingsymbol,
            "transactiontype": transaction_type,
            "exchange": exchange,
            "ordertype": order_type,
            "producttype": product,
            "duration": "DAY",
            "price": str(price),
            "squareoff": "0",
            "stoploss": "0",
            "quantity": str(quantity),
        }
        resp = self.obj.placeOrder(params)
        return resp.get("data", {}).get("orderid", "")

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        orders = self.obj.orderBook()
        for o in (orders.get("data") or []):
            if str(o.get("orderid")) == order_id:
                return o
        return {}

    def cancel_order(self, order_id: str) -> None:
        self.obj.cancelOrder(order_id, "NORMAL")

    def get_positions(self) -> List[Dict[str, Any]]:
        resp = self.obj.position()
        return resp.get("data") or []


# ---------------------------------------------------------------------------
# OpenAlgo adapter — one HTTP contract in front of 35 brokers
# ---------------------------------------------------------------------------
class OpenAlgoBroker(BrokerBase):
    """Talks to a self-hosted OpenAlgo instance (https://docs.openalgo.in).

    WHY THIS EXISTS. The three adapters above each hand-roll a different SDK,
    and only one of them (Kite) is actually wired for futures lookup. OpenAlgo
    normalises 35 brokers behind one REST contract, so a single adapter reaches
    all of them — including the Upstox and Angel accounts whose own adapters
    here cannot price a parity trade today.

    🔴 NO SESSION TO MANAGE. Unlike Kite/Upstox/Angel, OpenAlgo authenticates
    per-request with an apikey in the JSON body; the broker OAuth dance happens
    once inside the OpenAlgo web UI, not here. That is the point — this process
    never handles broker credentials, only a key to a service the operator runs.

    Config comes from the environment so nothing lands in config.py:
        OPENALGO_URL      default http://127.0.0.1:5000
        OPENALGO_APIKEY   required
    """

    QUOTE_KEY_SEP = ":"          # strategy.py keys quotes as "EXCHANGE:SYMBOL"

    def __init__(self):
        self.base = os.environ.get("OPENALGO_URL", "http://127.0.0.1:5000").rstrip("/")
        self.apikey = os.environ.get("OPENALGO_APIKEY", "")
        self.strategy_tag = os.environ.get("OPENALGO_STRATEGY", "put_call_parity")
        self._session = None

    # -- transport ----------------------------------------------------------

    def _post(self, path: str, payload: Dict[str, Any], tries: int = 3) -> Dict[str, Any]:
        """POST with backoff on THROTTLING ONLY.

        Same rule as price_sources._get: 429/5xx are retried, 4xx comes straight
        back. A 4xx here means "wrong symbol" or "bad key" — permanent answers
        that retrying would only multiply against the operator's own broker
        rate limit, which is shared with the orders this strategy has to place.
        """
        import random
        import requests
        if self._session is None:
            self._session = requests.Session()
        body = dict(payload, apikey=self.apikey)
        last = None
        for attempt in range(tries):
            try:
                r = self._session.post(f"{self.base}/api/v1/{path}", json=body, timeout=15)
            except Exception as exc:                                   # noqa: BLE001
                last = exc
                if attempt == tries - 1:
                    raise
                time.sleep((2 ** attempt) + random.uniform(0, 0.4))
                continue
            if r.status_code == 429 or 500 <= r.status_code < 600:
                if attempt == tries - 1:
                    r.raise_for_status()
                time.sleep(min((2 ** attempt) + random.uniform(0, 0.4), 20))
                continue
            r.raise_for_status()
            out = r.json()
            # OpenAlgo returns HTTP 200 with {"status": "error"} for domain
            # failures, so a bare raise_for_status() would let those through as
            # success and hand the caller an empty dict to misread.
            if isinstance(out, dict) and out.get("status") == "error":
                raise RuntimeError(f"openalgo {path}: {out.get('message', 'error')}")
            return out
        raise last if last else RuntimeError("unreachable")

    @staticmethod
    def _expiry_to_chain_format(expiry: str) -> str:
        """'10-JUL-25' or '2025-07-10' -> '10JUL25'.

        🔴 THE TWO ENDPOINTS DISAGREE. /expiry and /search return DD-MMM-YY with
        hyphens; /optionchain wants DDMMMYY without them. Passing one to the
        other returns an empty chain and no error, which reads as "no strikes
        for this expiry" — indistinguishable from a genuine holiday gap.
        """
        import datetime as _dt
        e = expiry.strip().upper()
        for fmt in ("%d-%b-%y", "%Y-%m-%d", "%d%b%y"):
            try:
                return _dt.datetime.strptime(e, fmt).strftime("%d%b%y").upper()
            except ValueError:
                continue
        return e.replace("-", "")

    @staticmethod
    def _expiry_to_iso(expiry: str) -> str:
        """'10-JUL-25' -> '2025-07-10'. strategy.py compares expiries as ISO."""
        import datetime as _dt
        e = expiry.strip().upper()
        for fmt in ("%d-%b-%y", "%d%b%y", "%Y-%m-%d"):
            try:
                return _dt.datetime.strptime(e, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return expiry

    # -- interface ----------------------------------------------------------

    def login(self) -> None:
        """No session to establish — verify the key instead of pretending.

        A no-op login would defer an invalid key to the first order, which is
        the worst possible moment to discover it.
        """
        if not self.apikey:
            raise RuntimeError("OPENALGO_APIKEY is not set — refusing to start "
                               "with an unauthenticated client")
        self._post("positionbook", {})          # cheapest authenticated call
        log.info("OpenAlgo reachable at %s, key accepted", self.base)

    def get_quote(self, instruments: List[str]) -> Dict[str, Any]:
        """Quotes keyed 'EXCHANGE:SYMBOL', shaped like Kite's response.

        🔴 MERGES TWO ENDPOINTS. /quotes has bid/ask scalars but NO depth ladder
        and no oi; strategy.py reads data['depth']['buy'][0]['price'] and falls
        back to last_price. Returning only /quotes would make every leg silently
        fall back to LTP, turning a spread-aware parity check into a mid-less
        one — the deviation would then be measured against a price nobody can
        actually trade at. So depth is fetched too and mapped into Kite's shape.
        """
        out: Dict[str, Any] = {}
        for key in instruments:
            exchange, _, symbol = key.partition(self.QUOTE_KEY_SEP)
            if not symbol:
                exchange, symbol = "NSE", key
            try:
                q = self._post("quotes", {"symbol": symbol, "exchange": exchange}).get("data", {})
            except Exception as exc:                                   # noqa: BLE001
                log.warning("openalgo quote failed for %s: %s", key, exc)
                continue
            depth_buy, depth_sell, oi = [], [], 0
            try:
                d = self._post("depth", {"symbol": symbol, "exchange": exchange}).get("data", {})
                depth_buy = [{"price": b.get("price", 0), "quantity": b.get("quantity", 0)}
                             for b in (d.get("bids") or [])]
                depth_sell = [{"price": a.get("price", 0), "quantity": a.get("quantity", 0)}
                              for a in (d.get("asks") or [])]
                oi = d.get("oi", 0) or 0
            except Exception as exc:                                   # noqa: BLE001
                # Depth is an enhancement, not a precondition: without it the
                # caller falls back to last_price exactly as it does for a
                # broker that returns no ladder. Losing the quote entirely
                # because the ladder failed would be the worse trade.
                log.debug("openalgo depth unavailable for %s: %s", key, exc)
            out[key] = {
                "last_price": q.get("ltp", 0.0),
                "ohlc": {"open": q.get("open", 0.0), "high": q.get("high", 0.0),
                         "low": q.get("low", 0.0), "close": q.get("prev_close", 0.0)},
                "volume": q.get("volume", 0),
                "oi": oi,
                "depth": {"buy": depth_buy, "sell": depth_sell},
                # Preserve the scalars too: they are the broker's own top-of-book
                # and may be fresher than the ladder's first level.
                "bid": q.get("bid", 0.0),
                "ask": q.get("ask", 0.0),
            }
        return out

    def get_option_chain(self, underlying: str, expiry: str, exchange: str) -> List[Dict]:
        """Flat CE/PE rows, matching the shape KiteBroker returns.

        🔴 FLATTENED ON PURPOSE. OpenAlgo returns strikes PAIRED as
        {strike, ce{...}, pe{...}}, which is genuinely nicer for parity — the
        two legs arrive already matched. But strategy.py consumes the flat
        Kite-style list, and changing the contract to suit one adapter would
        break the other three. The pairing is re-derived downstream by strike;
        flattening here keeps this a drop-in.
        """
        payload = {"underlying": underlying, "exchange": exchange,
                   "expiry_date": self._expiry_to_chain_format(expiry)}
        data = self._post("optionchain", payload)
        rows: List[Dict] = []
        for entry in data.get("chain") or []:
            strike = entry.get("strike")
            for side, itype in (("ce", "CE"), ("pe", "PE")):
                leg = entry.get(side) or {}
                if not leg:
                    continue
                rows.append({
                    "strike": strike,
                    "instrument_type": itype,
                    "tradingsymbol": leg.get("symbol"),
                    "last_price": leg.get("ltp", 0.0),
                    "bid": leg.get("bid", 0.0),
                    "ask": leg.get("ask", 0.0),
                    "oi": leg.get("oi", 0),
                    "volume": leg.get("volume", 0),
                    # OpenAlgo has no numeric instrument_token; the symbol IS the
                    # identifier for every downstream call. Emitting None here
                    # would look like a token that failed to resolve.
                    "instrument_token": leg.get("symbol"),
                    "lot_size": leg.get("lotsize"),
                    "exchange": exchange,
                })
        return rows

    def get_futures_contracts(self, underlying: str, exchange: str) -> List[Dict[str, Any]]:
        """Futures contracts via /search — the hole the Kite reach-through left."""
        data = self._post("search", {"query": f"{underlying} FUT", "exchange": exchange})
        rows = []
        for r in data.get("data") or []:
            if r.get("instrumenttype") != "FUT" or r.get("name") != underlying:
                continue
            rows.append({
                "name": r.get("name"),
                "instrument_type": "FUT",
                "tradingsymbol": r.get("symbol"),
                "expiry": self._expiry_to_iso(r.get("expiry", "")),
                "instrument_token": r.get("token"),
                "lot_size": r.get("lotsize"),
                "exchange": exchange,
            })
        rows.sort(key=lambda x: x["expiry"])
        return rows

    def get_expiries(self, underlying: str, exchange: str,
                     instrument_type: str = "options") -> List[str]:
        """Via /expiry, which returns DD-MMM-YY sorted nearest-first.

        Normalised to ISO here so strategy.py can compare expiries as plain
        strings across every adapter — the old inline `hasattr(exp, 'strftime')`
        branch existed only because Kite returned dates and others returned text.
        """
        data = self._post("expiry", {"symbol": underlying, "exchange": exchange,
                                     "instrumenttype": instrument_type})
        return sorted(self._expiry_to_iso(e) for e in (data.get("data") or []))

    def place_order(self, tradingsymbol, exchange, transaction_type, quantity,
                    order_type, price=0.0, trigger_price=0.0,
                    product="NRML", tag="") -> str:
        payload = {
            "strategy": tag or self.strategy_tag,
            "symbol": tradingsymbol,
            "exchange": exchange,
            "action": transaction_type.upper(),          # BUY | SELL
            "quantity": str(int(quantity)),
            # OpenAlgo spells SL-M with a hyphen; the strategy's "SL" maps to a
            # plain stop-loss limit, so pass it through unchanged rather than
            # guessing that a bare SL means SL-M.
            "pricetype": order_type.upper(),             # MARKET | LIMIT | SL | SL-M
            "product": product.upper(),                  # MIS | CNC | NRML
        }
        if price:
            payload["price"] = str(price)
        if trigger_price:
            payload["trigger_price"] = str(trigger_price)
        resp = self._post("placeorder", payload)
        return str(resp.get("orderid", ""))

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        return self._post("orderstatus", {"orderid": order_id,
                                          "strategy": self.strategy_tag}).get("data", {})

    def cancel_order(self, order_id: str) -> None:
        self._post("cancelorder", {"orderid": order_id, "strategy": self.strategy_tag})

    def get_positions(self) -> List[Dict[str, Any]]:
        return self._post("positionbook", {}).get("data") or []


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_broker(broker: str = "kite") -> BrokerBase:
    mapping = {
        "kite":     KiteBroker,
        "upstox":   UpstoxBroker,
        "angel":    AngelBroker,
        "openalgo": OpenAlgoBroker,
    }
    cls = mapping.get(broker.lower())
    if cls is None:
        raise ValueError(f"Unknown broker '{broker}'. Choose from: {list(mapping)}")
    return cls()
