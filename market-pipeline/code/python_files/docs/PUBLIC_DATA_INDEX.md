# Public data index — what NSE / BSE / others actually expose

Every row was **probed**, not recalled. `status` is the result of this tool's own request; `shape` is the payload it got back. An endpoint listed as DEAD was tried and returned 404 — recorded so nobody re-derives it. Rebuild with `public_data_index.py --probe`.

🔴 **This is a lower bound, not a complete enumeration.** Neither NSE nor BSE publishes a machine-readable index of its own endpoints, so the candidate list is hand-assembled. It says *at least these exist* — never *only these exist*.

**53 endpoints probed · 39 live · 25 live and currently unused.**

## The gap — live, parseable, and nobody is reading it

This is the answer to "we only fetch what we need": everything below is available right now at no additional access cost.

| site | endpoint | category | what it gives | payload |
|---|---|---|---|---|
| bse | `bse-results-tab` | fundamentals | filed financial results | scalar str |
| bse | `bse-stock-trading` | microstructure | trading detail / market depth | object keys=['CktLimit', 'ExDate', 'MktCapFF', 'MktCapFull', 'TTQ', 'T |
| bse | `bse-advance-decline` | microstructure | advance/decline breadth | list[78] keys=['Advance', 'Advance_PER', 'DN', 'Decline', 'Decline_PER |
| bse | `bse-high-low` | microstructure | 52-week high/low hits | object keys=['Table', 'Table1'] max_list=128 |
| bse | `bse-quote` | prices | price series for a scrip | object keys=['CurrDate', 'CurrTime', 'CurrVal', 'Data', 'HighVal', 'Hi |
| bse | `bse-scrip-header` | prices | live quote header (O/H/L/C) | object keys=['Cmpname', 'CompResp', 'CurrRate', 'Header'] max_list=0 |
| bse | `bse-index-archive` | prices | daily close, every BSE index | object keys=['Table'] max_list=130 |
| bse | `bse-bhavcopy` | prices | official EOD bhavcopy CSV | application/octet-stream 835639b |
| bse | `bse-comheader` | reference | company header / industry | object keys=['CEPS', 'COName', 'COdetails', 'ConCEPS', 'ConEPS', 'ConN |
| nse | `nse-corp-info` | corp-actions | per-company announcements bundle | object keys=['borad_meeting', 'corporate_actions', 'financial_results' |
| nse | `nse-liveequity-deriv` | derivatives | live F&O board | object keys=['data', 'marketStatus', 'timestamp'] max_list=3 |
| nse | `nse-event-calendar` | disclosure | forthcoming corporate events | list[648] keys=['bm_desc', 'company', 'date', 'purpose', 'symbol'] |
| nse | `nse-large-deals` | flows | bulk / block / short deals | object keys=['BLOCK_DEALS', 'BLOCK_DEALS_DATA', 'BULK_DEALS', 'BULK_DE |
| nse | `nse-gainers` | microstructure | top gainers | object keys=['BANKNIFTY', 'FOSec', 'NIFTY', 'NIFTYNEXT50', 'SecGtr20', |
| nse | `nse-most-active` | microstructure | most active by value | object keys=['data', 'timestamp'] max_list=20 |
| nse | `nse-52w-high` | microstructure | 52-week high hits | object keys=['data', 'high', 'timestamp'] max_list=93 |
| nse | `nse-insider` | ownership | insider trading (PIT/SAST) | object keys=['acqNameList', 'data'] max_list=0 |
| nse | `nse-all-indices` | prices | live level+change for all indices | object keys=['advances', 'data', 'dates', 'declines', 'timestamp', 'un |
| nse | `nse-equity-master` | reference | index -> constituent-list names | object keys=['Broad Market Indices', 'Indices Eligible In Derivatives' |
| nse | `nse-index-names` | reference | every index NSE publishes | object keys=['nts', 'stn'] max_list=150 |
| nse | `nse-holiday-master` | reference | trading holiday calendar | object keys=['CBM', 'CD', 'CM', 'CMOT', 'COM', 'EGR', 'FO', 'IRD', 'MF |
| nse | `nse-market-status` | reference | open/closed per segment | object keys=['giftnifty', 'indicativenifty50', 'marketState', 'marketc |
| nse | `nse-sme-emerge` | segment | SME Emerge board | object keys=['adv', 'data', 'dec', 'marketStatus', 'noChg', 'timestamp |
| nse | `nse-ipo-current` | segment | live IPO issues | list[2] keys=['category', 'companyName', 'issueEndDate', 'issuePrice', |
| nse | `nse-debt-market` | segment | traded bonds | object keys=['adv', 'data', 'dec', 'filters', 'marketStatus', 'noChg', |

## Already wired in

Attribution greps our own `.py` files only — **never `.venv`**. The `nse` and `nsepython` packages name every NSE endpoint in their own source, so searching site-packages marked almost everything as used.

| site | endpoint | what it gives | consumed by |
|---|---|---|---|
| bse | `bse-announcements` | corporate announcements | `earnings_dates_bse.py,exchange_extras.py` |
| bse | `bse-corp-actions` | corporate actions (ex-dates) | `earnings_dates_bse.py,exchange_extras.py` |
| bse | `bse-forth-results` | forthcoming results calendar | `exchange_extras.py` |
| bse | `bse-scrip-list` | full active scrip master | `earnings_dates_bse.py` |
| nse | `nse-announcements` | every corporate announcement | `earnings_dates_bse.py` |
| nse | `nse-board-meetings` | board meeting calendar | `collect_board_meetings.py,earnings_dates_nse.py` |
| nse | `nse-corp-actions` | dividends, splits, bonus | `exchange_extras.py` |
| nse | `nse-fii-dii` | daily FII/DII cash buy/sell | `equity_ownership.py,nse_shareholding.py` |
| nse | `nse-fin-results` | quarterly results as filed | `earnings_dates_nse.py,nse_xbrl_results.py` |
| nse | `nse-shareholding` | promoter/public %, 22 quarters | `nse_shareholding.py,ownership_behaviour_india.py` |

### Unattributable

No path token distinctive enough to grep for, so usage is genuinely unknown — listed separately rather than counted as unused.

| site | endpoint | what it gives |
|---|---|---|
| nse | `nse-circulars` | exchange circulars |
| nse | `nse-mf-etf` | ETF board |
| other | `amfi-nav` | daily NAV, every MF scheme |
| other | `datagov-in` | data.gov.in dataset catalog |

## Not usable as an API (recorded so it is not re-attempted)

| site | endpoint | status | detail | what it would have given |
|---|---|---|---|---|
| nse | `nse-quote-equity` | AUTH/BLOCKED | http 403 | live quote + 52w + band |
| nse | `nse-quote-trade-info` | AUTH/BLOCKED | http 403 | delivery %, order book, VWAP |
| other | `mca-master` | AUTH/BLOCKED | http 403 | company master (CIN, status) |
| nse | `nse-eq-stockindices` | DEAD | http 404 | index constituents w/ live quote |
| nse | `nse-optionchain-idx` | DEAD | http 404 | index option chain w/ OI+IV |
| nse | `nse-quote-derivative` | DEAD | http 404 | futures/options quotes per underlying |
| other | `ibbi-cirp` | DEAD | http 404 | insolvency (CIRP) cases |
| bse | `bse-ann-subcat` | EMPTY | empty object | announcement category taxonomy |
| nse | `nse-optionchain-eq` | EMPTY | empty object | single-stock option chain |
| nse | `nse-historical-cm` | ERROR | http 503 | daily OHLCV history |
| other | `ccil-gsec` | ERROR | http 503 | G-sec / repo / forex benchmarks |
| other | `rbi-wss` | HTML | html 56118b, 1 table(s) | weekly statistical supplement |
| other | `sebi-fpi` | HTML-NOAPI | html 8203b, 0 table(s) | FPI investment statistics |
| other | `nsdl-fpi` | HTML-NOAPI | html 247b, 0 table(s) | FPI fortnightly AUC |

## Coverage by category

| category | live | unused |
|---|---|---|
| corp-actions | 3 | 1 |
| derivatives | 1 | 1 |
| disclosure | 5 | 1 |
| flows | 2 | 1 |
| fundamentals | 2 | 1 |
| funds | 1 | 0 |
| macro | 1 | 0 |
| microstructure | 6 | 6 |
| ownership | 2 | 1 |
| prices | 5 | 5 |
| reference | 6 | 5 |
| regulatory | 1 | 0 |
| segment | 4 | 3 |
