FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

RUN apt-get update && apt-get install -y \
    python3 python3-venv python3-pip \
    git \
    ffmpeg \
    libgl1 \
    libopengl0 \
    libegl1 \
    libglib2.0-0 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git config --global --add safe.directory /app

# Create a virtual environment for pip installs (PEP 668-safe)
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# install playwright deps
RUN playwright install --with-deps chromium

COPY . .

RUN find bot/data/Binaries/Linux/CHOpt/ bot/data/Binaries/Linux/FFmpeg/bin/ \
    -type f \( -name "*.sh" -o -not -name "*.*" \) -exec chmod +x {} +

CMD ["python", "festivalinfobot.py"]