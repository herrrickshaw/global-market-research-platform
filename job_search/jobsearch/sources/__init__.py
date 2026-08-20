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

ATS_SOURCES = {"greenhouse": GreenhouseSource, "lever": LeverSource, "ashby": AshbySource}
FEED_SOURCES = {"arbeitnow": ArbeitnowSource, "remotive": RemotiveSource, "adzuna": AdzunaSource}
