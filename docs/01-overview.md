# Operation GLASSHOUSE

## Introduction

Operation GLASSHOUSE is a self-contained security research project that explores both sides of a cyber attack: offense and defense. It invoices building a working Command and Control (C2) infraestructure with evasion techniques, and then building a detection system designed to catch that very same traffic. The project's core idea is simple but powerful: attack your own system, then measure how well you can defend against it.

## Motivation

Most introductory cybersecurity projects stop at running a pre-build tool and calling it a day. This project goes further by building both the offensive and defensive components from the ground up, in order to understand *why* techniques work, not just *that* they work.

The motivation behind this project is to:

- Understand how C2 infraestructure operates internally, beyond just using off-the-shelf tools
- Learn how security analysts actually detect evasive network traffic in practice
- Apply existing DevOps, clou and system knowledge to an offensive/defensive security context
- Build a strong, well-documented portfolio project that demonstrates practical, hands-on security engineering skills

## Objectives

- Deploy a functional C2 infraestructure (Silver) with evasion techniques, including beacon jitter and malleable C2 profile
- Build a redirector to separate the real C2 server from the exposed endpoint
- Design and implement a detection engine based on statistical analysis of network traffic (beaconing detection)
- Quantitatively measure the impact of each evasion techniques on detection time and detection rate
- Visualize both the attack and the detection process through a live operations dashboard
- Document the entire process as a purple team case study, from setup to measurable results

## Scope & Disclaimer

> This project operates exclusively within an isolated lab environment.

All components of Operation GLASSHOUSE run inside Docker containers on a single Raspberry PI 5, fully isolated from any production network. No third-party systems, networks, or data are targeted, accessed, or affected at any point in this project.

This project folllows the principles of responsible security reseach and is intended solely for educational and professional purposes.

## Tech Stack

- **Hardware**: Raspberry PI 5
- **Containerization**: Docker / Docker Compose
- **C2 Framework**: Silver
- **Detection Engine**: Python
- **Dashboard**: Grafana
- **Version Control**: Git / Github

## Project Structure

```
operation-glasshouse/
├── docs/           # Project documentation
├── c2/             # C2 server configuration
├── redirector/     # Redirector setup
├── detection/      # Detection engine source code
├── dashboard/      # Visualization dashboard
└── docker-compose.yml
```
