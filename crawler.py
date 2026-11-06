
import sys
import time
import sqlite3
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

DB = "database.db"
HEADERS = {
    "User-Agent": "ShivkantSearchBot/0.1"
}

def allowed_by_robots(url):
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"

    try:
        response = requests.get(
            robots_url, headers=HEADERS, timeout=10
        )

        if response.status_code == 404:
            return True

        if response.status_code != 200:
            return False

        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(response.text.splitlines())

        return parser.can_fetch(HEADERS["User-Agent"], url)

    except requests.RequestException:
        return False

def save_page(title, url, description, content):
    with sqlite3.connect(DB) as con:
        con.execute("""
        INSERT INTO pages(title, url, description, content)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            content=excluded.content
        """, (title, url, description, content))

def crawl(start_url):
    parsed = urlparse(start_url)

    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        print("Invalid URL")
        return

    domain = parsed.netloc
    queue = [start_url]
    visited = set()

    while queue and len(visited) < 20:
        url = queue.pop(0)

        if url in visited:
            continue

        if urlparse(url).netloc != domain:
            continue

        visited.add(url)

        if not allowed_by_robots(url):
            print("Robots permission denied:", url)
            continue

        try:
            response = requests.get(
                url, headers=HEADERS, timeout=15
            )

            if response.status_code != 200:
                continue

            if "text/html" not in response.headers.get(
                "Content-Type", ""
            ):
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()

            title = (
                soup.title.get_text(" ", strip=True)
                if soup.title else url
            )

            description_tag = soup.find(
                "meta", attrs={"name": "description"}
            )

            description = (
                description_tag.get("content", "")
                if description_tag else ""
            )

            content = soup.get_text(" ", strip=True)[:20000]

            save_page(title, url, description, content)
            print("Saved:", title)

            for link in soup.find_all("a", href=True):
                next_url = urljoin(url, link["href"]).split("#")[0]
                next_parts = urlparse(next_url)

                if (
                    next_parts.scheme in ("http", "https")
                    and next_parts.netloc == domain
                    and next_url not in visited
                ):
                    queue.append(next_url)

            time.sleep(2)

        except requests.RequestException as error:
            print("Error:", error)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python crawler.py https://example.com")
    else:
        crawl(sys.argv[1])
