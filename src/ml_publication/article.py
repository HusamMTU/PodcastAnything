"""Fetch and extract readable article text."""
from __future__ import annotations

import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup


class ArticleError(RuntimeError):
    pass


def fetch_html(url: str, timeout_sec: int = 20) -> str:
    if not url.startswith(("http://", "https://")):
        raise ArticleError("source_url must start with http:// or https://")

    try:
        resp = requests.get(
            url,
            timeout=timeout_sec,
            headers={"User-Agent": "ml-publication-bot"},
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        raise ArticleError(f"Failed to fetch article from {url}: {exc}") from exc


def _clean_text(lines: Iterable[str]) -> str:
    """Clean and normalize text lines."""
    joined = "\n".join(line.strip() for line in lines if line.strip())
    return re.sub(r"\n{3,}", "\n\n", joined).strip()


def extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
        tag.decompose()

    article = soup.find("article")
    if article:
        paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p")]
        text = _clean_text(paragraphs)
        if text:
            return text

    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = _clean_text(paragraphs)
    if not text:
        raise ArticleError("No readable text found in the article.")
    return text
