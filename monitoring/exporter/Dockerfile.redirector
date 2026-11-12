FROM nginx:alpine

RUN apk add --no-cache tcpdump python3 py3-pip

RUN pip install --no-cache-dir --break-system-packages scapy prometheus_client

COPY nginx.conf /etc/nginx/nginx.conf
COPY exporter.py /opt/exporter.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
