"""Load config, run company fetches, filter jobs, and report matches."""

import json
import sys
import time

from .fetchers import FETCHERS, fetch_career_page
from .filters import Filters
from .persistence import load_seen, save_seen, write_results

def main():

    config_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "config.json"
    )

    with open(
        config_path,
        encoding="utf-8"
    ) as f:

        config = json.load(f)

    flt = Filters(
        config["search"]
    )

    seen = load_seen()

    results = []

    for company in config["companies"]:

        name = company.get(
            "name",
            "Unknown"
        )

        try:
            if company.get("ats"):
                ats = company["ats"].lower()
                fetch = FETCHERS.get(ats)

                if not fetch:
                    print(
                        f"[SKIPPED] {name}: "
                        f"unsupported ATS '{ats}'"
                    )
                    continue

                jobs = fetch(company)
            else:
                jobs = fetch_career_page(company)

                if not jobs:
                    continue

        except Exception as e:

            careers = company.get(
                "careers",
                "N/A"
            )

            print(
                f"[FAILED] {name}: "
                f"{type(e).__name__}: {e}"
            )

            print(
                f"          verify: {careers}"
            )

            continue
        print(jobs)
        after_title = [
            job
            for job in jobs
            if flt.title_ok(job)
        ]

        after_loc = [
            job
            for job in after_title
            if flt.location_ok(job)
        ]

        after_age = [
            job
            for job in after_loc
            if flt.age_ok(job)
        ]

        final = [
            job
            for job in after_age
            if flt.experience_ok(job)
        ]

        print(
            f"\n[OK] {name}: "
            f"{len(jobs)} jobs "
            f"-> title {len(after_title)} "
            f"-> location {len(after_loc)} "
            f"-> age {len(after_age)} "
            f"-> experience {len(final)}"
        )

        if not jobs:

            print(
                f"     WARNING: 0 jobs returned. "
                f"Check manually: "
                f"{company.get('careers', 'N/A')}"
            )

        for job in final:

            job_url = job["url"]

            is_new = (
                job_url not in seen
            )

            exp = (
                "not stated"
                if job["exp_required"] is None
                else f"{job['exp_required']}+ yrs"
            )

            print(
                f"  {'NEW ' if is_new else '    '}"
                f"{job['title']} | "
                f"{job['location']} | "
                f"exp: {exp}"
            )

            print(
                f"       {job_url}"
            )

            results.append({
                "company": name,
                "title": job["title"],
                "location": job["location"],
                "exp_required": exp,
                "url": job_url,
                "new": is_new,
            })

        # Be polite to career APIs
        time.sleep(1)

    write_results(results)

    save_seen(seen, results)

    print(
        f"\nDone: {len(results)} matches "
        f"saved to results.csv "
        f"({sum(r['new'] for r in results)} new)"
    )
