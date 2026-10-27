FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends curl xz-utils \
    && curl -sL https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz \
       | tar -xJ --strip-components=1 -C /usr/local/bin/ --wildcards '*/ffmpeg' '*/ffprobe' \
    && apt-get purge -y curl xz-utils && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir '.[dev]'
COPY alembic.ini ./
COPY alembic ./alembic
COPY tests ./tests
RUN useradd --create-home trace
USER trace
