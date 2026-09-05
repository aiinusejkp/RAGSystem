"""
A gentle recursive crawler that walks a website depth-first.
It collects every reachable page while being polite to the server
and never getting lost in loops.
"""

import random
import re
import sys
import time
import urllib.error
import urllib.request
from functools import reduce
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

MAXIMUM_PAGES_TO_COLLECT = 2000
MAXIMUM_DEPTH_ALLOWED = 10
REQUEST_TIMEOUT_SECONDS = 10
SECONDS_TO_PAUSE_BETWEEN_REQUESTS = 0.2

BROWSER_LIKE_HEADER = {"User-Agent": "Mozilla/5.0 (compatible; symbol_def/1.0)"}

# We only take links that appear inside real <a> tags
LINK_INSIDE_ANCHOR_TAG = re.compile(
    r"""<a\s[^>]*?href\s*=\s*["']([^"']+)["']""", re.IGNORECASE | re.DOTALL
)


def the_website_name_of(url):
    """Return the website name without 'www.'"""
    return urlparse(url).netloc.removeprefix("www.")


def make_address_consistent(url):
    """
    Turn different spellings of the same page into one standard form.
    Example: http://www.site.in/about/  and  https://site.in/about#team
    both become → https://site.in/about
    """
    parts = urlparse(url)
    return urlunparse(
        (
            "https",
            the_website_name_of(url),
            parts.path.rstrip("/"),
            "",
            parts.query,
            "",
        )
    )


def is_a_normal_web_page(url):
    """True only for normal http/https pages."""
    parts = urlparse(url)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def does_this_page_belong_to(website, url):
    """True when the page belongs to the given website."""
    return the_website_name_of(url) == website


def pause_politely_before_next_request():
    """Wait a little (with random jitter) so we don't hammer the server."""
    time.sleep(SECONDS_TO_PAUSE_BETWEEN_REQUESTS + random.random() * 0.5)


def download_the_html_of(page):
    """
    Download the HTML of a page.
    Returns an empty string if anything goes wrong or it is not HTML.
    """
    pause_politely_before_next_request()
    try:
        request = urllib.request.Request(page, headers=BROWSER_LIKE_HEADER)
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as reply:
            if "html" not in reply.headers.get("Content-Type", "").lower():
                return ""
            charset = reply.headers.get_content_charset() or "utf-8"
            return reply.read().decode(charset, errors="replace")
    except (urllib.error.URLError, OSError, ValueError, LookupError):
        return ""


def find_every_link_on(page):
    """Return every valid link found on this page."""
    raw_links = LINK_INSIDE_ANCHOR_TAG.findall(download_the_html_of(page))
    full_links = (urljoin(page, urldefrag(href)[0]) for href in raw_links)
    return [make_address_consistent(link) for link in full_links if is_a_normal_web_page(link)]


def should_we_follow_links_from(page, home_website):
    """True only when the page belongs to the starting website."""
    return does_this_page_belong_to(home_website, page)


def show_progress(page, depth, how_many_found_so_far):
    """Show live progress on stderr so it never mixes with the final list."""
    print(f"[{how_many_found_so_far:>4}] depth {depth}  {page}", file=sys.stderr)


def should_we_stop_exploring(page, pages_already_visited, depth):
    """True when we should stop this branch of the recursion."""
    return (
        page in pages_already_visited
        or depth > MAXIMUM_DEPTH_ALLOWED
        or len(pages_already_visited) >= MAXIMUM_PAGES_TO_COLLECT
    )


def explore_from_this_page(page, pages_already_visited, home_website, depth):
    """
    The heart of the crawler (recursive).

    Story:
    1. If we should stop → return what we already have.
    2. Remember this page.
    3. Show progress.
    4. Find its links (only if it belongs to our website).
    5. Explore each new link (go one level deeper).
    """
    if should_we_stop_exploring(page, pages_already_visited, depth):
        return pages_already_visited

    pages_now_visited = pages_already_visited | {page}
    show_progress(page, depth, len(pages_now_visited))

    links_to_follow = (
        find_every_link_on(page) if should_we_follow_links_from(page, home_website) else []
    )

    return reduce(
        lambda visited_so_far, next_page: explore_from_this_page(
            next_page, visited_so_far, home_website, depth + 1
        ),
        links_to_follow,
        pages_now_visited,
    )


def collect_every_reachable_page(starting_url):
    """
    Main entry point of the story.

    1. Clean the starting address.
    2. Begin the recursive exploration.
    3. Return every page we discovered (sorted).
    """
    if not is_a_normal_web_page(starting_url):
        raise ValueError(f"Expected an http(s) URL, got: {starting_url!r}")

    starting_page = make_address_consistent(starting_url)
    home_website = the_website_name_of(starting_page)

    return sorted(
        explore_from_this_page(
            starting_page,
            frozenset(),
            home_website,
            depth=0,
        )
    )


if __name__ == "__main__":
    website_to_explore = sys.argv[1] if len(sys.argv) > 1 else "https://www.startupbengal.in"

    for discovered_page in collect_every_reachable_page(website_to_explore):
        print(discovered_page)