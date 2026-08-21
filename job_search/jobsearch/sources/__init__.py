"""Job posting sources. Each returns a list[JobPosting]."""
from .base import JobSource, SourceError, http_get_json, http_get_text  # noqa: F401
from .greenhouse import GreenhouseSource  # noqa: F401
from .lever import LeverSource  # noqa: F401
from .ashby import AshbySource  # noqa: F401
from .arbeitnow import ArbeitnowSource  # noqa: F401
from .remotive import RemotiveSource  # noqa: F401
from .adzuna import AdzunaSource  # noqa: F401
from .careers_page import CareersPageSource  # noqa: F401
from .apollo import ApolloDumpSource, ApolloSource  # noqa: F401
from .jsearch import JSearchSource  # noqa: F401
from .serpapi import SerpApiJobsSource  # noqa: F401
from .rapidapi_jobs import (ActiveJobsDBSource, Indeed12Source,  # noqa: F401
                            LinkedInJobSearchSource, LinkedInJobsApi2Source)
from .ats_public import (PersonioSource, SmartRecruitersSource,  # noqa: F401
                         WorkableSource)
from .workday import WorkdaySource, tenants_from_urls  # noqa: F401
from .aggregators import CareerjetSource, JoobleSource  # noqa: F401

# Slug-addressed public boards, probed by discovery.resolve_board(). Ordered
# by how often a probe hits: the big three first, then the long tail.
ATS_SOURCES = {"greenhouse": GreenhouseSource, "lever": LeverSource,
               "ashby": AshbySource, "smartrecruiters": SmartRecruitersSource,
               "workable": WorkableSource, "personio": PersonioSource}

# Workday is deliberately NOT in ATS_SOURCES: its host carries a data-centre
# number (wd1/wd3/wd5) that cannot be guessed from a company name, so it is
# configured per company from a careers URL instead of probed.
FEED_SOURCES = {"arbeitnow": ArbeitnowSource, "remotive": RemotiveSource,
                "adzuna": AdzunaSource, "jsearch": JSearchSource,
                "google_jobs": SerpApiJobsSource,
                "linkedin": LinkedInJobSearchSource,
                "linkedin2": LinkedInJobsApi2Source,
                "active_ats": ActiveJobsDBSource}

# Company-scoped rather than query-scoped: called per employer, so it is
# driven by the network ranking instead of the feed loop.
COMPANY_SOURCES = {"indeed": Indeed12Source}

# Free-key aggregators. Jooble and Careerjet cover India far better than
# Adzuna does; Adzuna is the stronger of the three in the UK and Germany.
KEYED_AGGREGATORS = {"adzuna": AdzunaSource, "jooble": JoobleSource,
                     "careerjet": CareerjetSource}
