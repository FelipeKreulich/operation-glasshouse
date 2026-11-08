FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*

COPY beacon /opt/beacon
RUN chmod +x /opt/beacon

WORKDIR /opt
CMD ["./beacon"]
