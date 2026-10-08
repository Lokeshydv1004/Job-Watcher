"""Fetcher registry and public fetcher imports."""

from .ats import (
    fetch_ashby,
    fetch_greenhouse,
    fetch_icims,
    fetch_lever,
    fetch_smartrecruiters,
    fetch_workday,
)
from .career_page import fetch_career_page

FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "workday": fetch_workday,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "icims": fetch_icims,
}
