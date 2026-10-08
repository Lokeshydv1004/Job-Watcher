"""Conservative extraction of static job postings from career pages."""

import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from ..helpers import make_job, parse_date, strip_html
from ..settings import HEADERS, TIMEOUT
from urllib.parse import urljoin, urlparse
JOB_URL_RE = re.compile(
    r"/(?:job|jobs|position|positions|careers)(?:/|[-_])",
    re.I
)

def _jsonld_job_records(value):
    """Yield JobPosting dictionaries from JSON-LD structures."""
    if isinstance(value, list):
        for item in value:
            yield from _jsonld_job_records(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]

        if any(item.lower() == "jobposting" for item in types if isinstance(item, str)):
            yield value

        for key, item in value.items():
            if key in {"@graph", "mainEntity", "itemListElement"}:
                yield from _jsonld_job_records(item)

def _json_job_records(value):
    """Yield likely job records from embedded JSON without trusting arbitrary links."""
    if isinstance(value, list):
        for item in value:
            yield from _json_job_records(item)
    elif isinstance(value, dict):
        title = value.get("title") or value.get("jobTitle")
        url = value.get("url") or value.get("jobUrl") or value.get("applyUrl")
        keys = {str(key).lower() for key in value}
        job_context = bool(
            {"description", "jobdescription", "location", "joblocation", "dateposted", "posteddate"} & keys
        )

        if title and url and (job_context or JOB_URL_RE.search(str(url))):
            yield value

        for item in value.values():
            if isinstance(item, (dict, list)):
                yield from _json_job_records(item)

def _job_location(value):
    """Flatten common Schema.org and embedded-JSON location shapes."""
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return "; ".join(
            location
            for location in (_job_location(item) for item in value)
            if location
        )

    if isinstance(value, dict):
        address = value.get("address", value)
        if isinstance(address, dict):
            parts = [
                address.get(key)
                for key in (
                    "addressLocality",
                    "addressRegion",
                    "addressCountry",
                )
            ]
            return ", ".join(str(part) for part in parts if part)

        return str(address) if address else ""

    return ""

def _normalized_career_job(record, base_url):
    """Convert a structured job record into the watcher schema."""
    title = record.get("title") or record.get("jobTitle") or record.get("name") or ""
    url = record.get("url") or record.get("jobUrl") or record.get("applyUrl") or ""
    if isinstance(url, dict):
        url = url.get("@id") or url.get("url") or ""

    description = record.get("description") or record.get("jobDescription") or ""
    if isinstance(description, (dict, list)):
        description = json.dumps(description, ensure_ascii=True)

    return make_job(
        title=strip_html(str(title)),
        location=_job_location(record.get("jobLocation") or record.get("location")),
        url=urljoin(base_url, str(url)),
        description=strip_html(str(description)),
        date=parse_date(record.get("datePosted") or record.get("postedDate") or record.get("date")),
    )



def fetch_career_page(company):
    """Discover actual static job postings from a company's public career page."""
    name = company.get("name", "Unknown")
    careers_url = company.get("careers")

    if not careers_url:
        raise ValueError("Company config is missing 'careers'")

    response = requests.get(
        careers_url,
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    response.raise_for_status()

    if not response.text.strip():
        raise ValueError("Career page returned an empty response")

    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    seen_urls = set()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def clean_url(url):
        if not url:
            return ""

        url = url.strip()
        url = urljoin(response.url, url)

        # Remove fragment
        url = url.split("#", 1)[0]

        return url

    def is_same_domain(url):
        try:
            base_host = urlparse(response.url).netloc.lower()
            job_host = urlparse(url).netloc.lower()

            # Allow subdomains of the career domain.
            return (
                job_host == base_host
                or job_host.endswith("." + base_host)
                or base_host.endswith("." + job_host)
            )
        except Exception:
            return False

    def looks_like_job_url(url):
        """
        Strong URL-level signal.

        Examples accepted:
            /job/software-engineer/123
            /jobs/software-engineer
            /position/software-engineer
            /positions/123
            /careers/job/123

        Examples rejected:
            /careers/teams
            /careers/blog
            /search-jobs
            /saved-jobs
            /careers
        """
        if not url:
            return False

        parsed = urlparse(url)
        path = parsed.path.lower().rstrip("/")

        # Must be a real HTTP(S) URL.
        if parsed.scheme not in ("http", "https"):
            return False

        # Avoid external links.
        if not is_same_domain(url):
            return False

        # Obvious non-job paths.
        blocked = (
            "/blog",
            "/blogs",
            "/news",
            "/events",
            "/event",
            "/team",
            "/teams",
            "/about",
            "/contact",
            "/privacy",
            "/terms",
            "/legal",
            "/saved-jobs",
            "/search-jobs",
            "/search",
            "/internships",
            "/entry-level",
            "/locations",
        )

        if any(path == item or path.startswith(item + "/") for item in blocked):
            return False

        # Strong job URL patterns.
        job_patterns = (
            r"/job/",
            r"/jobs/",
            r"/position/",
            r"/positions/",
            r"/opening/",
            r"/openings/",
            r"/vacancy/",
            r"/vacancies/",
        )

        return any(re.search(pattern, path) for pattern in job_patterns)

    def looks_like_job_title(title):
        if not title:
            return False

        title = re.sub(r"\s+", " ", title).strip()

        if len(title) < 5 or len(title) > 250:
            return False

        lower = title.lower()

        # Navigation/category links that were appearing in your output.
        blocked_titles = {
            "saved jobs",
            "customer experience",
            "data",
            "marketing",
            "product management",
            "sales",
            "software engineering",
            "hiring process",
            "internships",
            "entry-level careers",
            "working at intuit",
            "hybrid work",
            "careers",
            "search jobs",
            "view jobs",
            "all jobs",
            "job search",
            "locations",
            "teams",
            "about us",
            "contact us",
            "privacy policy",
            "terms of use",
        }

        if lower in blocked_titles:
            return False

        # Obvious non-job links.
        blocked_words = (
            "privacy policy",
            "terms of use",
            "cookie policy",
            "youtube",
            "linkedin",
            "instagram",
            "facebook",
            "read more",
            "learn more",
            "view all",
            "see all",
        )

        if any(word in lower for word in blocked_words):
            return False

        # A job title normally contains at least one role-like word.
        role_words = (
            "engineer",
            "developer",
            "scientist",
            "analyst",
            "designer",
            "manager",
            "architect",
            "intern",
            "developer",
            "consultant",
            "specialist",
            "administrator",
            "researcher",
            "recruiter",
            "director",
            "associate",
            "accountant",
            "security",
            "devops",
            "product",
            "software",
            "technical",
            "machine learning",
            "data",
        )

        return any(word in lower for word in role_words)

    def extract_jsonld_jobposting(html_soup):
        """
        Extract JobPosting from an individual job page.
        """
        for script in html_soup.select('script[type="application/ld+json"]'):
            try:
                raw = script.string or script.get_text()
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue

            records = []

            if isinstance(data, dict):
                if data.get("@type") == "JobPosting":
                    records.append(data)

                # @graph can contain JobPosting objects.
                graph = data.get("@graph")
                if isinstance(graph, list):
                    records.extend(
                        item
                        for item in graph
                        if isinstance(item, dict)
                        and item.get("@type") == "JobPosting"
                    )

            elif isinstance(data, list):
                records.extend(
                    item
                    for item in data
                    if isinstance(item, dict)
                    and item.get("@type") == "JobPosting"
                )

            if records:
                return records[0]

        return None

    def fetch_job_details(url, fallback_title="", fallback_description=""):
        """
        Fetch an individual job page and extract JobPosting structured data.

        This is what fixes the Intuit problem where the career listing
        showed "Multiple Locations" instead of the actual job location.
        """
        try:
            detail_response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
            )
            detail_response.raise_for_status()

            detail_soup = BeautifulSoup(
                detail_response.text,
                "html.parser",
            )

            posting = extract_jsonld_jobposting(detail_soup)

            if posting:
                return {
                    "title": posting.get("title") or fallback_title,
                    "location": posting.get("jobLocation"),
                    "description": posting.get("description")
                    or fallback_description,
                    "url": url,
                    "date": (
                        posting.get("datePosted")
                        or posting.get("dateCreated")
                        or posting.get("validThrough")
                    ),
                }

            # Fallback when there is no JobPosting JSON-LD.
            title = fallback_title

            if detail_soup.title:
                page_title = detail_soup.title.get_text(" ", strip=True)

                if page_title and looks_like_job_title(page_title):
                    title = page_title

            description_node = detail_soup.select_one(
                '[itemprop="description"], '
                '[class*="job-description" i], '
                '[class*="description" i]'
            )

            description = (
                description_node.get_text(" ", strip=True)
                if description_node
                else fallback_description
            )

            return {
                "title": title,
                "location": "",
                "description": description,
                "url": url,
                "date": None,
            }

        except requests.RequestException:
            return {
                "title": fallback_title,
                "location": "",
                "description": fallback_description,
                "url": url,
                "date": None,
            }

    def add_job(record, fetch_details=False):
        job = _normalized_career_job(
            record,
            response.url,
        )

        if not job.get("title") or not job.get("url"):
            return

        job["url"] = clean_url(job["url"])

        if not job["url"]:
            return

        if not is_same_domain(job["url"]):
            return

        if job["url"] in seen_urls:
            return

        if not looks_like_job_title(job["title"]):
            return

        # If the listing page doesn't have useful location/description,
        # inspect the actual job page.
        if fetch_details:
            details = fetch_job_details(
                job["url"],
                fallback_title=job.get("title", ""),
                fallback_description=job.get("description", ""),
            )

            if details:
                if details.get("title"):
                    job["title"] = details["title"]

                if details.get("location"):
                    job["location"] = details["location"]

                if details.get("description"):
                    job["description"] = details["description"]

                if details.get("date"):
                    job["date"] = details["date"]

        seen_urls.add(job["url"])
        jobs.append(job)

    # ---------------------------------------------------------
    # 1. JSON-LD JobPosting
    # ---------------------------------------------------------

    for script in soup.select('script[type="application/ld+json"]'):
        try:
            raw = script.string or script.get_text()
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue

        for record in _jsonld_job_records(data):
            add_job(record)

    # ---------------------------------------------------------
    # 2. Application state JSON
    # ---------------------------------------------------------

    for script in soup.select(
        'script[type="application/json"], script#__NEXT_DATA__'
    ):
        try:
            raw = script.string or script.get_text()
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue

        for record in _json_job_records(data):
            add_job(record)

    # ---------------------------------------------------------
    # 3. Strong job-link discovery
    # ---------------------------------------------------------

    candidate_links = []

    for link in soup.select("a[href]"):
        href = link.get("href", "").strip()
        title = link.get_text(" ", strip=True)

        if not href:
            continue

        url = clean_url(href)

        # IMPORTANT:
        # Do NOT accept a link merely because its parent has
        # class="job" / class="result".
        #
        # The URL itself must look like a job URL.
        if not looks_like_job_url(url):
            continue

        if not looks_like_job_title(title):
            continue

        candidate_links.append(
            {
                "title": title,
                "url": url,
                "element": link,
            }
        )

    # ---------------------------------------------------------
    # 4. Extract each actual job page
    # ---------------------------------------------------------

    for candidate in candidate_links:
        link = candidate["element"]
        title = candidate["title"]
        url = candidate["url"]

        parent = (
            link.find_parent(
                attrs={
                    "class": re.compile(
                        r"job|posting|position|result|opening",
                        re.I,
                    )
                }
            )
            or link.find_parent(
                attrs={
                    "id": re.compile(
                        r"job|posting|position|result|opening",
                        re.I,
                    )
                }
            )
        )

        location_node = None
        description_node = None

        if parent:
            location_node = parent.select_one(
                '[class*="location" i], '
                '[class*="office" i], '
                '[itemprop="jobLocation"]'
            )

            description_node = parent.select_one(
                '[class*="description" i], '
                '[itemprop="description"]'
            )

        location = (
            location_node.get_text(" ", strip=True)
            if location_node
            else ""
        )

        description = (
            description_node.get_text(" ", strip=True)
            if description_node
            else ""
        )

        add_job(
            {
                "title": title,
                "location": location,
                "url": url,
                "description": description,
                "date": None,
            },
            fetch_details=True,
        )

    # ---------------------------------------------------------
    # Final result
    # ---------------------------------------------------------

    if not jobs:
        print(
            f"[NO_STATIC_JOBS] {name}: career page loaded but no actual "
            "job postings were found in the HTML"
        )
    else:
        print(
            f"[DISCOVERED] {name}: {len(jobs)} actual job postings"
        )

    return jobs
