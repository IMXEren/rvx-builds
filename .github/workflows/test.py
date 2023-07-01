from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Set up Chrome options
chrome_options = Options()
# chrome_options.add_argument("--headless")  # Run Chrome in headless mode

# Create a new instance of the Chrome driver
driver = webdriver.Chrome(options=chrome_options)

# Navigate to a website
driver.get("https://www.apkmirror.com/apk/red-apps-ltd/sync-for-reddit/")

# Find an element by its CSS selector and interact with it
element = driver.find_element(By.CSS_SELECTOR, "h1")
print(element.text)

# Close the browser
driver.quit()
