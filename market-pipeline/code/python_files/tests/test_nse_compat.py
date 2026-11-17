"""nse_compat must send www.nseindia.com traffic to www.nseindia.in (offline)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from nse.transport import Transport  # noqa: E402
from nse_compat import NSE  # noqa: E402


class _Resp:
    status_code = 200
    reason_phrase = "OK"


class _Session:
    def __init__(self):
        self.urls = []

    def get(self, url, params=None, timeout=None):
        self.urls.append(url)
        return _Resp()


def _transport():
    t = Transport.__new__(Transport)  # skip __init__: it fetches cookies over the network
    t.timeout = 1
    t._session = _Session()
    return t


def test_www_host_is_rewritten():
    t = _transport()
    t.request("https://www.nseindia.com/option-chain")
    t.request("https://www.nseindia.com/api/marketStatus")
    assert t._session.urls == [
        "https://www.nseindia.in/option-chain",
        "https://www.nseindia.in/api/marketStatus",
    ]


def test_archive_host_is_left_alone():
    t = _transport()
    url = "https://nsearchives.nseindia.com/content/cm/x.csv.zip"
    t.request(url)
    assert t._session.urls == [url]


def test_class_urls_point_at_new_host():
    assert NSE.base_url == "https://www.nseindia.in/api"
    assert NSE.next_api_url.startswith("https://www.nseindia.in/")
    assert NSE.archive_url == "https://nsearchives.nseindia.com"
