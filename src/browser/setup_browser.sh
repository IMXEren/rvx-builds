#!/bin/bash

check_browser_dependencies() {
    echo "Checking browser dependencies..."
    if [[ -n "$browser" ]]; then
        if command -v "$browser" >/dev/null 2>&1; then
            echo "Already installed $($browser --version)"
        else
            echo "Installing $browser..."
            install_browser "$browser"
        fi
    fi
    if [[ -n "$webdriver" ]]; then
        if command -v "$webdriver" >/dev/null 2>&1; then
            echo "Already installed $($webdriver --version)"
        else
            echo "Installing $webdriver..."
            install_webdriver
        fi
    fi
}

install_browser() {
    case "$browser" in
        google-chrome)
            install_chrome
            ;;
        chromium-browser)
            install_chromium
            ;;
        *)
            echo "[ERROR] Unknown browser: $browser" >&2
            exit 1
            ;;
    esac
}

install_webdriver() {
    case "$webdriver" in
        chromedriver)
            install_chromedriver
            ;;
        *)
            echo "[ERROR] Unknown webdriver: $webdriver" >&2
            exit 1
            ;;
    esac
}

install_chrome() {
    sudo apt-get remove google-chrome-stable
    sudo curl -sS -o - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add
    echo "deb http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee -a /etc/apt/sources.list.d/google-chrome.list
    sudo apt-get -y update
    sudo apt-get -y --no-install-recommends install google-chrome-stable
    echo "Installed $(google-chrome --version)"
}

install_chromium() {
    sudo apt-get -y update
    sudo apt-get -y --no-install-recommends install chromium
    echo "Installed $(chromium --version)"
}

install_chromedriver() {
    if ! command -v google-chrome >/dev/null 2>&1; then
        echo "Google Chrome not installed but required! Exiting..." >&2
        exit 1
    fi
    CHROMEDRIVER_VERSION=$(google-chrome --version | awk '{print $3}')
    delete_executable chromedriver
    echo "Proceeding to install chromedriver..."
    curl -# -o ~/chromedriver-linux64.zip "https://storage.googleapis.com/chrome-for-testing-public/${CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip"
    unzip ~/chromedriver-linux64.zip -d ~/
    rm ~/chromedriver-linux64.zip
    sudo mv -f ~/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
    sudo chown root:root /usr/local/bin/chromedriver
    sudo chmod 0755 /usr/local/bin/chromedriver
    echo "Installed $(chromedriver --version)"
}

delete_executable() {
    local exec_name="$1"
    local exec_path
    exec_path=$(which "$exec_name")
    if [[ -n "$exec_path" ]]; then
        sudo rm "$exec_path" 2>/dev/null && echo "Deleted $exec_name: $exec_path" || echo "Couldn't find $exec_name to delete: $exec_path"
    else
        echo "Executable '$exec_name' not found to delete." >&2
    fi
}

browser="$1"
webdriver="$2"
check_browser_dependencies
exit 0
