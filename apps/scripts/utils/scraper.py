import re
import json
import requests
from bs4 import BeautifulSoup
from loguru import logger

from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

# Constants for GitHub URLs
gh = GitHubRepo()
repo = gh.get_repo()
branch = gh.get_branch()
urls = GitHubURLs(repo, branch)
config_py_url = urls.get_config_py()
extras_json_url = urls.get_extras_json()

def gplay_scrape(package_name):
    app_url = f"https://play.google.com/store/apps/details?id={package_name}"
    response = requests.get(app_url)
    soup = BeautifulSoup(response.text, "html.parser")
    app_name_element = soup.select_one("h1 > span")
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
    response = requests.get(config_py_url)
    pattern = r'"{}": f"(.*?)",'.format(app_code)
    match = re.search(pattern, response.text)
    app_url = ""
    if match:
        app_url = match.group(1)
        app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
    if len(app_url) == 0:
        try:
            result = get_json_data("app_package", package_name, extras_json_url)
            app_url = result[0]['app_url']
        except Exception as e:
            # print("APKMScrape:", str(e))
            pass
    if app_url:
        # print(app_url)
        s = requests
        hdr = {'User-Agent': 'anything'}
        r = s.get(app_url, headers=hdr)
        soup = BeautifulSoup(r.text, "html.parser")
        app_name_element = soup.select_one("#masthead > header > div > div > div.f-grow > h1")
        app_icon_element = soup.select_one("#masthead > header > div > div > div.p-relative.icon-container > img")
        if app_icon_element:
            app_icon = app_icon_element["src"] if app_icon_element else ""
            app_icon = f'{apk_mirror}{app_icon.replace("&w=96&h=96", "&w=64&h=64")}'
        if app_name_element:
            app_name = app_name_element.text
        logger.debug(app_name)
        # print("App Name:", app_name, flush=True)
        # print("Icon URL:", app_icon, flush=True)
        return app_name, app_icon, app_url
    else:
        logger.warning("APKMirror URL not found for the specified app code - {} and package - {}", app_code, package_name)

def apksos_scrape(package_name):
    app_url = f"https://apksos.com/app/{package_name}"
    response = requests.get(app_url)
    soup = BeautifulSoup(response.text, "html.parser")
    app_name_element = soup.select_one("body > div > div > div > div > div.col-sm-12.col-md-8 > div:nth-child(2) > div:nth-child(1)")
    app_icon_element = soup.select_one("body > div img")
    if app_icon_element:
        app_icon = app_icon_element["src"] if app_icon_element else ""
        app_icon = app_icon.replace("_1.png", "_2.png")
    if app_name_element:
        app_name = app_name_element.text
        app_name = re.sub(r'.*?\n\s+', '', app_name).strip()
    logger.debug(app_name)
    return app_name, app_icon, app_url

def get_json_data(key, value, url):
    response = requests.get(url)
    data = response.json()
    matched_objects = [obj for obj in data if obj.get(key) == value]
    return matched_objects

def scraper(package_name, code_name):
    # Parameter variables    
    key = "app_package"
    value = package_name
    
    # Ordered List of functions
    scrapers = [
        get_json_data, 
        gplay_scrape, 
        apkm_scrape,
        apksos_scrape,
    ]
    
    # Ordered List of parameter variables
    params = [
        (key, value, extras_json_url,),
        (package_name,),
        (package_name, code_name,),
        (package_name,),
    ]
    
    # Calling functions with parameter variables
    for scraper, param in zip(scrapers, params):
        # print("Scraper:", scraper.__name__)
        # print("Params:", param)
        try:
            if scraper == get_json_data:
                result = scraper(*param)
                app_name, app_icon, app_url = result[0]['app_name'], result[0]['app_icon'], result[0]['app_url']
                logger.debug(app_name)
            else:
                app_name, app_icon, app_url = scraper(*param)
            break
        except Exception as e:
            app_name, app_icon, app_url = "NA", "NA", "NA"
            # print("ERROR:", str(e))
            continue
    return app_name, app_icon, app_url