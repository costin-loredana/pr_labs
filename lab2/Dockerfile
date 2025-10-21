FROM python:3.11-slim

WORKDIR /app

COPY . /app

EXPOSE 8000

ENV SERVE_DIR files

CMD ["python", "web-server.py", "files"]
