FROM nikhilbadyal/docker-py-revanced-base

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium runtime libraries
    libasound2 libatk-bridge2.0-0 libatk1.0-0 libatspi2.0-0 \
    libcairo2 libcups2 libdbus-1-3 libdrm2 libgbm1 libglib2.0-0 \
    libnspr4 libnss3 libpango-1.0-0 libx11-6 libxcb1 \
    libxcomposite1 libxdamage1 libxext6 libxfixes3 \
    libxkbcommon0 libxrandr2 libx11-xcb1 \
    gnupg unzip \
    # Fonts
    fonts-liberation fonts-noto-color-emoji fonts-unifont \
    fonts-freefont-ttf fonts-ipafont-gothic fonts-wqy-zenhei \
    fonts-tlwg-loma-otf libfontconfig1 libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

## Extra fonts
COPY fonts.zi[p] /tmp/
RUN if [ -f /tmp/fonts.zip ]; then \
        mkdir -p /usr/share/fonts/windows && \
        unzip -q /tmp/fonts.zip -d /usr/share/fonts/windows/ && \
        fc-cache -f && \
        rm /tmp/fonts.zip; \
    fi

# Copy and install Python dependencies
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

## CloakBrowser
ENV CLOAKBROWSER_AUTO_UPDATE="false"
RUN python -c "from cloakbrowser import ensure_binary; ensure_binary()" \
    && mkdir -p ~/.cloakbrowser/geoip \
    && curl -L -o ~/.cloakbrowser/geoip/GeoLite2-City.mmdb "https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb"

# Copy entrypoint script
COPY ./entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

# Copy application code
COPY . ${APP_HOME}

# Set the default command to run the entrypoint script
CMD [ "bash", "/entrypoint" ]
