"""Read and write watcher state and CSV results."""

import csv
import json
import os

from .settings import SEEN_FILE

def load_seen():

    if not os.path.exists(
        SEEN_FILE
    ):
        return set()

    try:

        with open(
            SEEN_FILE,
            encoding="utf-8"
        ) as f:

            return set(
                json.load(f)
            )

    except (
        ValueError,
        OSError,
        TypeError
    ):
        return set()


def write_results(results):
    with open(
        "results.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "company",
                "title",
                "location",
                "exp_required",
                "url",
                "new",
            ],
        )
        writer.writeheader()
        writer.writerows(results)


def save_seen(seen, results):
    seen.update(
        result["url"]
        for result in results
        if result["url"]
    )

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            sorted(seen),
            f,
            indent=2
        )
