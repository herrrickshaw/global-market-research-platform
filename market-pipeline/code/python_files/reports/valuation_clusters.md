# Valuation clustering — over/under-priced vs same-profile peers

Peers are learned by clustering on **business economics** (ROE, ROCE, margins, growth, asset turnover, leverage, FCF yield) — not GICS sectors. Within each peer cluster, PE & PB are z-scored (robust); `valuation_z` > +1.5 = OVERPRICED vs same-profile peers, < −1.5 = UNDERPRICED. Markets with fundamentals: IN/US/KR.

## INDIA — 1179 stocks, 8 peer clusters

**UNDERPRICED vs peers (cheap for their economics):**
```
  ZUARI AGRO CHEMICALS LTD PE    1.0 PB   0.4 ROE  44.0% val_z -1.3
  GIC HOUSING FINANCE LTD  PE    5.1 PB   0.4 ROE   7.3% val_z -1.3
  ASHOKA BUILDCON LTD      PE    1.3 PB   0.5 ROE  38.8% val_z -1.3
  MUKAND LTD.              PE    3.3 PB   1.3 ROE  39.7% val_z -1.3
  SPIC LTD                 PE    6.2 PB   1.0 ROE  15.4% val_z -1.2
  BRIGHTCOM GROUP LIMITED  PE    2.0 PB   0.2 ROE   9.1% val_z -1.2
  REPCO HOME FINANCE LTD   PE    5.1 PB   0.6 ROE  11.8% val_z -1.2
  TAMILNADU NEWSPRT & PAPE PE    4.2 PB   0.5 ROE  10.7% val_z -1.2
  INDIAN OIL CORP LTD      PE    4.7 PB   0.9 ROE  19.2% val_z -1.2
  GHCL LIMITED             PE    8.4 PB   1.1 ROE  13.3% val_z -1.1
  DEN NETWORKS LTD         PE    7.8 PB   0.3 ROE   4.4% val_z -1.1
  LIC HOUSING FINANCE LTD  PE    5.2 PB   0.7 ROE  13.5% val_z -1.1
```

**OVERPRICED vs peers (expensive for their economics):**
```
  SBC EXPORTS LIMITED      PE   79.4 PB  25.0 ROE  31.5% val_z +9.9
  MTAR Technologies Limite PE  192.1 PB  22.0 ROE  11.4% val_z +9.5
  AVANTEL LIMITED          PE  291.5 PB  12.9 ROE   4.4% val_z +8.5
  SCHNEIDER ELECTRIC INFRA PE  150.9 PB  41.4 ROE  27.4% val_z +8.2
  RHETAN TMT LIMITED       PE  221.1 PB  21.0 ROE   9.5% val_z +8.0
  PRATAAP SNACKS LIMITED   PE  274.2 PB   3.8 ROE   1.4% val_z +7.7
  TVS MOTOR COMPANY  LTD   PE   61.7 PB  19.5 ROE  31.6% val_z +7.3
  ADANI GREEN ENERGY LTD   PE  137.6 PB  11.4 ROE   8.3% val_z +7.1
  WESTLIFE FOODWORLD LTD   PE  230.4 PB  12.0 ROE   5.2% val_z +7.0
  TITAN COMPANY LIMITED    PE   82.2 PB  26.6 ROE  32.3% val_z +6.3
  HITACHI ENERGY INDIA LTD PE  144.7 PB  27.6 ROE  19.1% val_z +6.1
  HIND RECTIFIER LIMITED   PE   98.1 PB  21.2 ROE  21.6% val_z +5.7
```

**★ Best value (underpriced AND high-ROE within cluster):**
```
  MUKAND LTD.              PE    3.3 PB   1.3 ROE  39.7% val_z -1.3
  TAMILNADU NEWSPRT & PAPE PE    4.2 PB   0.5 ROE  10.7% val_z -1.2
  INDIAN OIL CORP LTD      PE    4.7 PB   0.9 ROE  19.2% val_z -1.2
  LIC HOUSING FINANCE LTD  PE    5.2 PB   0.7 ROE  13.5% val_z -1.1
  HINDUSTAN PETROLEUM CORP PE    4.5 PB   1.3 ROE  27.5% val_z -1.1
  DILIP BUILDCON LIMITED   PE    4.8 PB   0.9 ROE  19.1% val_z -1.1
  PRAKASH INDUSTRIES LTD   PE    6.6 PB   0.6 ROE   9.3% val_z -1.1
  BHARAT PETROLEUM CORP  L PE    5.2 PB   1.3 ROE  25.8% val_z -1.1
```

## US — 534 stocks, 8 peer clusters

**UNDERPRICED vs peers (cheap for their economics):**
```
  Rubico Inc.              PE    0.3 PB   0.0 ROE   5.8% val_z -1.5
  Chatterbox Technologies  PE    6.8 PB   2.1 ROE  31.1% val_z -1.5
  Performance Shipping Inc PE    0.4 PB   0.1 ROE  15.5% val_z -1.5
  Next Technology Holding  PE    0.0 PB   0.0 ROE  31.4% val_z -1.4
  Palladyne AI Corp.       PE    0.1 PB   0.0 ROE  13.4% val_z -1.4
  ASIA PACIFIC WIRE & CABL PE    1.8 PB   0.1 ROE   6.8% val_z -1.3
  Ridgetech Inc.           PE    0.8 PB   0.3 ROE  34.4% val_z -1.3
  Lucas GC Ltd             PE    3.5 PB   0.1 ROE   3.1% val_z -1.2
  AMERICAN FINANCIAL GROUP PE    1.8 PB   0.3 ROE  17.5% val_z -1.2
  AMERICAN FINANCIAL GROUP PE    2.0 PB   0.4 ROE  17.5% val_z -1.2
  CITIGROUP INC            PE    3.5 PB   0.2 ROE   6.7% val_z -1.2
  ENERGIZER HOLDINGS, INC. PE    5.8 PB   8.2 ROE 140.7% val_z -1.2
```

**OVERPRICED vs peers (expensive for their economics):**
```
  Fortress Biotech, Inc.   PE  226.9 PB  31.0 ROE  13.7% val_z +13.6
  BrightSpring Health Serv PE  231.0 PB  23.5 ROE  10.2% val_z +12.0
  VIAVI SOLUTIONS INC.     PE  267.3 PB  11.9 ROE   4.5% val_z +9.1
  ADVANCED MICRO DEVICES I PE  201.6 PB  13.9 ROE   6.9% val_z +7.9
  GE Vernova Inc.          PE   57.0 PB  24.9 ROE  43.7% val_z +7.5
  TERADYNE, INC            PE  104.3 PB  20.7 ROE  19.8% val_z +7.4
  GENUINE PARTS CO         PE  249.6 PB   3.7 ROE   1.5% val_z +7.3
  Everpure, Inc.           PE  131.1 PB  17.1 ROE  13.0% val_z +7.1
  STMicroelectronics N.V.  PE  286.2 PB   2.7 ROE   0.9% val_z +6.8
  Vishay Precision Group,  PE  251.1 PB   4.0 ROE   1.6% val_z +6.3
  Phreesia, Inc.           PE  259.0 PB   1.8 ROE   0.7% val_z +5.9
  Himax Technologies, Inc. PE  162.2 PB   9.9 ROE   6.1% val_z +5.8
```

**★ Best value (underpriced AND high-ROE within cluster):**
```
  Next Technology Holding  PE    0.0 PB   0.0 ROE  31.4% val_z -1.4
  Palladyne AI Corp.       PE    0.1 PB   0.0 ROE  13.4% val_z -1.4
  Ridgetech Inc.           PE    0.8 PB   0.3 ROE  34.4% val_z -1.3
  AMERICAN FINANCIAL GROUP PE    1.8 PB   0.3 ROE  17.5% val_z -1.2
  AMERICAN FINANCIAL GROUP PE    2.0 PB   0.4 ROE  17.5% val_z -1.2
  ENERGIZER HOLDINGS, INC. PE    5.8 PB   8.2 ROE 140.7% val_z -1.2
  CLEANSPARK, INC.         PE    0.3 PB   0.0 ROE  16.8% val_z -1.2
  Western Union CO         PE    5.2 PB   2.7 ROE  52.2% val_z -1.1
```

## KOREA — 1470 stocks, 8 peer clusters

**UNDERPRICED vs peers (cheap for their economics):**
```
  INVENI                   PE    0.9 PB   0.1 ROE  13.4% val_z -1.3
  KG케미칼                    PE    1.1 PB   0.1 ROE   6.2% val_z -1.3
  파라택시스이더리움                PE    1.2 PB   0.2 ROE  12.7% val_z -1.3
  F&F홀딩스                   PE    1.4 PB   0.1 ROE  10.1% val_z -1.3
  포스코스틸리온                  PE    1.4 PB   0.1 ROE   4.7% val_z -1.3
  KG에코솔루션                  PE    1.4 PB   0.1 ROE   5.9% val_z -1.3
  아이디스홀딩스                  PE    1.9 PB   0.2 ROE   8.8% val_z -1.2
  미원화학                     PE    0.9 PB   0.1 ROE  14.2% val_z -1.2
  동국홀딩스                    PE    2.5 PB   0.0 ROE   1.1% val_z -1.2
  서연                       PE    1.8 PB   0.1 ROE   5.8% val_z -1.2
  삼정펄프                     PE    2.1 PB   0.2 ROE  10.9% val_z -1.1
  크라운해태홀딩스                 PE    2.4 PB   0.1 ROE   5.5% val_z -1.1
```

**OVERPRICED vs peers (expensive for their economics):**
```
  현대무벡스                    PE  194.6 PB  13.7 ROE   7.0% val_z +31.7
  바이오다인                    PE  289.7 PB   5.6 ROE   1.9% val_z +25.1
  주성엔지니어링                  PE  214.5 PB  13.0 ROE   6.0% val_z +24.5
  큐에이드                     PE  142.6 PB  18.0 ROE  12.6% val_z +23.8
  삼성전기                     PE  142.8 PB  10.7 ROE   7.5% val_z +23.8
  케어젠                      PE  147.3 PB  13.9 ROE   9.5% val_z +23.1
  삼천당제약                    PE  298.0 PB   9.9 ROE   3.3% val_z +22.5
  타이거일렉                    PE   90.7 PB   8.2 ROE   9.0% val_z +16.8
  테크윙                      PE  190.3 PB   8.1 ROE   4.2% val_z +16.5
  대덕전자                     PE  123.5 PB   6.6 ROE   5.3% val_z +16.3
  에스피지                     PE  200.6 PB   7.1 ROE   3.5% val_z +15.4
  에쎈테크                     PE  196.3 PB   2.9 ROE   1.5% val_z +15.0
```

**★ Best value (underpriced AND high-ROE within cluster):**
```
  INVENI                   PE    0.9 PB   0.1 ROE  13.4% val_z -1.3
  파라택시스이더리움                PE    1.2 PB   0.2 ROE  12.7% val_z -1.3
  미원화학                     PE    0.9 PB   0.1 ROE  14.2% val_z -1.2
  삼정펄프                     PE    2.1 PB   0.2 ROE  10.9% val_z -1.1
  유니온                      PE    1.7 PB   0.3 ROE  19.7% val_z -1.1
  한진중공업홀딩스                 PE    2.2 PB   0.3 ROE  13.0% val_z -1.1
  계룡건설                     PE    1.7 PB   0.2 ROE   9.9% val_z -1.1
  하림지주                     PE    2.0 PB   0.2 ROE   8.2% val_z -1.1
```

## Discovered peer archetypes (India clusters)

| cluster | n | med ROE | med net-margin | med growth | med PE | med PB |
|---|--:|--:|--:|--:|--:|--:|
| 0 | 74 | 12% | 15% | 14% | 21 | 2.4 |
| 1 | 163 | 15% | 4% | 15% | 25 | 3.6 |
| 2 | 74 | 12% | 12% | 62% | 40 | 4.4 |
| 3 | 248 | 17% | 13% | 13% | 31 | 5.1 |
| 4 | 145 | 13% | 25% | 10% | 28 | 2.9 |
| 5 | 402 | 8% | 6% | 8% | 34 | 2.3 |
| 6 | 44 | 44% | 24% | 12% | 34 | 12.4 |
| 7 | 29 | 22% | 72% | 8% | 22 | 2.9 |

> Peer clusters are unsupervised (business economics), so a stock flagged over/under-priced is mispriced vs names that ACTUALLY resemble it — catching what sector labels miss. Fundamentals are yfinance-sourced, latest FY; PE>150/PB>30/losses excluded. Descriptive screen, not investment advice.