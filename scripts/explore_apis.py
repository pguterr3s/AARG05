#explore_apis.py
#!/usr/bin/env python3
"""
Part 1 – Explore device APIs directly.
Demonstrates RESTCONF on Arista cEOS and gNMI on Nokia SR Linux.
Also exercises Mikrotik proprietary REST API.
"""

import json
import subprocess
import sys
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

MY_R1_HOST = "clab-aar-lab-r1"
MY_R3_HOST = "clab-aar-lab-r3"
MY_R4_HOST = "clab-aar-lab-r4"

MY_ARISTA_USER   = "admin"
MY_ARISTA_PASS   = "admin"
MY_RESTCONF_PORT = 5900

MY_SRL_TLS_CA = "~/topology/clab-aar-lab/r3/config/tls/clab-profile.pem"


# ──────────────────────────────────────────────
# RESTCONF – ARISTA cEOS
# ──────────────────────────────────────────────

def restconfGetInterfaces(myHost):
    """GET all interfaces from Arista via RESTCONF."""
    myUrl = (
        f"https://{myHost}:{MY_RESTCONF_PORT}"
        f"/restconf/data/openconfig-interfaces:interfaces"
    )
    print(f"\n[RESTCONF] GET {myUrl}")
    myResp = requests.get(
        myUrl,
        auth=(MY_ARISTA_USER, MY_ARISTA_PASS),
        verify=False,
        timeout=10,
    )
    print(f"  Status: {myResp.status_code}")
    try:
        myData = myResp.json()
        print(json.dumps(myData, indent=2)[:1000])
    except Exception:
        print(myResp.text[:500])
    return myResp


def restconfGetInterface(myHost, myIntfName):
    """GET a specific interface configuration from Arista via RESTCONF."""
    myUrl = (
        f"https://{myHost}:{MY_RESTCONF_PORT}"
        f"/restconf/data/openconfig-interfaces:interfaces/interface={myIntfName}"
    )
    print(f"\n[RESTCONF] GET interface {myIntfName}")
    myResp = requests.get(
        myUrl,
        auth=(MY_ARISTA_USER, MY_ARISTA_PASS),
        verify=False,
        timeout=10,
    )
    print(f"  Status: {myResp.status_code}")
    print(myResp.text[:800])
    return myResp


def restconfPatchDescription(myHost, myIntfName, myDescription):
    """PATCH interface description on Arista via RESTCONF."""
    myUrl = (
        f"https://{myHost}:{MY_RESTCONF_PORT}"
        f"/restconf/data/openconfig-interfaces:interfaces/interface={myIntfName}"
    )
    myBody = {
        "openconfig-interfaces:config": {
            "description": myDescription
        }
    }
    myHeaders = {"Content-Type": "application/yang-data+json"}
    print(f"\n[RESTCONF] PATCH description on {myIntfName} → '{myDescription}'")
    myResp = requests.patch(
        myUrl,
        auth=(MY_ARISTA_USER, MY_ARISTA_PASS),
        verify=False,
        headers=myHeaders,
        json=myBody,
        timeout=10,
    )
    print(f"  Status: {myResp.status_code}")
    print(myResp.text[:400])
    return myResp


def restconfCheckMethods(myHost):
    """Check supported HTTP methods via OPTIONS request."""
    myUrl = (
        f"https://{myHost}:{MY_RESTCONF_PORT}"
        f"/restconf/data/openconfig-interfaces:interfaces"
    )
    print(f"\n[RESTCONF] OPTIONS {myUrl}")
    myResp = requests.options(
        myUrl,
        auth=(MY_ARISTA_USER, MY_ARISTA_PASS),
        verify=False,
        timeout=10,
    )
    myAllow = myResp.headers.get("Allow", "N/A")
    print(f"  Allow: {myAllow}")
    print("  PUT replaces the full resource; PATCH merges/updates fields only.")
    return myAllow


# ──────────────────────────────────────────────
# gNMI – NOKIA SR LINUX  (calls gnmic CLI)
# ──────────────────────────────────────────────

def gnmicRun(myArgs):
    """Run a gnmic command and return output."""
    myCmd = [
        "gnmic", "-a", MY_R3_HOST, "--skip-verify",
        "-u", "admin", "-p", "admin",
        "-e", "json_ietf",
    ] + myArgs
    print(f"\n[gNMI] {' '.join(myCmd)}")
    myResult = subprocess.run(myCmd, capture_output=True, text=True)
    myOut = myResult.stdout + myResult.stderr
    print(myOut[:1000])
    return myOut


def gnmiGetSystemInfo():
    """Get SR Linux system information via gNMI."""
    return gnmicRun(["get", "--path", "/system/information"])


def gnmiGetInterfaces():
    """Get SR Linux interfaces operational state via gNMI."""
    return gnmicRun(["get", "--path", "/interface", "--type", "state"])


def gnmiSetLocation(myLocation):
    """Set SR Linux system location via gNMI Set."""
    return gnmicRun([
        "set",
        "--update-path", "/system/information/location",
        "--update-value", myLocation,
    ])


def gnmiSubscribeOnce():
    """Subscribe to interface state changes in ONCE mode via gNMI."""
    return gnmicRun([
        "subscribe",
        "--path", "/interface/oper-state",
        "--mode", "once",
    ])


# ──────────────────────────────────────────────
# MIKROTIK – Proprietary REST API
# ──────────────────────────────────────────────

def mikrotikGetAddresses():
    """GET IP addresses from Mikrotik via its proprietary REST API."""
    myUrl = f"http://{MY_R4_HOST}/rest/ip/address"
    print(f"\n[Mikrotik REST] GET {myUrl}")
    try:
        myResp = requests.get(
            myUrl,
            auth=("admin", "admin"),
            timeout=10,
        )
        print(f"  Status: {myResp.status_code}")
        print(json.dumps(myResp.json(), indent=2)[:800])
    except Exception as myErr:
        print(f"  ERROR: {myErr}")


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    """Run all API exploration tasks."""
    print("\n" + "="*60)
    print("  Part 1 – Direct API Exploration")
    print("="*60)

    # ── RESTCONF ──────────────────────────────
    print("\n### RESTCONF on Arista cEOS (R1) ###")
    restconfGetInterfaces(MY_R1_HOST)
    restconfGetInterface(MY_R1_HOST, "Ethernet1")
    restconfCheckMethods(MY_R1_HOST)
    restconfPatchDescription(MY_R1_HOST, "Ethernet1", "Configured via RESTCONF")
    restconfGetInterface(MY_R1_HOST, "Ethernet1")   # Verify change

    # ── gNMI ─────────────────────────────────
    print("\n### gNMI on Nokia SR Linux (R3) ###")
    gnmiGetSystemInfo()
    gnmiGetInterfaces()
    gnmiSetLocation("ISEL, Lisbon")
    gnmiGetSystemInfo()   # Verify change
    gnmiSubscribeOnce()

    # ── Mikrotik REST ─────────────────────────
    print("\n### Mikrotik Proprietary REST API (R4) ###")
    mikrotikGetAddresses()
    print("\n  Note: Mikrotik uses a proprietary REST API (port 80),")
    print("  not RESTCONF or gNMI – standard APIs are not supported.")

    print("\n" + "="*60)
    print("  RESTCONF vs gNMI Comparison (RFC 2119 vocabulary)")
    print("="*60)
    print("""
  Transport:
    RESTCONF MUST use HTTP/HTTPS (RFC 8040).
    gNMI MUST use gRPC over HTTP/2 (per gNMI spec).

  Encoding:
    RESTCONF MUST encode data as JSON or XML (YANG-modelled).
    gNMI SHOULD use JSON_IETF or Protobuf encoding.

  Subscriptions:
    RESTCONF does NOT support streaming subscriptions natively.
    gNMI MUST support STREAM subscriptions (SAMPLE and ON_CHANGE modes).

  Vendor support:
    Arista cEOS and Nokia SR Linux both support gNMI.
    Mikrotik CHR does NOT support RESTCONF or gNMI.
  """)


if __name__ == "__main__":
    main()
