FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -L -o /usr/local/bin/sliver-server \
    https://github.com/BishopFox/sliver/releases/latest/download/sliver-server_linux-arm64 \
    && chmod +x /usr/local/bin/sliver-server

WORKDIR /root

CMD ["sliver-server"]
