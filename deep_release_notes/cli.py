# -*- coding: utf-8 -*-

"""Console script for deep_release_notes."""
import click
from datetime import datetime
import logging
from pathlib import Path
import re
import requests
import sys
from time import sleep


@click.group()
@click.option("-v", "--verbose", count=True)
@click.option("-q", "--quiet", count=True)
def main(verbose, quiet):
    log_level = min(
        max(logging.DEBUG, logging.WARNING - verbose * 10 + quiet * 10),
        logging.CRITICAL,
    )
    logging.basicConfig(
        format="[%(levelname)s %(asctime)s|%(filename)s:%(lineno)d] %(message)s",
        level=log_level,
    )


@main.command(name="find-all")
@click.option("--size", default=6000)
def find_all(size):
    all_search_criteria = [
        {"file_name": "RELEASENOTES", "extension": "md"},
        {"file_name": "RELEASE_NOTES", "extension": "md"},
        {"file_name": "RELEASENOTES", "extension": "rst"},
        {"file_name": "RELEASE_NOTES", "extension": "rst"},
        {"file_name": "CHANGELOG", "extension": "md"},
        {"file_name": "CHANGE_LOG", "extension": "md"},
        {"file_name": "CHANGELOG", "extension": "rst"},
        {"file_name": "CHANGE_LOG", "extension": "rst"},
        {"file_name": "NEWS", "extension": "md"},
        {"file_name": "NEWS", "extension": "rst"},
    ]
    for search_criterion in all_search_criteria:
        find_release_notes(
            file_name=search_criterion["file_name"],
            extension=search_criterion["extension"],
            size=size,
        )


@main.command(name="find")
@click.argument("file_name")
@click.option("--size", default=5900)
@click.option("--extension", default="md")
@click.option("--output-dir", default=None)
def find(file_name, extension, size, output_dir):
    find_release_notes(file_name, extension, size, output_dir)


def find_release_notes(file_name, extension, size=5900, output_dir=None):
    out_dir = Path(output_dir) if output_dir else Path(f"{file_name}.size_{size}")
    out_dir.mkdir(parents=True, exist_ok=True)
    logging.info(
        "Looking for repositories with %s.%s of size > %s. Storing results into %s.",
        file_name,
        extension,
        size,
        str(out_dir),
    )

    http_session = get_github_session()
    downloaded_files = get_files_in_dir(out_dir)
    next_page = (find_last_downloaded_page(downloaded_files) or 0) + 1
    while True:
        logging.debug("Finding %s.%s file. Page %s...", file_name, extension, next_page)
        response = github_find_file_in_repos(
            http_session, file_name, extension, size, next_page
        )
        logging.debug("Got response status: %s", response.status_code)
        logging.debug("Got response text: %s", response.text)
        logging.debug("Got response headers: %s", response.headers)
        if should_retry(response):
            wait_before_retry(response)
            logging.info("Retrying now...")
            # It looks like we have to reset the session after we get rate limited
            http_session = get_github_session()
            continue
        elif response.status_code == 422:
            # It looks like this error code is used when the page number exceeds last... so let's break here.
            logging.info("Looks like we went past the last page. Stopping.")
            break
        else:
            response.raise_for_status()

        num_of_results = len(response.json()["items"])
        logging.debug(
            "Found %s %s files on page %s.", num_of_results, file_name, next_page
        )
        if num_of_results > 0:
            write_page_file(out_dir.joinpath(file_name), next_page, response.text)
        next_page = get_next_page(response.headers)

        if next_page is None:
            logging.info("Finished.")
            break

        pause = get_request_pause(response.headers)
        logging.debug("Sleeping for %s seconds to avoid being rate-limited.", pause)
        sleep(pause)


def wait_before_retry(response):
    retry_after = int(response.headers["Retry-After"])
    logging.info("Reached rate limit. Waiting for %s seconds.", retry_after)
    sleep(retry_after)


def should_retry(response):
    return response.status_code == 403 and "Retry-After" in response.headers


def github_find_file_in_repos(http_session, file_name, extension, size, page):
    return http_session.get(
        "https://api.github.com/search/code",
        params={
            "q": f"{file_name} in:path path:/ size:>{size} extension:{extension}",
            "page": page,
            "sort": "indexed",
        },
    )


def get_files_in_dir(dir=None):
    dir = dir if dir else Path()
    return [str(f) for f in dir.iterdir() if f.is_file()]


def wait_if_close_to_rate_limit(response, closeness_ratio):
    rate_limit = int(response.headers["X-RateLimit-Limit"])
    rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
    if rate_limit_remaining / rate_limit < closeness_ratio:
        reset_time = datetime.utcfromtimestamp(
            int(response.headers["X-RateLimit-Reset"])
        )
        wait_seconds = (reset_time - datetime.utcnow()).seconds + 1
        logging.warning(
            "Closing in on the rate limit. Rate limit remaining is %s. "
            "Waiting %s seconds until rate limit reset.",
            rate_limit_remaining,
            wait_seconds,
        )
        sleep(wait_seconds)


def get_github_session():
    session = requests.Session()
    session.auth = tuple(
        Path.home().joinpath(".github", "access_token").read_text().splitlines()
    )
    return session


def write_page_file(prefix, page, json_str):
    output_file = f"{prefix}-{page}.json"
    logging.info("Storing page file %s...", output_file)
    with open(output_file, "w") as projects_file:
        projects_file.write(json_str)
        click.echo(output_file)


def find_last_downloaded_page(downloaded_files):
    if not downloaded_files:
        return None
    pattern = re.compile(r"^.*-(?P<page>\d+).json$")
    pages = [
        int(m.group("page"))
        for m in [
            pattern.match(downloaded_file) for downloaded_file in downloaded_files
        ]
        if m is not None
    ]
    return max(pages) if pages else None


def get_next_page(response_headers):
    link_header = response_headers.get("Link")
    logging.debug("Got link header: %s", link_header)
    if link_header is None:
        return None
    match = re.search(r"page=(\d+)[^>]*?>; rel=\"next\"", link_header)
    if match is None:
        logging.debug("Could not find the next page...")
        return None
    logging.debug("Found next page: %s", match.group(1))
    return int(match.group(1))


def get_request_pause(response_headers, response_timestamp=None):
    response_timestamp = (
        int(datetime.now().timestamp())
        if response_timestamp is None
        else response_timestamp
    )
    rate_remaining = response_headers.get("X-RateLimit-Remaining")
    rate_reset_timestamp = response_headers.get("X-RateLimit-Reset")
    if not rate_remaining or not rate_reset_timestamp:
        return None
    return (float(rate_reset_timestamp) - float(response_timestamp)) / float(
        rate_remaining
    )


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
