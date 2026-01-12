FROM nikhilbadyal/docker-py-revanced-base

# Copy and install Python dependencies
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

## Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gnupg unzip libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# Install chrome
COPY ./src/browser/setup_browser.sh /setup_browser.sh
RUN sed -i 's/\r$//g' /setup_browser.sh && \
    sed -i 's/sudo\s//g' /setup_browser.sh && \
    chmod +x /setup_browser.sh && \
    /setup_browser.sh "google-chrome"

# Copy entrypoint script
COPY ./entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

# Copy application code
COPY . ${APP_HOME}

# Set the default command to run the entrypoint script
CMD [ "bash", "/entrypoint" ]
