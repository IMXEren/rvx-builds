import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger

from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

sys.path.append(str(Path.cwd()))
from src.downloader import sources

# Constants for GitHub URLs
gh = GitHubRepo
repo = gh.get_repo()
branch = gh.get_backup_branch()
urls = GitHubURLs(repo, branch)
sources_py_url = urls.get_sources_py()
extras_json_url = urls.get_extras_json()


def gplay_scrape(package_name):
    app_url = f"https://play.google.com/store/apps/details?id={package_name}"
    response = requests.get(app_url)
    soup = BeautifulSoup(response.text, "html.parser")
    app_name_element = soup.select_one("h1")
    app_icon_element = soup.select_one("div.Il7kR > img")
    if app_icon_element is None:
        app_icon_element = soup.select_one("div.qxNhq > img")
    if app_icon_element:
        app_icon = app_icon_element["src"] if app_icon_element else ""
        app_icon = app_icon.replace("=w240-h480", "=w64-h64")
    if app_name_element:
        app_name = app_name_element.text
    logger.debug(app_name)
    return app_name, app_icon, app_url


def apkm_scrape(package_name, app_code):
    apk_mirror = "https://www.apkmirror.com"
    response = requests.get(sources_py_url)
    pattern = rf'"{app_code}": f"(.*?)",'
    match = re.search(pattern, response.text)
    app_url = ""
    if match:
        app_url = match.group(1)
        app_url = app_url.replace("{APK_MIRROR_BASE_APK_URL}", f"{apk_mirror}/apk")
    if len(app_url) == 0:
        try:
            result = get_json_data("app_package", package_name, extras_json_url)
            app_url = result[0]["app_url"]
        except Exception:
            pass
    if app_url:
        s = requests
        hdr = {"User-Agent": "anything"}
        r = s.get(app_url, headers=hdr)
        soup = BeautifulSoup(r.text, "html.parser")
        app_name_element = soup.select_one("#masthead > header > div > div > div.f-grow > h1")
        app_icon_element = soup.select_one("#masthead > header > div > div > div.p-relative.icon-container > img")
        if app_icon_element:
            app_icon = app_icon_element["src"] if app_icon_element else ""
            app_icon = f"{apk_mirror}{app_icon.replace('&w=96&h=96', '&w=64&h=64')}"
        if app_name_element:
            app_name = app_name_element.text
        logger.debug(app_name)
        # print("App Name:", app_name, flush=True)
        # print("Icon URL:", app_icon, flush=True)
        return app_name, app_icon, app_url
    logger.warning(f"APKMirror URL not found for the specified app code - {app_code} and package - {package_name}")
    return None


def uptodown_scrape(app_code):
    if (app_url := sources.apk_sources.get(app_code, None)) and app_url == (sources.UPTODOWN_BASE_URL.format(app_code)):
        response = requests.get(app_url)
        soup = BeautifulSoup(response.text, "html.parser")
        app_name_element = soup.select_one("h1#detail-app-name")
        app_icon_element = soup.select_one("body > div > main > div.c1 > div.detail > div.icon > img")
        if app_icon_element:
            app_icon = app_icon_element["src"] if app_icon_element else ""
            app_icon = f"{app_icon}:64"
        if app_name_element:
            app_name = app_name_element.text.strip()
        logger.debug(app_name)
        return app_name, app_icon, app_url
    logger.warning(f"Uptodown URL not found for the specified app code - {app_code}")
    return None


def apksos_scrape(package_name):
    app_url = f"https://apksos.com/app/{package_name}"
    response = requests.get(app_url)
    soup = BeautifulSoup(response.text, "html.parser")
    app_name_element = soup.select_one(
        "body > div > div > div > div > div.col-sm-12.col-md-8 > div:nth-child(2) > div:nth-child(1)",
    )
    app_icon_element = soup.select_one("body > div img")
    if app_icon_element:
        app_icon = app_icon_element["src"] if app_icon_element else ""
        app_icon = app_icon.replace("_1.png", "_2.png")
    if app_name_element:
        app_name = app_name_element.text
        app_name = re.sub(r".*?\n\s*?", "", app_name).strip()
    logger.debug(app_name)
    return app_name, app_icon, app_url


def get_json_data(key, value, url):
    response = requests.get(url)
    data = response.json()
    return [obj for obj in data if obj.get(key) == value]


def scraper(package_name, code_name):
    # Parameter variables
    key = "app_package"
    value = package_name

    # Ordered List of functions
    scrapers = [
        get_json_data,
        gplay_scrape,
        apkm_scrape,
        uptodown_scrape,
        apksos_scrape,
    ]

    # Ordered List of parameter variables
    params = [
        (
            key,
            value,
            extras_json_url,
        ),
        (package_name,),
        (
            package_name,
            code_name,
        ),
        (code_name,),
        (package_name,),
    ]

    # Calling functions with parameter variables
    for scraper_fn, param in zip(scrapers, params, strict=False):
        try:
            if scraper_fn == get_json_data:
                result = scraper_fn(*param)
                app_name, app_icon, app_url = result[0]["app_name"], result[0]["app_icon"], result[0]["app_url"]
                logger.debug(app_name)
            else:
                app_name, app_icon, app_url = scraper_fn(*param)
            break
        except Exception:
            icon = "https://img.icons8.com/bubbles/64/android-os.png"
            url = f"https://play.google.com/store/apps/details?id={package_name}"
            name = "Unavailable"
            app_name, app_icon, app_url = name, icon, url
            continue
    return app_name, app_icon, app_url


if __name__ == "__main__":
    pass
