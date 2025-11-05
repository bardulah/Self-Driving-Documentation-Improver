"""Web exploration module using browser automation."""

import asyncio
from typing import List, Set, Optional
from urllib.parse import urljoin, urlparse
import logging

try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from bs4 import BeautifulSoup

from doc_improver.models import WebPage, ExplorationConfig
from doc_improver.utils.logger import setup_logger

logger = setup_logger(__name__)


class WebExplorer:
    """Explores websites using browser automation to find documentation."""

    def __init__(self, config: ExplorationConfig):
        """Initialize web explorer.

        Args:
            config: Exploration configuration
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is not installed. Install it with: pip install playwright && playwright install"
            )

        self.config = config
        self.start_url = config.target_path_or_url
        self.visited_urls: Set[str] = set()
        self.pages: List[WebPage] = []
        self.base_domain = urlparse(self.start_url).netloc

    async def explore(self) -> List[WebPage]:
        """Explore the website starting from the configured URL.

        Returns:
            List of discovered web pages
        """
        logger.info(f"Exploring website: {self.start_url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                await self._explore_url(browser, self.start_url, depth=0)
            finally:
                await browser.close()

        logger.info(f"Explored {len(self.pages)} pages")
        return self.pages

    async def _explore_url(self, browser: Browser, url: str, depth: int) -> None:
        """Recursively explore a URL and its links.

        Args:
            browser: Playwright browser instance
            url: URL to explore
            depth: Current exploration depth
        """
        # Check depth limit
        if depth > self.config.max_depth:
            return

        # Skip if already visited
        if url in self.visited_urls:
            return

        # Skip external domains unless configured
        if not self._should_explore_url(url):
            return

        self.visited_urls.add(url)
        logger.debug(f"Exploring: {url} (depth: {depth})")

        try:
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await self._analyze_page(page, url, depth, browser)
            finally:
                await page.close()
        except Exception as e:
            logger.warning(f"Error exploring {url}: {e}")

    async def _analyze_page(self, page: Page, url: str, depth: int, browser: Browser) -> None:
        """Analyze a web page for documentation content.

        Args:
            page: Playwright page instance
            url: Page URL
            depth: Current depth
            browser: Browser instance for recursive exploration
        """
        # Get page content
        content = await page.content()
        title = await page.title()

        # Parse with BeautifulSoup
        soup = BeautifulSoup(content, 'html.parser')

        # Extract text content
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        text_content = soup.get_text(separator='\n', strip=True)

        # Extract links
        links = []
        if self.config.follow_links:
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(url, link['href'])
                if self._should_explore_url(absolute_url):
                    links.append(absolute_url)

        # Analyze documentation completeness
        has_docs, score = self._analyze_documentation_quality(soup, text_content)

        # Create WebPage object
        web_page = WebPage(
            url=url,
            title=title,
            content=text_content[:5000],  # Limit content size
            links=links,
            has_docs=has_docs,
            doc_completeness_score=score,
        )

        self.pages.append(web_page)

        # Recursively explore links
        if self.config.follow_links and depth < self.config.max_depth:
            tasks = []
            for link in links[:10]:  # Limit concurrent explorations
                if link not in self.visited_urls:
                    tasks.append(self._explore_url(browser, link, depth + 1))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    def _should_explore_url(self, url: str) -> bool:
        """Check if URL should be explored.

        Args:
            url: URL to check

        Returns:
            True if should be explored
        """
        parsed = urlparse(url)

        # Skip non-http(s) URLs
        if parsed.scheme not in ['http', 'https']:
            return False

        # Skip files
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in ['.pdf', '.zip', '.jpg', '.png', '.gif', '.mp4']):
            return False

        # Only explore same domain (unless configured otherwise)
        if parsed.netloc != self.base_domain:
            return False

        return True

    def _analyze_documentation_quality(self, soup: BeautifulSoup, text: str) -> tuple[bool, float]:
        """Analyze the quality and presence of documentation.

        Args:
            soup: BeautifulSoup parsed content
            text: Text content

        Returns:
            Tuple of (has_docs, completeness_score)
        """
        score = 0.0
        indicators = 0

        # Check for documentation indicators
        doc_keywords = [
            'api', 'documentation', 'guide', 'tutorial', 'reference',
            'getting started', 'installation', 'usage', 'examples'
        ]

        text_lower = text.lower()
        for keyword in doc_keywords:
            if keyword in text_lower:
                score += 0.1
                indicators += 1

        # Check for code examples
        code_blocks = soup.find_all(['code', 'pre'])
        if code_blocks:
            score += min(len(code_blocks) * 0.05, 0.3)

        # Check for structured content (headings)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
        if headings:
            score += min(len(headings) * 0.02, 0.2)

        # Check for lists (often used in documentation)
        lists = soup.find_all(['ul', 'ol'])
        if lists:
            score += min(len(lists) * 0.02, 0.1)

        # Check content length
        if len(text) > 500:
            score += 0.1
        if len(text) > 2000:
            score += 0.1

        score = min(score, 1.0)
        has_docs = indicators > 0 or len(code_blocks) > 0

        return has_docs, score

    def get_pages_needing_docs(self, threshold: float = 0.5) -> List[WebPage]:
        """Get pages that need better documentation.

        Args:
            threshold: Completeness score threshold

        Returns:
            List of pages below threshold
        """
        return [p for p in self.pages if p.doc_completeness_score < threshold]

    def get_pages_without_docs(self) -> List[WebPage]:
        """Get pages with no documentation.

        Returns:
            List of pages without documentation
        """
        return [p for p in self.pages if not p.has_docs]


def explore_website_sync(config: ExplorationConfig) -> List[WebPage]:
    """Synchronous wrapper for website exploration.

    Args:
        config: Exploration configuration

    Returns:
        List of discovered web pages
    """
    explorer = WebExplorer(config)
    return asyncio.run(explorer.explore())
