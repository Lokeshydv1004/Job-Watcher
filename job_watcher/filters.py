"""Search criteria and job filtering."""

from datetime import datetime, timedelta, timezone

from .helpers import (
    FRESHER_RE,
    RANGE_RE,
    SINGLE_RE,
    extract_required_years,
    location_regex,
    phrase_regex,
)

class Filters:

    def __init__(self, search):

        self.roles = phrase_regex(
            search.get(
                "roles",
                []
            )
        )

        self.exclude_title = phrase_regex(
            search.get(
                "exclude_title",
                []
            )
        )

        self.locations = location_regex(
            search.get(
                "locations",
                []
            )
        )

        self.exclude_locations = location_regex(
            search.get(
                "exclude_locations",
                []
            )
        )

        exp = search.get(
            "experience",
            {}
        )

        self.min_years = exp.get(
            "min_years",
            0
        )

        self.max_years = exp.get(
            "max_years",
            99
        )

        self.include_unstated = exp.get(
            "include_if_not_stated",
            True
        )

        days = search.get(
            "max_age_days",
            0
        )

        self.cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=days)
            if days
            else None
        )

    def title_ok(self, job):

        if (
            self.roles
            and not self.roles.search(
                job["title"]
            )
        ):
            return False

        if (
            self.exclude_title
            and self.exclude_title.search(
                job["title"]
            )
        ):
            return False

        return True

    def location_ok(self, job):

        loc = job["location"]

        if (
            self.exclude_locations
            and self.exclude_locations.search(
                loc
            )
        ):
            return False

        if (
            self.locations
            and not self.locations.search(
                loc
            )
        ):
            return False

        return True

    def age_ok(self, job):

        if (
            not self.cutoff
            or not job["date"]
        ):
            return True

        return job["date"] >= self.cutoff

    def experience_ok(self, job):

        req = extract_required_years(
            job["description"]
        )

        job["exp_required"] = req

        if req is None:
            return self.include_unstated

        return (
            self.min_years
            <= req
            <= self.max_years
        )
