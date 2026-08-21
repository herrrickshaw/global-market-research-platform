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

ATS_SOURCES = {"greenhouse": GreenhouseSource, "lever": LeverSource, "ashby": AshbySource}
FEED_SOURCES = {"arbeitnow": ArbeitnowSource, "remotive": RemotiveSource,
                "adzuna": AdzunaSource, "jsearch": JSearchSource,
                "google_jobs": SerpApiJobsSource,
                "linkedin": LinkedInJobSearchSource,
                "linkedin2": LinkedInJobsApi2Source,
                "active_ats": ActiveJobsDBSource}

# Company-scoped rather than query-scoped: called per employer, so it is
# driven by the network ranking instead of the feed loop.
COMPANY_SOURCES = {"indeed": Indeed12Source}
