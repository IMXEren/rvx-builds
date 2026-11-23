"""Morphe Manager's download page resolver."""

from urllib.parse import quote, urljoin, urlsplit

from curl_cffi.requests.exceptions import RequestException
from loguru import logger

from src.downloader.sources import MORPHE_RESOLVER_URL
from src.utils import request_timeout, session

# The resolver only answers Morphe Manager.
RESOLVER_USER_AGENT = "Morphe-Manager/1.0"
# Ends redirect loops.
MAX_HOPS = 6


def resolve_download_page(package_name: str, version: str | None, abi: str, version_code: int | None = None) -> str:
    """Return the mirror page Morphe Manager would open for a build, or an empty string when it has none.

    The resolver answers with a chain of redirects that ends on an APKMirror or Uptodown page, or on a web
    search when it knows no mirror for the build.
    """
    parts = [package_name, version or "any", abi, *([str(version_code)] if version_code else [])]
    resolver_host = urlsplit(MORPHE_RESOLVER_URL).hostname
    url = MORPHE_RESOLVER_URL + quote("~".join(parts), safe="~")
    for _ in range(MAX_HOPS):
        try:
            response = session.head(
                url,
                headers={"User-Agent": RESOLVER_USER_AGENT},
                allow_redirects=False,
                timeout=request_timeout,
            )
        except RequestException as exc:
            logger.debug(f"Morphe resolver request failed for {url}: {exc}")
            return ""
        location: str | None = response.headers.get("location")
        if not location:
            break
        url = urljoin(url, location)
        if urlsplit(url).hostname != resolver_host:
            logger.debug(f"Morphe resolver answered {url} for {package_name} {version or 'any'}")
            return url
    return ""
