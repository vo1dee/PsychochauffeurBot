# Dockerfile for PsychochauffeurBot
# Pinned to bookworm: wkhtmltopdf (wkhtmltoimage for /flares) is not packaged in trixie.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime tools the bot shells out to: ffmpeg (video processing),
# wkhtmltoimage (screenshots), gcc/g++ for wheels without prebuilt binaries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    ffmpeg \
    wkhtmltopdf \
    fontconfig \
    fonts-dejavu-core \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Deno: yt-dlp needs a JavaScript runtime to solve YouTube's player challenges;
# without it YouTube returns no usable formats and every download fails.
COPY --from=denoland/deno:bin-2.9.7 /deno /usr/local/bin/deno

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as an unprivileged user whose UID matches the host owner of mounted volumes
ARG APP_UID=1000
RUN useradd --uid ${APP_UID} --create-home --shell /usr/sbin/nologin bot

COPY --chown=bot:bot . .

RUN mkdir -p logs downloads data config/private config/group config/backups config/archive \
    && chown -R bot:bot /app

USER bot

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}

CMD ["python", "main.py"]
