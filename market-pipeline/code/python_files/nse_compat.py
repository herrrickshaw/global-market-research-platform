"""NSE client that survives the www.nseindia.com -> www.nseindia.in move.

Since 2026-11-13 NSE answers every www.nseindia.com URL (the cookie page
/option-chain and all /api/* endpoints) with `301 -> www.nseindia.in`. The
pinned `nse` 4.0.1 client treats any non-2xx as fatal, so constructing NSE()
died in cookie setup and took the bhavcopy refresh and India scan with it.

Upstream fixed this in nse 5.x by switching its base URL, but 5.x also renamed
every public method (equityBhavcopy, listIndices, ... are gone), so upgrading
would break every caller. This shim keeps 4.0.1 and rewrites the host instead.
The archive host (nsearchives.nseindia.com) did not move and is left alone.

Use `from nse_compat import NSE` in place of `from nse import NSE`.
Delete this file once the callers are ported to nse >= 5.
"""
from nse import NSE  # noqa: F401  (re-exported)
from nse.transport import Transport

_OLD = "https://www.nseindia.com/"
_NEW = "https://www.nseindia.in/"

if not getattr(Transport, "_nse_in_patched", False):
    _orig_request = Transport.request

    def _request(self, url, params=None):
        if isinstance(url, str) and url.startswith(_OLD):
            url = _NEW + url[len(_OLD):]
        return _orig_request(self, url, params=params)

    Transport.request = _request
    Transport._nse_in_patched = True
    NSE.base_url = NSE.base_url.replace(_OLD, _NEW)
    NSE.next_api_url = NSE.next_api_url.replace(_OLD, _NEW)
