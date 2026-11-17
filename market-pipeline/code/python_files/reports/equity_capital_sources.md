# Who actually buys stocks — capital sources by market

Literature and public-source review of **where the money that buys equities comes from**,
per market, and how much of it is debt-financed. Companion to the bond/carry studies:
those asked what moves prices; this asks who supplies the demand.

**Sourcing note.** Figures below are marked ⓟ primary (regulator/central bank/industry
body: Fed Z.1, SEBI, AMFI, FINRA, BoJ, NPS, JPX/KRX) or ⓢ secondary (press or broker
commentary reporting those figures). Nothing here has been recomputed from raw data —
this is a literature review, not a measurement. The measurement plan is §6.

---

## 1. The distinction that matters: savings vs leverage

Your framing — "DII and FII exist in India but that money is sourced via debt, retail
investors and other sources" — needs one split made explicit, because the two behave
completely differently under stress:

| layer | what it is | behaviour in a drawdown |
|---|---|---|
| **Intermediated household savings** | SIPs, provident funds, insurance premiums, 401(k) | **Sticky.** Contributions are payroll-linked and continue through drawdowns |
| **Debt-financed positions** | margin/MTF, F&O, loan-against-securities | **Reflexive.** Margin calls force selling into weakness, amplifying the move |
| **Corporate self-purchase** | buybacks | Discretionary; falls when cash flow or credit tightens |

Most DII money is **not** debt — it is household savings intermediated through funds,
insurers and provident funds. The debt sits *on top*, as a leveraged retail overlay. That
distinction is the whole point: the first layer is why drawdowns get absorbed, the second
is why they sometimes accelerate.

---

## 2. India — domestic savings displaced foreign money

**The ownership crossover.** DII holdings reached ₹71.76 lakh crore, ~2% above FII
holdings, with the FII:DII ownership ratio falling below 1 to **0.98** as of 31 Mar 2025 ⓢ.
DII net investment hit **₹6 trillion in CY2025**, the highest calendar year since BSE
began the series in 2007 ⓢ.

**The absorption event.** Apr 2025 – Apr 2026: **₹3.8 lakh crore of FII net selling was
more than offset by ₹8.85 lakh crore of DII buying**, and the Nifty held ⓢ (NSE + AMFI
data). This is the single clearest demonstration that the domestic bid now sets the
marginal price in India.

**Where the DII money comes from:**

| source | scale | character |
|---|---|---|
| **SIP flows** ⓟ AMFI | ₹3,17,502 crore FY2025-26 (to Feb 2026), ~7× the ₹43,921 crore of FY2016-17; ~₹31,100 crore in Apr 2026 alone | Monthly, automated, payroll-linked — the stickiest component |
| **EPFO / NPS** | retirement savings with a mandated equity allocation | Contractual inflow, near-insensitive to price |
| **Insurance (LIC)** | share to 3.72% at 31 Mar 2025 from 3.51%; net buy ₹34,435 crore, highest in 5 years ⓢ | Premium-funded, long-horizon |

**The debt-financed overlay:**

- **MTF (Margin Trading Facility)** — broker lends against a position. SEBI caps funding
  at 50% of trade value with 50% investor margin, restricted to Group 1 stocks; interest
  ~0.04–0.05%/day, i.e. **14–18% annualised** ⓟ SEBI. Marketed as 4–5× buying power;
  industry figures have publicly flagged the pace of MTF growth ⓢ.
- **F&O** — SEBI's *Analysis of Profit and Loss of Individual Traders dealing in equity
  F&O* (25 Jan 2023, FY2021-22 data) ⓟ is the authoritative study on retail derivatives
  outcomes, and later SEBI work extended it. This is notional leverage rather than
  borrowed cash, but the forced-exit dynamic is the same.
- **Loan against securities** — smaller, less well documented publicly.

**Reading:** India's equity bid is now dominated by intermediated household savings, with
leverage as a cyclical accelerant rather than the base. The vulnerability is not that
"DII money is debt" — it mostly is not — but that the *marginal* buyer in a momentum
phase increasingly is.

---

## 3. United States — the buyer is the issuer

The US answer is structurally different from every other market here: **corporate
buybacks are the largest single source of net equity demand**, with commentary going as
far as arguing buybacks account for essentially the entire net demand over the last two
decades ⓢ. Households and institutions rebalance; corporates retire float.

| source | note |
|---|---|
| **Buybacks** | Largest net demand; discretionary, pro-cyclical, credit-sensitive |
| **Retirement / 401(k)** ⓟ ICI | 54 million active DC participants; payroll-linked and increasingly passive. One study finds a 10% rise in instrumented 401(k) stock demand associated with a **3.6%** price rise ⓢ |
| **Households direct** ⓟ Fed Z.1 | The canonical measurement is Fed Z.1 (`BOGZ1LM193064005A` etc. on FRED) |
| **Foreign** | Large and rising; Z.1 rest-of-world sector |

**Leverage:** FINRA margin debt — reported monthly under **FINRA Rule 4521** ⓟ, the
cleanest single read on equity leverage — stood at **~$1.502 trillion (Jun 2026)**,
reported as **102.8% above its long-term average** and **+49% year over year** ⓢ. Whatever
one thinks of the level, the *rate of change* is the part that matters for forced-selling
risk.

---

## 4. Japan — the central bank as shareholder

Japan is the one market where the state is a direct equity owner at scale. The **BoJ
overtook GPIF as the largest owner of Japanese stocks** (¥45.1tn vs ¥44.8tn at
end-November of the reported year) ⓢ, built through ETF purchases. GPIF remains the
world's largest pension fund ⓟ.

Retail is resurgent: individuals were **~25% of stock trading by value in FY2025, the
highest in 12 years** ⓢ, with individual holdings around **¥170.5tn (FY2023)** ⓢ. Foreign
investors have long dominated *turnover* even while owning a minority of the float — a
distinction that matters, since price is set by trading, not holding.

---

## 5. Korea — the most retail-driven major market

- **NPS**: third-largest pension fund globally, >$900bn; equities passed **50% of total
  assets for the first time** (14.8% domestic + 36.8% overseas as of end-August), with a
  target of **55% by 2030** ⓢ. Note the split — NPS is increasingly a buyer of *foreign*
  equities, not Korean ones.
- **Retail**: **64% of annual transaction value** ⓢ — the highest of any major market,
  against ~30% in the US and Japan. Korean retail has also been rotating into US equities ⓢ.

Korea is the cleanest case of retail setting the marginal price, and correspondingly the
market where leverage and sentiment dynamics dominate.

**Europe** is the gap in this review — the searches surfaced far less. European equity
demand is typically characterised as pension/insurance-led with low direct retail
participation, but I have no primary figure to cite and will not invent one.

---

## 6. What could actually be measured from here

Everything above is literature. These sources are machine-retrievable and would turn it
into data, in rough order of effort:

| market | series | source | access |
|---|---|---|---|
| US | Z.1 sector holdings of corporate equities | Fed / FRED | FRED API (key already in the store) |
| US | margin debt (Rule 4521) | FINRA | monthly publication |
| India | daily FII / DII cash-segment activity | NSE / BSE | public daily files |
| India | monthly SIP inflow, AUM | AMFI | public monthly release |
| India | FPI assets under custody | NSDL | public |
| Japan | trading value by investor type | JPX | weekly public series |
| Korea | trading value by investor type | KRX | public |

The single highest-value build is the **India FII/DII + AMFI SIP pair**: daily flow
against monthly savings inflow would let us test directly whether the domestic bid is
what absorbed the 2025-26 FII selling, rather than taking the press figure on trust.

---

*Literature review of public sources. Figures are as reported by the cited bodies and
have not been independently recomputed here. Not investment advice.*
