FROM python:3.12.6-slim

# Set working directory inside container
WORKDIR /

# Copy only the app directory into the container
COPY . .

# Set working directory to the app folder
WORKDIR /

# Install dependencies if needed
RUN apt-get update && apt-get install -y \
    wget \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libxshmfence1 \
    libxss1 \
    libgtk-3-0 \
    fonts-liberation \
    libappindicator3-1 \
    libnss3-tools \
    && apt-get clean

RUN pip install --default-timeout=300 -r requirements.txt
RUN playwright install chromium

# Run your script
CMD ["python", "telebot.py"]
