"""Candidate profile and role targeting.

Derived from CV_Umashankar_Master_20260826.pdf. Everything here is data, not
logic -- override any of it in config.yaml without touching the scoring engine.

The 2026-08-26 revision moved the candidate's headline identity to "Investment
Promotion & Energy-Sector Leader" and foregrounded deal origination, investor
outreach, PPP/BOOT structuring, and the energy-transition verticals built at
Invest India (SAF, CBG, CCUS, green hydrogen). The keyword map was widened to
match; see the FDI block below for why the Indian phrasing alone was not
enough.

Profile shape that drives the weights below:
  - 10+ yrs: LNG / oil & gas engineering (Shell), FDI & investment promotion
    (Invest India, GITA), business transformation (Synergy Marine, Ritzenhofer)
  - IIT Madras dual degree (Chem Eng) + ESMT Berlin MBA (Accounting & Finance)
  - Based Chennai; German B1, ESMT network -> Germany/EU is a live second market
  - Two credible lanes: (a) investment promotion / BD / corp dev in energy &
    infrastructure, (b) energy-transition technical-commercial roles
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TargetProfile:
    """What counts as a relevant job. Weights are 0-1 signal strength."""

    title_keywords: dict[str, float] = field(default_factory=lambda: {
        # --- Lane A: investment promotion / BD / corporate development ---
        "investment promotion": 1.0,
        "foreign direct investment": 1.0,
        "fdi": 1.0,
        "business development": 0.95,
        "corporate development": 0.95,
        "strategic partnerships": 0.9,
        "market entry": 0.9,
        "country manager": 0.9,
        "country head": 0.9,
        "india head": 0.9,
        "head of india": 0.9,
        "investment manager": 0.85,
        "investment analyst": 0.8,
        "investor relations": 0.8,
        "partnerships": 0.7,
        "commercial manager": 0.75,
        "commercial lead": 0.75,
        "business strategy": 0.8,
        "strategy": 0.75,
        "growth": 0.6,
        # --- Deal work: explicit on the CV (JV / BOOT / BOT, M&A, DD) ---
        "deal structuring": 0.9,
        "mergers and acquisitions": 0.85,
        "m&a": 0.85,
        "due diligence": 0.75,
        "transaction advisory": 0.8,
        "project finance": 0.8,
        "infrastructure advisory": 0.85,
        "public private partnership": 0.85,
        "ppp": 0.8,
        # --- Policy / government affairs: B2G is a core CV strength ---
        "government affairs": 0.85,
        "public affairs": 0.8,
        "policy advisor": 0.8,
        "policy manager": 0.8,
        "regulatory affairs": 0.7,
        "public policy": 0.8,
        # --- Lane B: energy transition, technical-commercial ---
        "energy transition": 0.9,
        "decarbonization": 0.85,
        "decarbonisation": 0.85,
        "sustainability manager": 0.7,
        "process engineer": 0.75,
        "front end engineering": 0.8,
        "feed": 0.6,
        "cost engineer": 0.7,
        # Cost engineering is an explicit CV bullet (basis-of-design, scope and
        # cost engineering on a ~USD 7bn LNG train; USD 40M saved) and a listed
        # core competency, but only the exact string "cost engineer" matched, so
        # "Tech Specialist - Cost Estimation" scored zero.
        "cost estimation": 0.75,
        "cost engineering": 0.75,
        # Finance-planning titles. Weighted mid, not high: the ESMT MBA is
        # Accounting & Finance and the CV carries NPV/IRR/TCO modelling, but
        # this is adjacent to the BD/investment core rather than the centre of
        # it, so these should rank below a genuine BD or energy-research role.
        "fp&a": 0.55,
        "financial planning": 0.5,
        "financial analysis": 0.5,
        "technical sales": 0.65,
        "proposal manager": 0.6,
        # --- Offshoring / capability-centre build-out ---
        # Directly evidenced: established a ~USD 400M India technology hub for a
        # pan-European insurer (BOOT/JV evaluation, 550+ hires). Titles in this
        # space rarely say "business development", so they need their own keys.
        "gcc": 0.85,
        "global capability": 0.85,
        "capability center": 0.85,
        "capability centre": 0.85,
        "shared services": 0.8,
        "outsourcing advisory": 0.85,
        "outsourcing": 0.7,
        "global business services": 0.8,
        "gbs": 0.8,
        "offshoring": 0.8,
        "location strategy": 0.75,
        # --- Adjacent: consulting, procurement, analytics ---
        "advisory": 0.6,
        "management consultant": 0.75,
        "engagement manager": 0.7,
        "consultant": 0.5,
        "category manager": 0.7,
        "procurement manager": 0.6,
        "market intelligence": 0.7,
        # Commodity/market research titles. These never say "business
        # development" but are exactly the Shell Category Analyst work
        # (market-intelligence analysis for rigs, offshore vessels, fabrication
        # yards) and the Invest India oil & gas benchmarking work. Without
        # them "Senior Market Analyst, Gas and LNG" scored zero.
        "market analyst": 0.85,
        "commodity analyst": 0.85,
        "energy analyst": 0.85,
        "oil market": 0.8,
        "gas market": 0.8,
        "market research": 0.7,
        "price reporter": 0.6,
        # "Head of Refined Products Analytics" scored zero: "analytics" was
        # nowhere in this map, though refined-product market analytics is
        # precisely the Shell Category Analyst work plus the Invest India
        # study of India's refining and import landscape.
        "analytics": 0.6,
        "refined products": 0.8,
        "commodity": 0.7,
        # The CV's own subtitle is "Business Transformation & Project
        # Development", and Invest India was project development in
        # substance -- steering approvals so companies could realise
        # projects. Four Uniper "Project Development Manager" roles scored
        # zero because only "project manager" was listed, which the words
        # "project development manager" do not contain.
        "project development": 0.8,
        "development manager": 0.7,
        "business development manager": 0.95,
        # LNG is the single deepest sector line on the CV (~USD 7bn train,
        # front-end design, cost engineering). Weighted mid on its own: an
        # LNG TRADING desk is a different discipline the CV does not
        # evidence, so this should surface the role, not top-rank it.
        "lng": 0.6,
        "gas trading": 0.45,
        # German-language titles, for the Germany/DACH corridor the ESMT MBA
        # and B1 German open up. "Leiter Energy Hub Nordwest" -- head of the
        # Wilhelmshaven LNG import hub -- scored zero purely for being in
        # German.
        "leiter": 0.75,
        "geschaftsentwicklung": 0.9,
        "geschäftsentwicklung": 0.9,
        "referent": 0.6,
        # --- The FDI / investment-promotion vocabulary the CV leads with ---
        # This is the candidate's headline identity ("Investment Promotion &
        # Energy-Sector Leader"), and outside India the same function is almost
        # never advertised as "investment promotion". Britain, Ireland and the
        # Netherlands say "inward investment"; agency roles say "trade and
        # investment"; the private-sector version is "site selection". Without
        # these keys the strongest lane on the CV is only reachable through the
        # one phrase India happens to use.
        "inward investment": 0.95,
        "trade and investment": 0.9,
        "trade commissioner": 0.85,
        "economic development": 0.85,
        "site selection": 0.8,
        "industrial policy": 0.75,
        # "Deal Origination & Investor Outreach" is a named core competency and
        # the substance of both the Invest India and GITA roles. In energy and
        # infrastructure finance the title word is simply "origination".
        "deal origination": 0.9,
        "origination": 0.8,
        "investment strategy": 0.85,
        # ESMT elective plus the development-finance flavour of the agency
        # work. Mid weight: adjacent to the core, not the centre of it.
        "impact investment": 0.75,
        "impact investing": 0.75,
        # Both spellings on purpose. strip_inserts() keeps hyphens, so a title
        # reading "Go-To-Market Strategy Manager" never contains the spaced
        # form -- the same hyphen asymmetry already fixed in the ATS scorer.
        "go-to-market": 0.7,
        "go to market": 0.7,
        # "Market Research, Competitive Intelligence & Benchmarking" is one
        # core-competency line; only the "market intelligence" half was here.
        "competitive intelligence": 0.75,
        # Verticals the CV built from scratch at Invest India (SAF, CBG,
        # lubricant recycling, CCUS) and advocated on at GITA. These appear in
        # titles as the sector, not as a function, so a role can be a perfect
        # fit and carry none of the function words above.
        "green hydrogen": 0.7,
        "energy efficiency": 0.6,
        "city gas distribution": 0.7,
        # --- Found by pulling four new employers and reading the ZEROES ---
        # Every one of these scored 0.000 "no role keyword match" against a
        # real posting that is plainly a fit. The gaps are all near-misses on
        # a word this map already almost had.
        #
        # "Manager - Mobility Consulting (DFI & Government Business)" is the
        # Invest India job description almost verbatim, and it scored zero
        # because the map had "consultant" but not "consulting", and nothing
        # at all for development-finance or government-business work.
        "consulting": 0.5,
        "dfi": 0.9,
        "development finance": 0.9,
        "government business": 0.85,
        "public sector advisory": 0.85,
        # "Manager (Power / Clean Energy Domain)" - the energy-transition
        # vertical is on the CV twice, but only as sector words, which cannot
        # rescue a title carrying no function word. Not bare "power": that
        # would pull in power-systems engineering.
        "clean energy": 0.7,
        "power sector": 0.65,
        "energy sector": 0.65,
        # "Regional Manager - Large Corporates (BD)" - India's market
        # abbreviates business development in the title itself. Two letters
        # is a greedy key: "BD" is also Becton Dickinson, so their brands are
        # hard negatives below. Without that, "Territory Sales Rep - BD
        # Biosciences" scored 0.85.
        "bd": 0.85,
        # "Director - Private Markets" - private-market investment is the
        # deal-side neighbour of the FDI work; the sector map had "private
        # equity" but no title key could reach it.
        "private markets": 0.6,
        # Development-finance grade titles. The World Bank, IFC and the
        # regional banks advertise senior professional roles as "Officer" and
        # "Specialist"; without these the only key they hit is the generic
        # "consultant", which then trips the junior penalty.
        "investment officer": 0.85,
        "sector specialist": 0.75,
        "industry specialist": 0.7,
        "operations officer": 0.6,
        # Sector-leadership titles. "Director Oil and Gas" at an advisory or
        # research house is the CV's deepest sector line with a grade attached,
        # and it scored 0.000: oil and gas were only ever SECTOR words, which
        # cannot rescue a title carrying no function word. Found by refreshing
        # Crisil and reading the zeroes again.
        "oil and gas": 0.7,
        "oil & gas": 0.7,
        "natural gas": 0.65,
        "research analyst": 0.6,
        "business analyst": 0.5,
        "transformation": 0.6,
        "program manager": 0.55,
        "project manager": 0.5,
    })

    # Sector words. Energy and infrastructure dominate the CV, so they carry
    # the most lift; the quant-investing pivot is real but less evidenced.
    sector_keywords: dict[str, float] = field(default_factory=lambda: {
        "lng": 0.7, "oil": 0.6, "gas": 0.6, "petrochemical": 0.6, "refinery": 0.6,
        "upstream": 0.55, "downstream": 0.55, "energy": 0.6,
        "hydrogen": 0.65, "electrolyzer": 0.6, "renewable": 0.6, "solar": 0.5,
        "wind": 0.5, "biogas": 0.6, "biofuel": 0.6, "ethanol": 0.55,
        "sustainable aviation fuel": 0.65, "saf": 0.5,
        "carbon capture": 0.65, "ccus": 0.65, "net zero": 0.5,
        "infrastructure": 0.6, "power": 0.45, "utilities": 0.4,
        "chemicals": 0.5, "manufacturing": 0.45, "industrial": 0.4,
        "electric vehicle": 0.5, "battery": 0.45, "mobility": 0.4,
        "shipping": 0.55, "maritime": 0.55, "logistics": 0.4, "port": 0.45,
        "food processing": 0.4, "textile": 0.35,
        "private equity": 0.55, "venture capital": 0.45, "asset management": 0.5,
        "investment": 0.5, "fund": 0.4,
    })

    seniority_keywords: dict[str, float] = field(default_factory=lambda: {
        "head of": 0.95, "director": 0.9, "associate director": 0.9,
        "vice president": 0.85, "vp": 0.8, "general manager": 0.85,
        "senior manager": 0.85, "principal": 0.75, "lead": 0.7,
        "manager": 0.7, "senior": 0.6, "chief": 0.8,
    })

    # A single hit here zeroes the score. Tuned to strip out the noise that
    # dominates broad aggregator feeds for a senior non-engineering candidate.
    exclude_keywords: list[str] = field(default_factory=lambda: [
        # Wrong career stage
        "intern", "internship", "working student", "werkstudent", "praktikum",
        "apprentice", "graduate scheme", "trainee", "fresher", "entry level",
        "phd", "postdoc", "doctoral",
        # Wrong function - enterprise-platform implementation. These carry
        # consulting-sounding titles ("Senior Manager, SAP Treasury, Advisory")
        # and slip through on generic keywords, but they need deep platform
        # skills the CV does not evidence.
        "sap", "oracle", "salesforce", "servicenow", "workday", "d365",
        "dynamics 365", "guidewire", "coupa", "onestream", "mulesoft",
        "sailpoint", "hana", "netsuite", "peoplesoft", "tableau", "power bi",
        "sharepoint", "microsoft 365", "m365",
        # Junior sales, not business development. The Siemens note in this
        # file claimed BDR roles were "correctly excluded"; they were not -
        # "Business Development Representative" scored 0.95 on the
        # "business development" key. They cannot be caught by the junior
        # penalty either, since that is now withheld from strong domain
        # matches, so they belong here as their own function.
        "business development representative", "sales development representative",
        "sales representative", "account executive", "bdr", "sdr",
        # Wrong function - software/IC engineering
        # "Consulting Software Architect" scored 0.5 on the new "consulting"
        # key - the same wrong-function trap as the rest of this block.
        "software architect", "solution architect",
        # BD = Becton Dickinson, not business development.
        "biosciences", "becton",
        # Plant and field operations. The new "oil and gas" key gave
        # "Oil and Gas Field Operator" 0.82, and these titles dominate the
        # boards of every refiner and national oil company in the dump
        # (Reliance 99 postings, QatarEnergy 181, ADNOC 80).
        "operator", "fitter", "welder", "machinist", "rigger",
        "software engineer", "software developer", "backend engineer",
        "frontend engineer", "full stack", "devops", "sre", "qa engineer",
        "data engineer", "machine learning engineer", "android", "ios developer",
        "java developer", "python developer", ".net", "salesforce developer",
        # Wrong function - volume sales / support / ops
        # Financial-crime / compliance. These wear "due diligence" and
        # "advisory" in their titles and were scoring near the top on those
        # words alone, but the CV's due diligence is TRANSACTION due diligence
        # (M&A, deal structuring, JV/BOOT), not KYC/AML screening. Different
        # discipline, different hiring managers.
        "fincrime", "financial crime", "anti-money laundering", "aml",
        "kyc", "sanctions screening", "compliance officer",
        "sales representative", "sales executive", "sdr", "bdr", "telecaller",
        "cold calling", "customer support", "customer service", "call center",
        "call centre", "field sales", "insurance agent", "real estate agent",
        # Wrong collar entirely
        "nurse", "driver", "warehouse", "cashier", "cleaner", "security guard",
        "electrician", "welder", "fitter", "machinist", "technician",
        "receptionist", "chef", "waiter", "housekeeping",
    ])

    # India first (Chennai-based), then the German/EU corridor the MBA and B1
    # German open up, then the Gulf and Singapore where Indian energy BD travels.
    locations: list[str] = field(default_factory=lambda: [
        # India
        "india", "chennai", "bengaluru", "bangalore", "delhi", "new delhi",
        "gurgaon", "gurugram", "noida", "mumbai", "pune", "hyderabad",
        "ahmedabad", "gujarat", "tamil nadu", "kolkata",
        # Germany / DACH
        "germany", "deutschland", "berlin", "munich", "münchen", "muenchen",
        "frankfurt", "hamburg", "düsseldorf", "duesseldorf", "cologne",
        "stuttgart", "austria", "vienna", "switzerland", "zurich",
        # Rest of Europe
        "netherlands", "amsterdam", "the hague", "rotterdam", "belgium",
        "brussels", "united kingdom", "london", "paris", "france", "madrid",
        "spain", "milan", "italy", "copenhagen", "denmark", "sweden",
        "stockholm", "norway", "oslo", "europe", "emea",
        # Gulf + APAC hubs
        "dubai", "abu dhabi", "uae", "qatar", "doha", "saudi", "riyadh",
        "oman", "muscat", "singapore",
        # Anywhere
        "remote", "hybrid",
    ])

    # Titles that signal an individual-contributor entry rung. Penalised (not
    # excluded) when the title carries no seniority marker: "Research Analyst"
    # is junior, "Senior Research Analyst" is not.
    junior_keywords: list[str] = field(default_factory=lambda: [
        "analyst", "associate", "assistant", "coordinator", "executive",
        "officer", "specialist", "engineer", "consultant",
    ])

    remote_ok: bool = True
    min_score: float = 0.25


DEFAULT_PROFILE = TargetProfile()
