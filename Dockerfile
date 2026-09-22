FROM ghcr.io/imxeren/docker-py-revanced-base:latest

# Copy and install Python dependencies
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy entrypoint script
COPY ./entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint && chmod +x /entrypoint

# Copy application code
COPY . .

# Set the default command to run the entrypoint script
CMD [ "bash", "/entrypoint" ]
