FROM python:3.12-slim-bookworm
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends kicad openscad ngspice ca-certificates && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 10001 engineer && useradd -u 10001 -g engineer -m engineer
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
RUN mkdir -p /projects && chown engineer:engineer /projects
USER engineer
EXPOSE 8767
CMD ["python", "server.py"]
