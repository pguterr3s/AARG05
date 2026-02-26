# AARG05

A network automation lab project that combines **Containerlab** network topology definitions, **Ansible** configuration management, and a **telemetry stack** (gNMIc + Prometheus) to provision, configure, and monitor a virtual network lab — including a digital twin of the production environment.

---

## Table of Contents

- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
  - [1. Deploy the Network Topology](#1-deploy-the-network-topology)
  - [2. Run Ansible Playbooks](#2-run-ansible-playbooks)
  - [3. Start the Telemetry Stack](#3-start-the-telemetry-stack)
- [Digital Twin](#digital-twin)
- [Telemetry](#telemetry)

---

## Overview

AARG05 is a lab environment built on top of [Containerlab](https://containerlab.dev/) for spinning up virtual network topologies, [Ansible](https://www.ansible.com/) for automated device configuration, and a streaming telemetry pipeline using [gNMIc](https://gnmic.openconfig.net/) and [Prometheus](https://prometheus.io/).

The project includes two environments:
- **Production lab** – the primary network topology.
- **Digital Twin** – an identical virtual replica of the production lab used for testing and validation.

---

## Repository Structure

```
AARG05/
├── ansible/
│   └── inventory/
│       ├── production.yml   # Inventory for the production lab nodes
│       └── twin.yml         # Inventory for the digital twin lab nodes
├── telemetry/
│   ├── docker-compose.yml   # Compose file to run the telemetry stack
│   ├── gnmic.yml            # gNMIc configuration (subscriptions, targets)
│   └── prometheus.yml       # Prometheus scrape configuration
├── topology/
│   ├── aar-lab.yml          # Containerlab topology for the production lab
│   └── aar-lab-twin.yml     # Containerlab topology for the digital twin
├── requirements.txt         # Python / Ansible dependencies
└── README.md
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| [Containerlab](https://containerlab.dev/install/) | Deploy virtual network topologies |
| [Ansible](https://docs.ansible.com/ansible/latest/installation_guide/) | Automated device configuration |
| [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/) | Run the telemetry stack |
| Python 3.8+ | Required by Ansible |

Install Python dependencies:

```bash
pip install -r requirements.txt
```

---

## Getting Started

### 1. Deploy the Network Topology

Deploy the **production** lab:

```bash
sudo containerlab deploy -t topology/aar-lab.yml
```

To tear it down:

```bash
sudo containerlab destroy -t topology/aar-lab.yml
```

### 2. Run Ansible Playbooks

Target the **production** inventory:

```bash
ansible-playbook -i ansible/inventory/production.yml <playbook>.yml
```

Target the **digital twin** inventory:

```bash
ansible-playbook -i ansible/inventory/twin.yml <playbook>.yml
```

### 3. Start the Telemetry Stack

```bash
cd telemetry
docker compose up -d
```

This starts gNMIc (streaming telemetry collector) and Prometheus (metrics storage). Bring it down with:

```bash
docker compose down
```

---

## Digital Twin

The digital twin is a virtual replica of the production lab:

- **Topology**: `topology/aar-lab-twin.yml`
- **Ansible inventory**: `ansible/inventory/twin.yml`

Deploy it the same way as the production lab:

```bash
sudo containerlab deploy -t topology/aar-lab-twin.yml
```

Use the twin to safely test configuration changes before applying them to production.

---

## Telemetry

The telemetry pipeline collects streaming data from network devices using **gNMI** and stores metrics in **Prometheus**.

| Component | Config file | Default port |
|-----------|-------------|-------------|
| gNMIc | `telemetry/gnmic.yml` | — |
| Prometheus | `telemetry/prometheus.yml` | `9090` |

Access Prometheus at [http://localhost:9090](http://localhost:9090) after starting the stack.
