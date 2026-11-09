# Operation GLASSHOUSE

```
___________________________________________________
@@@@@@@@@@@@@@@@@@@@@**^^""~~~"^@@^*@*@@**@@@@@@@@@
@@@@@@@@@@@@@*^^'"~   , - ' '; ,@@b. '  -e@@@@@@@@@
@@@@@@@@*^"~      . '     . ' ,@@@@(  e@*@@@@@@@@@@
@@@@@^~         .       .   ' @@@@@@, ~^@@@@@@@@@@@
@@@~ ,e**@@*e,  ,e**e, .    ' '@@@@@@e,  "*@@@@@'^@
@',e@@@@@@@@@@ e@@@@@@       ' '*@@@@@@    @@@'   0
@@@@@@@@@@@@@@@@@@@@@',e,     ;  ~^*^'    ;^~   ' 0
@@@@@@@@@@@@@@@^""^@@e@@@   .'           ,'   .'  @
@@@@@@@@@@@@@@'    '@@@@@ '         ,  ,e'  .    ;@
@@@@@@@@@@@@@' ,&&,  ^@*'     ,  .  i^"@e, ,e@e  @@
@@@@@@@@@@@@' ,@@@@,          ;  ,& !,,@@@e@@@@ e@@
@@@@@,~*@@*' ,@@@@@@e,   ',   e^~^@,   ~'@@@@@@,@@@
@@@@@@, ~" ,e@@@@@@@@@*e*@*  ,@e  @@""@e,,@@@@@@@@@
@@@@@@@@ee@@@@@@@@@@@@@@@" ,e@' ,e@' e@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@" ,@" ,e@@e,,@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@~ ,@@@,,0@@@@@@@@@@@@@@@@@@@
@@@@@@@@@@@@@@@@@@@@@@@@,,@@@@@@@@@@@@@@@@@@@@@@@@@
"""""""""""""""""""""""""""""""""""""""""""""""""""
```

> Red team C2 infrastructure with evasion techniques, paired with a
> self-detection blue team pipeline — offense and defense in one closed-lab
> project.

Everything here runs in one isolated Docker network on a Raspberry Pi 5.
The premise: build a realistic beacon-based C2 chain (redirector + malleable
profile + jitter), then build the detector that catches it — using nothing
but connection-timing metadata, no payload inspection, no prior knowledge of
the C2 profile.

---

## Architecture

```
  [ target ]  --(beacon, HTTP)-->  [ redirector ]  --(proxy_pass)-->  [ sliver-c2 ]
  net-offense                      net-offense + net-c2                 net-c2

                                         |
                                         v
                                  [ tcpdump capture ]
                                         |
                                         v
                              [ detection/analyze_beacon.py ]
```

- **target** — runs the Sliver beacon implant (linux/arm64), isolated on
  `net-offense`, no direct route to the C2 server.
- **redirector** — nginx reverse proxy, multi-homed across `net-offense`
  and `net-c2`. Stands in for the kind of domain-fronting / redirector
  infrastructure a real operator would use to hide the C2 server's real
  address. Also where traffic is captured for the blue team side.
- **sliver-c2** — [Sliver](https://github.com/BishopFox/sliver) C2 server,
  only reachable through the redirector, never directly by the target.
- **detection** — a standalone Python pipeline that takes a raw pcap and
  decides, from timing alone, whether it's looking at a beacon.

Full writeup of each piece is in [`docs/`](docs/).

## Why this setup

Most "build your own C2" writeups stop at "it works." The interesting
question is the next one: **if I were defending this network, could I catch
myself?** So this project is split deliberately into two adversarial halves
built by the same person — tune the evasion, then try to break it.

The beacon uses:
- A malleable HTTP C2 profile (`glasshouse`) that mimics CDN/WordPress
  static asset requests — not just a bare `/beacon` endpoint
- Configurable jitter (`--jitter`) to avoid a fixed-interval check-in
  pattern
- A redirector in front of the actual C2 server, so the target never talks
  to it directly

The detector uses only what's visible to anyone with a span port or a
redirector log — no payload content, no profile prior knowledge:
- Groups raw packets into actual check-in **events** (not naive
  packet-to-packet or connection-to-connection deltas — see
  [`docs/04-defense-detection.md`](docs/04-defense-detection.md) for the two
  wrong approaches that got ruled out first)
- Computes the **coefficient of variation (CV)** of inter-check-in
  intervals — low CV (tight, regular spacing) flags automated beaconing even
  through jitter; high CV is consistent with organic/human traffic

## Key result

A beacon configured with `--seconds 45 --jitter 20` (a theoretical spread of
25-65s) was still caught: 49 real check-ins produced a mean interval of
55.29s with only 5.27s of standard deviation — **CV = 0.095**, far under the
0.4 detection threshold. Jitter narrowed the *practical* spread far less
than it widened the *theoretical* one.

Full numbers, methodology, and the control-traffic comparison are in
[`docs/05-results.md`](docs/05-results.md).

## Repo layout

```
operation-glasshouse/
├── docs/
│   ├── 01-overview.md
│   ├── 02-architecture.md
│   ├── 03-offense-c2-setup.md       — C2, redirector, beacon, malleable profile
│   ├── 04-defense-detection.md      — detection methodology + the mistakes made getting there
│   └── 05-results.md                — beacon vs. control traffic comparison
├── c2/                              — Sliver server Dockerfile
├── redirector/                      — nginx config, multi-homed container
├── target/                          — beacon container
├── detection/
│   ├── analyze_beacon.py            — pcap -> check-in clustering -> CV verdict
│   └── captures/                    — raw pcaps used in the analysis
└── docker-compose.yml
```

## Running it

```bash
docker compose up -d --build
docker exec -it sliver-c2 sliver-server
```

Inside the Sliver console:

```
generate beacon --http redirector:8888 --os linux --arch arm64 \
  --skip-symbols --seconds 45 --jitter 20 --c2profile glasshouse --save /root/
```

Copy the generated binary into the `target` build context as `beacon`,
rebuild, and bring the stack up again. Capture and analyze:

```bash
docker exec redirector tcpdump -i eth0 -w /captures/traffic.pcap port 8888
# let it run for several check-in cycles, then Ctrl+C
python3 detection/analyze_beacon.py detection/captures/traffic.pcap
```

## Status

- [x] Offensive chain (C2 + redirector + evasive, profiled, jittered beacon)
- [x] Detection engine (timing-based CV analysis)
- [x] Beacon vs. control traffic comparison
- [ ] Grafana dashboard (C2 sessions + detection alerts side by side)
- [ ] Detection sensitivity sweep across jitter configurations

## Disclaimer

Built and run entirely inside an isolated, internal-only Docker network on
hardware I own, for the purpose of studying detection engineering. Not
intended for, and not tested against, any system I don't control.
