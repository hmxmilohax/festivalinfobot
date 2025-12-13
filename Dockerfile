# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
# ffmpeg: required for audio processing (fallback if local binary missing)
# libgl1-mesa-glx: often required for Qt apps (like CHOpt) to run, even headlessly
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libgl1 \
    libopengl0 \
    libegl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Configure git to trust the /app directory (fixes "dubious ownership" error in Docker)
RUN git config --global --add safe.directory /app

# Copy the requirements file into the container at /app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Grant execution permissions to the Linux CHOpt script
# Adjust the path if your structure is different, but this matches the user's setup
RUN chmod +x bot/data/Binaries/Linux/CHOpt/CHOpt.sh
RUN chmod +x bot/data/Binaries/Linux/FFmpeg/bin/ffmpeg
RUN chmod +x bot/data/Binaries/Linux/FFmpeg/bin/ffprobe

# Run the bot
CMD ["python", "festivalinfobot.py"]
