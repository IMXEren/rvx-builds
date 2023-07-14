import re
import json
import requests
from bs4 import BeautifulSoup
from pyvirtualdisplay import Display
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

from utils.repo import GitHubRepo
from utils.urls import GitHubURLs

# Constants for GitHub URLs
gh = GitHubRepo()
repo = gh.get_repo()
branch = gh.get_branch()
urls = GitHubURLs(repo, branch)
config_py_file_url = urls.get_config_py()
extras_json_url = urls.get_extras_json

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
    return app_name, app_icon, app_url

def apk_mirror_selenium_scrape(app_code):
    apk_mirror = "https://www.apkmirror.com"
    response = requests.get(config_py_file_url)
    pattern = r'"{}": f"(.*?)",'.format(app_code)
    match = re.search(pattern, response.text)
    if match:
        app_url = match.group(1)
        app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
        print(app_url)
        display = Display(visible=0, size=(800, 600))
        display.start()
        chrome_options = Options()
        # driver = uc.Chrome(headless=True, options=chrome_options)
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(app_url)
        app_name_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.f-grow > h1")
        app_icon_element = driver.find_element(By.CSS_SELECTOR, "#masthead > header > div > div > div.p-relative.icon-container > img")
        app_name = app_name_element.text if app_name_element else "NA"
        app_icon = app_icon_element.get_attribute("src") if app_icon_element else "NA"
        app_icon = app_icon.replace("&w=96&h=96", "&w=64&h=64")
        driver.quit()
        display.stop()
        print("App Name:", app_name, flush=True)
        print("Icon URL:", app_icon, flush=True)
        return app_name, app_icon, app_url
    else:
        print("APKMirror URL not found for the specified app code")

def apk_mirror_requests_scrape(app_code):
    apk_mirror = "https://www.apkmirror.com"
    response = requests.get(config_py_file_url)
    pattern = r'"{}": f"(.*?)",'.format(app_code)
    match = re.search(pattern, response.text)
    if match:
        app_url = match.group(1)
        app_url = app_url.replace("{self.apk_mirror}", apk_mirror)
        print(app_url)
        s = requests
        hdr = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Encoding': 'none',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            }
        r = s.get(app_url, headers=hdr)
        soup = BeautifulSoup(r.text, "html.parser")
        app_name_element = soup.select_one("#masthead > header > div > div > div.f-grow > h1")
        app_icon_element = soup.select_one("#masthead > header > div > div > div.p-relative.icon-container > img")
        if app_icon_element:
            app_icon = app_icon_element["src"] if app_icon_element else ""
            app_icon = f'{apk_mirror}{app_icon.replace("&w=96&h=96", "&w=64&h=64")}'
        if app_name_element:
            app_name = app_name_element.text
        print("App Name:", app_name, flush=True)
        print("Icon URL:", app_icon, flush=True)
        return app_name, app_icon, app_url
    else:
        print("APKMirror URL not found for the specified app code")

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
        apk_mirror_requests_scrape, 
        apk_mirror_selenium_scrape,
    ]
    
    # Ordered List of parameter variables
    params = [
        (key, value, extras_json_url,),
        (package_name,),
        (code_name,),
        (code_name,),
    ]
    
    # Calling functions with parameter variables
    for scraper, param in zip(scrapers, params):
        # print("Scraper:", scraper.__name__)
        # print("Params:", param)
        try:
            if scraper == get_json_data:
                result = scraper(*param)
                app_name, app_icon, app_url = result[0]['app_name'], result[0]['app_icon'], result[0]['app_url']
            else:
                app_name, app_icon, app_url = scraper(*param)
            break
        except Exception as e:
            app_name, app_icon, app_url = "NA", "NA", "NA"
            # print("ERROR:", str(e))
            continue
    return app_name, app_icon, app_url