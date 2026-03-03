#configure_network.py
#!/usr/bin/env python3
"""
Part 1 – Configure network devices using NAPALM and Jinja2 templates.
Applies IP addresses, loopbacks and OSPF configuration to all routers.
After configuration, validates connectivity using NAPALM ping.
"""

import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from jinja2 import Environment, FileSystemLoader
from napalm import get_network_driver
from tabulate import tabulate

DATA_DIR      = os.path.join(os.path.dirname(__file__), "..", "..", "data")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
CSV_FILE      = os.path.join(DATA_DIR, "devices.csv")

# TLS certificate path for Nokia SR Linux (adjust if needed)
MY_SRL_TLS_CA = os.path.expanduser(
    "~/topology/clab-aar-lab/r3/config/tls/clab-profile.pem"
)

# ──────────────────────────────────────────────
# DEVICE TOPOLOGY DATA
# Network: 172.16.X.0/24 – third byte = concat of router numbers
# Each router loopback: 172.16.0.R/32
# ──────────────────────────────────────────────

MY_ROUTER_DATA = {
    "clab-aar-lab-r1": {
        "router_id":  "172.16.0.1",
        "loopback":   "172.16.0.1/32",
        "ospf_area0": True,
        "interfaces": {
            "Ethernet1": {"ip": "172.16.12.1", "mask": "24", "ospf_area": "0.0.0.0"},
            "Ethernet2": {"ip": "192.168.1.254", "mask": "24", "ospf_area": "0.0.0.1"},
            "Ethernet3": {"ip": "172.16.13.1", "mask": "24", "ospf_area": "0.0.0.0"},
            "Ethernet4": {"ip": "172.16.14.1", "mask": "24", "ospf_area": "0.0.0.0"},
        },
        "ospf_process": 1,
        "vendor": "arista",
    },
    "clab-aar-lab-r2": {
        "router_id":  "172.16.0.2",
        "loopback":   "172.16.0.2/32",
        "interfaces": {
            "Ethernet1": {"ip": "172.16.12.2", "mask": "24", "ospf_area": "0.0.0.0"},
            "Ethernet2": {"ip": "192.168.2.254", "mask": "24", "ospf_area": "0.0.0.2"},
            "Ethernet3": {"ip": "172.16.23.2", "mask": "24", "ospf_area": "0.0.0.0"},
            "Ethernet4": {"ip": "172.16.24.2", "mask": "24", "ospf_area": "0.0.0.0"},
        },
        "ospf_process": 1,
        "vendor": "arista",
    },
    "clab-aar-lab-r3": {
        "router_id":  "172.16.0.3",
        "loopback":   "172.16.0.3/32",
        "interfaces": {
            "ethernet-1/1": {"ip": "172.16.13.3", "mask": "24", "ospf_area": "0.0.0.0"},
            "ethernet-1/2": {"ip": "172.16.23.3", "mask": "24", "ospf_area": "0.0.0.0"},
            "ethernet-1/3": {"ip": "192.168.3.254", "mask": "24", "ospf_area": "0.0.0.3"},
        },
        "ospf_process": "main",
        "vendor": "srl",
    },
    "clab-aar-lab-r4": {
        "router_id":  "172.16.0.4",
        "loopback":   "172.16.0.4/32",
        "interfaces": {
            "ether2": {"ip": "192.168.4.254", "mask": "24", "ospf_area": "0.0.0.4"},
            "ether3": {"ip": "172.16.14.4", "mask": "24", "ospf_area": "0.0.0.0"},
            "ether4": {"ip": "172.16.24.4", "mask": "24", "ospf_area": "0.0.0.0"},
        },
        "ospf_process": 1,
        "vendor": "mikrotik",
    },
}

MY_LOOPBACKS = {host: data["router_id"] for host, data in MY_ROUTER_DATA.items()}


def readDevices(myFilePath):
    """Read device credentials from CSV."""
    myDevices = []
    with open(myFilePath, newline="") as myF:
        myReader = csv.DictReader(myF)
        for myRow in myReader:
            myDevices.append(myRow)
    return myDevices


def renderTemplate(myVendor, myTemplateName, myVars):
    """Render a Jinja2 template for a given vendor."""
    myEnv = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
    myTpl = myEnv.get_template(f"{myVendor}_{myTemplateName}.j2")
    return myTpl.render(**myVars)


def getNapalmDriver(myDevice, myRouterData):
    """Create and open a NAPALM driver for the given device."""
    myType = myDevice["type"]
    myHost = myDevice["host"]

    if myType == "arista_eos":
        myDriver = get_network_driver("eos")
        myOptional = {
            "transport": "https",
            "port": 443,
        }
        myConn = myDriver(myHost, myDevice["user"], myDevice["password"],
                          timeout=60, optional_args=myOptional)

    elif myType == "nokia_srl":
        myDriver = get_network_driver("srl")
        myOptional = {
            "gnmi_port":    57400,
            "jsonrpc_port": 443,
            "target_name":  myHost,
            "tls_ca":       MY_SRL_TLS_CA,
            "skip_verify":  True,
            "encoding":     "JSON_IETF",
        }
        myConn = myDriver(myHost, myDevice["user"], myDevice["password"],
                          timeout=60, optional_args=myOptional)

    elif myType == "mikrotik_routeros":
        myDriver = get_network_driver("ros")
        myOptional = {"port": 22}
        myConn = myDriver(myHost, myDevice["user"], myDevice["password"],
                          timeout=60, optional_args=myOptional)
    else:
        raise ValueError(f"Unknown device type: {myType}")

    return myConn


def configureDevice(myDevice):
    """Render and apply configuration to a single device via NAPALM."""
    myHost      = myDevice["host"]
    myRouterD   = MY_ROUTER_DATA.get(myHost)
    if not myRouterD:
        print(f"[{myHost}] No router data defined, skipping.")
        return myHost, False

    myVendor = myRouterD["vendor"]
    print(f"[{myHost}] Configuring ({myVendor})...")

    try:
        myConn = getNapalmDriver(myDevice, myRouterD)
        myConn.open()

        # Render configuration template
        myConfig = renderTemplate(myVendor, "full_config", {
            "host":       myHost,
            "router":     myRouterD,
            "router_id":  myRouterD["router_id"],
            "loopback":   myRouterD["loopback"],
            "interfaces": myRouterD["interfaces"],
            "process":    myRouterD["ospf_process"],
        })

        myConn.load_merge_candidate(config=myConfig)
        myDiff = myConn.compare_config()
        if myDiff:
            print(f"[{myHost}] Diff:\n{myDiff}")
            myConn.commit_config()
            print(f"[{myHost}] Configuration committed.")
        else:
            print(f"[{myHost}] No changes needed.")
            myConn.discard_config()

        myConn.close()
        return myHost, True

    except Exception as myErr:
        print(f"[{myHost}] ERROR during configuration: {myErr}")
        return myHost, False


def pingConnectivity(myDevice):
    """Use NAPALM ping to verify connectivity between routers."""
    myHost    = myDevice["host"]
    myRouterD = MY_ROUTER_DATA.get(myHost)
    if not myRouterD:
        return myHost, {}

    print(f"[{myHost}] Running ping tests...")
    myPingResults = {}

    try:
        myConn = getNapalmDriver(myDevice, myRouterD)
        myConn.open()

        for myTarget, myTargetIp in MY_LOOPBACKS.items():
            if myTarget == myHost:
                continue
            try:
                myResult = myConn.ping(myTargetIp, count=3)
                mySuccess = myResult.get("success", {})
                myPingResults[myTarget] = (
                    "✓" if mySuccess.get("packet_loss", 3) == 0 else "✗"
                )
            except Exception:
                myPingResults[myTarget] = "✗"

        myConn.close()

    except Exception as myErr:
        print(f"[{myHost}] Ping ERROR: {myErr}")

    return myHost, myPingResults


def printPingTable(myAllPingResults):
    """Print a table of ping results similar to ContainerLab output."""
    myHosts = sorted(MY_LOOPBACKS.keys())
    myHeaders = ["Source \\ Target"] + [h.split("-")[-1] for h in myHosts]
    myRows = []

    for mySrc in myHosts:
        myRow = [mySrc.split("-")[-1]]
        for myDst in myHosts:
            if mySrc == myDst:
                myRow.append("—")
            else:
                myRow.append(myAllPingResults.get(mySrc, {}).get(myDst, "?"))
        myRows.append(myRow)

    print("\n" + tabulate(myRows, headers=myHeaders, tablefmt="rounded_outline"))


def main():
    """Main entry point – configure all devices then verify connectivity."""
    myStartTime = time.time()
    myDevices   = readDevices(CSV_FILE)

    print(f"\n{'='*60}")
    print(f"  NetOps Part 1 – Network Configuration via NAPALM")
    print(f"{'='*60}\n")

    # Configure all devices (parallel)
    with ThreadPoolExecutor(max_workers=4) as myEx:
        myFutures = [myEx.submit(configureDevice, myDev) for myDev in myDevices]
        myConfigResults = [f.result() for f in as_completed(myFutures)]

    print("\nWaiting 30s for OSPF to converge...\n")
    time.sleep(30)

    # Ping connectivity tests (parallel)
    myAllPings = {}
    with ThreadPoolExecutor(max_workers=4) as myEx:
        myFutures = [myEx.submit(pingConnectivity, myDev) for myDev in myDevices]
        for myF in as_completed(myFutures):
            myHost, myPings = myF.result()
            myAllPings[myHost] = myPings

    printPingTable(myAllPings)

    myElapsed = time.time() - myStartTime
    print(f"\n  Total time: {myElapsed:.1f}s\n")


if __name__ == "__main__":
    main()
