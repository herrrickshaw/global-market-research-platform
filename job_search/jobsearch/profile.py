"""Candidate profile and role targeting.

Derived from Umashankar_TD_CV.pdf (2026-08-13). Everything here is data, not
logic -- override any of it in config.yaml without touching the scoring engine.

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
        # Wrong function - software/IC engineering
        "software engineer", "software developer", "backend engineer",
        "frontend engineer", "full stack", "devops", "sre", "qa engineer",
        "data engineer", "machine learning engineer", "android", "ios developer",
        "java developer", "python developer", ".net", "salesforce developer",
        # Wrong function - volume sales / support / ops
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
