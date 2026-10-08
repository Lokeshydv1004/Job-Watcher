"""Fetchers for supported applicant-tracking systems."""

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..helpers import get_html, make_job, parse_date, strip_html
from ..settings import HEADERS, TIMEOUT

def fetch_greenhouse(company):
    """
    Greenhouse public jobs API.

    Config:
        {
            "name": "...",
            "ats": "greenhouse",
            "slug": "...",
            "careers": "..."
        }
    """

    slug = company["slug"]

    url = (
        f"https://boards-api.greenhouse.io/v1/"
        f"boards/{slug}/jobs?content=true"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    jobs = []

    for job in data.get("jobs", []):

        location = (
            job.get("location") or {}
        ).get("name", "")

        jobs.append(
            make_job(
                title=job.get("title", ""),
                location=location,
                url=job.get("absolute_url", ""),
                description=strip_html(
                    job.get("content", "")
                ),
                date=parse_date(
                    job.get("updated_at")
                ),
            )
        )

    return jobs

def fetch_lever(company):
    """
    Lever public postings API.

    Config:
        {
            "name": "...",
            "ats": "lever",
            "slug": "...",
            "careers": "..."
        }
    """

    slug = company["slug"]

    url = (
        f"https://api.lever.co/v0/postings/"
        f"{slug}?mode=json"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError(
            f"Unexpected Lever response: {data}"
        )

    jobs = []

    for job in data:

        parts = [
            job.get("descriptionPlain", ""),
            job.get("additionalPlain", ""),
        ]

        for section in job.get("lists", []) or []:

            parts.append(
                section.get("text", "")
            )

            parts.append(
                strip_html(
                    section.get("content", "")
                )
            )

        location = (
            job.get("categories") or {}
        ).get("location", "") or ""

        jobs.append(
            make_job(
                title=job.get("text", ""),
                location=location,
                url=job.get("hostedUrl", ""),
                description=" ".join(parts),
                date=parse_date(
                    job.get("createdAt")
                ),
            )
        )

    return jobs

def fetch_workday(company):
    """
    Generic Workday CXS API fetcher.

    Config example:

        {
            "name": "Adobe",
            "ats": "workday",
            "tenant": "adobe",
            "site": "external_experienced",
            "careers": "..."
        }

    Important:
        tenant and site must be verified for each company.
    """

    tenant = company["tenant"]
    site = company["site"]

    api_url = (
        f"https://{tenant}.wd5.myworkdayjobs.com"
        f"/wday/cxs/{tenant}/{site}/jobs"
    )

    jobs = []

    offset = 0
    limit = 100

    while True:

        payload = {
            "appliedFacets": {},
            "limit": limit,
            "offset": offset,
            "searchText": "",
        }

        response = requests.post(
            api_url,
            headers={
                **HEADERS,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        postings = data.get(
            "jobPostings",
            []
        )

        if not postings:
            break

        for job in postings:

            title = job.get(
                "title",
                ""
            )

            location = job.get(
                "locationsText",
                ""
            )

            external_path = job.get(
                "externalPath",
                ""
            )

            job_url = urljoin(
                f"https://{tenant}.wd5.myworkdayjobs.com/",
                f"{site}{external_path}"
            )

            description = strip_html(
                job.get(
                    "jobDescription",
                    ""
                )
            )

            jobs.append(
                make_job(
                    title=title,
                    location=location,
                    url=job_url,
                    description=description,
                    date=parse_date(
                        job.get("postedOn")
                    ),
                )
            )

        offset += len(postings)

        total = data.get(
            "total",
            0
        )

        if offset >= total:
            break

    return jobs

def fetch_ashby(company):
    """
    Ashby public job board API.

    Config:
        {
            "name": "...",
            "ats": "ashby",
            "slug": "...",
            "careers": "..."
        }

    Typical board:
        https://jobs.ashbyhq.com/<slug>
    """

    slug = company["slug"]

    url = (
        f"https://api.ashbyhq.com/"
        f"posting-api/job-board/{slug}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    jobs = []

    for job in data.get("jobs", []):

        location = job.get(
            "location",
            ""
        )

        if isinstance(location, dict):
            location = (
                location.get("name")
                or location.get("locationName")
                or ""
            )

        description = (
            job.get("descriptionPlain")
            or strip_html(
                job.get("description", "")
            )
        )

        jobs.append(
            make_job(
                title=job.get("title", ""),
                location=location,
                url=job.get(
                    "jobUrl",
                    ""
                ),
                description=description,
                date=parse_date(
                    job.get("publishedAt")
                ),
            )
        )

    return jobs

def fetch_smartrecruiters(company):
    """
    SmartRecruiters public API.

    Config:
        {
            "name": "...",
            "ats": "smartrecruiters",
            "slug": "...",
            "careers": "..."
        }

    Example:
        https://careers.smartrecruiters.com/<slug>
    """

    slug = company["slug"]

    jobs = []

    offset = 0
    limit = 100

    while True:

        url = (
            f"https://api.smartrecruiters.com/"
            f"v1/companies/{slug}/postings"
        )

        response = requests.get(
            url,
            headers=HEADERS,
            params={
                "limit": limit,
                "offset": offset,
            },
            timeout=TIMEOUT
        )

        response.raise_for_status()

        data = response.json()

        postings = data.get(
            "content",
            []
        )

        if not postings:
            break

        for job in postings:

            location_data = (
                job.get("location") or {}
            )

            if isinstance(
                location_data,
                dict
            ):
                location = ", ".join(
                    x
                    for x in [
                        location_data.get("city"),
                        location_data.get("region"),
                        location_data.get("country"),
                    ]
                    if x
                )
            else:
                location = str(
                    location_data
                )

            job_id = job.get(
                "id",
                ""
            )

            job_url = (
                f"https://jobs.smartrecruiters.com/"
                f"{slug}/{job_id}"
            )

            jobs.append(
                make_job(
                    title=job.get(
                        "name",
                        ""
                    ),
                    location=location,
                    url=job_url,
                    description=strip_html(
                        job.get(
                            "jobAd", {}
                        ).get(
                            "sections", {}
                        ).get(
                            "jobDescription",
                            ""
                        )
                    ),
                    date=parse_date(
                        job.get(
                            "releasedDate"
                        )
                    ),
                )
            )

        offset += len(postings)

        total = data.get(
            "totalFound",
            0
        )

        if offset >= total:
            break

    return jobs

def fetch_icims(company):
    """
    Generic iCIMS HTML fetcher.

    Config example:

        {
            "name": "...",
            "ats": "icims",
            "base_url": "https://careers-company.icims.com",
            "careers": "..."
        }

    iCIMS deployments differ between companies, so this
    uses the public search page rather than assuming a
    universal API.
    """

    base_url = company["base_url"].rstrip("/")

    search_url = (
        f"{base_url}/jobs/search"
    )

    html_text = get_html(
        search_url
    )

    soup = BeautifulSoup(
        html_text,
        "html.parser"
    )

    jobs = []

    for link in soup.select(
        "a[href]"
    ):

        href = link.get(
            "href",
            ""
        )

        title = link.get_text(
            " ",
            strip=True
        )

        if not title:
            continue

        if "/jobs/" not in href.lower():
            continue

        jobs.append(
            make_job(
                title=title,
                location="",
                url=urljoin(
                    base_url,
                    href
                ),
                description=title,
            )
        )

    return jobs
