import re
import requests
from pyvirtualdisplay import Display
from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

def apk_mirror_selenium_scrape(package_name, app_code=None):
    apk_mirror = "https://www.apkmirror.com"
    response = requests.get(apk_mirror)
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