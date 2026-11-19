# ---------------------------------------------------------------
# Docker image for ConcurrencyBugBench
# ---------------------------------------------------------------
FROM python:3.11-slim

ARG USERNAME=appuser
ARG UID=1000
ARG GID=1000
RUN addgroup --gid ${GID} ${USERNAME} \
    && adduser --uid ${UID} --gid ${GID} --disabled-password --gecos "" ${USERNAME}

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

USER ${USERNAME}

CMD ["python", "run_eval.py", "--help"]
