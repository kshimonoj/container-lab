FROM python:3.11-slim

# ContainerLab インストール
RUN apt-get update && apt-get install -y \
    curl wget git iproute2 \
    && rm -rf /var/lib/apt/lists/*

RUN bash -c "$(curl -sL https://get.containerlab.dev)"

# docker CLI（クライアントのみ静的バイナリ）。lab_manager が docker ps/inspect を使用する
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
    | tar xz --strip-components=1 -C /usr/local/bin docker/docker \
    && docker --version

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

EXPOSE 8888

CMD ["uvicorn", "main:app", "--app-dir", "/app/backend", "--host", "0.0.0.0", "--port", "8888", "--reload"]
