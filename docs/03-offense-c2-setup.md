# Offense: C2 Setup

## Overview

This document covers the setup of the Sliver C2 server, the first component of the offensive side of Operation GLASSHOUSE. The server runs as a Docker container, isolated on the 'net-c2' network, with no direct access to the host's LAN or the internet.

## Why Sliver

Sliver was chosen because it is a open-source, actively maintained by Bishop Fox, support multiples transport protocols (mTLS, HTTP/HTTPS, DNS, etc...), and include built-in support for malleable C2 profile and beacon jitter.

## Building the C2 Server Container

### Initial approach: pre-built Docker image

The first attempt used the official Docker image (`ghcr.io/bishopfox/sliver:latest`), but it returned a `denied` error from the registry, indicating the image is not publicly accessible under that path.

### Second approach: build from source inside the container

The next attempt installed Sliver via its official install script (`curl https://sliver.sh/install | bash`) inside a Debian-based Dockerfile. This triggered a full local build, which placed sustained high load on the Raspberry Pi 5's CPU. Combined with an underpowered power supply, this caused the board to lose power entirely mid-build — confirmed afterwards via:

```bash
vcgencmd get_throttled
# throttled=0x50000
```

This value indicates both undervoltage and throttling had occurred since the last boot. The takeaway: any sustained heavy compilation task should be avoided without a proper 27W USB-C PD power supply for the Pi 5.

### Final approach: pre-compiled binary download

To avoid any local compilation, the Dockerfile was rewritten to simply download the pre-compiled `linux-arm64` server binary directly from Sliver's GitHub releases:

```dockerfile
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
```

This approach is both lighter on the CPU and avoids the power-related crash entirely.

### Debugging the binary name

The first attempt at this Dockerfile used an incorrect filename (`silver-server` instead of `sliver-server`), which caused the container to crash-loop with an `exec format error`. The correct asset name, confirmed directly from the GitHub releases page, is: sliver-server_linux-arm64

## Docker Compose Configuration

```yaml
networks:
  net-offense:
    driver: bridge
    internal: true
  net-c2:
    driver: bridge
    internal: true
  net-detection:
    driver: bridge

volumes:
  sliver-data:

services:
  sliver-c2:
    build:
      context: ./c2
    container_name: sliver-c2
    hostname: sliver-c2
    networks:
      - net-c2
    volumes:
      - sliver-data:/root/.sliver
    stdin_open: true
    tty: true
    restart: unless-stopped
```

The `net-c2` network is marked `internal: true`, meaning the container has no route to the internet or the host's LAN — it only communicates with other containers explicitly attached to the same network.

## Verifying the Setup

```bash
docker compose up -d sliver-c2
docker ps
docker exec -it sliver-c2 sliver-server
```

On first run, the Sliver server generates its internal certificates and configuration, then drops into its interactive console:

Sliver >

## Lessons Learned

- Always verify the exact asset filename from a project's releases page before scripting a download — naming conventions are not always intuitive.
- Heavy local compilation on a Raspberry Pi can expose power supply limitations that aren't obvious under light workloads.
- Preferring pre-compiled binaries over local builds, when available, reduces both build time and hardware stress.

## Status

✅ Sliver C2 server running in an isolated container.

🚧 Next: configure a listener and generate the first beacon implant.
