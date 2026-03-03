#collect_info.py
#!/usr/bin/env python3
"""
Part 1 – Collect network information via Netmiko (SSH).
Gathers software versions, LLDP neighbours, interfaces and running configs.
Uses multithreading for faster execution.
"""

import csv
import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tabulate import tabulate # tabulate serve para 
from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
DATA_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "data")
CSV_FILE   = os.path.join(DATA_DIR, "devices.csv")

os.makedirs(OUTPUT_DIR, exist_ok=True)

myLock = threading.Lock() 
myResults = {}


def readDevices(myFilePath):
    """Read device list from CSV and return list of dicts."""
    myDevices = []
    with open(myFilePath, newline="") as myF:
        myReader = csv.DictReader(myF)
        for myRow in myReader:
            myDevices.append(myRow)
    return myDevices


def getTimestamp():
    """Return current datetime string formatted for filenames."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def saveToFile(myFilename, myContent):
    """Write content to output file."""
    myPath = os.path.join(OUTPUT_DIR, myFilename)
    with open(myPath, "w") as myF:
        myF.write(myContent)
    print(f"  [saved] {myPath}")


# ──────────────────────────────────────────────
# VERSION COLLECTION
# ──────────────────────────────────────────────

def getAristaVersion(myConn):
    """Return software version string from Arista EOS device."""
    myOutput = myConn.send_command("show version | include Software")
    for myLine in myOutput.splitlines():
        if "EOS" in myLine or "version" in myLine.lower():
            return myLine.strip()
    return myOutput.strip().splitlines()[0] if myOutput.strip() else "unknown"


#def getNokiaVersion(myConn):
#    """Return software version string from Nokia SR Linux device."""
#    myOutput = myConn.send_command("info system information | grep version")
#    return myOutput.strip() if myOutput.strip() else "unknown"

def getNokiaVersion(myConn):
    """Return software version string from Nokia SR Linux device."""
    myOutput = myConn.send_command("info from state system information version")
    for myLine in myOutput.splitlines():
        if "version" in myLine.lower():
            # Limpar espaços e devolve só a versão 
            return myLine.replace("version", "").strip()
    return "unknown"


def getMikrotikVersion(myConn):
    """Return software version string from Mikrotik RouterOS device."""
    myOutput = myConn.send_command("/system resource print")
    for myLine in myOutput.splitlines():
        if "version" in myLine.lower():
            return myLine.strip()
    return "unknown"


# ──────────────────────────────────────────────
# LLDP NEIGHBOURS
# ──────────────────────────────────────────────

def getAristaNeighbours(myConn):
    """Return list of (interface, neighbour_hostname, neighbour_interface) from Arista."""
    myOutput = myConn.send_command("show lldp neighbors")
    myRows = []
    for myLine in myOutput.splitlines():
        myParts = myLine.split()
        if len(myParts) >= 4 and myParts[0].startswith("Et"):
            myRows.append((myParts[0], myParts[1], myParts[-1]))
    return myRows


def getNokiaNeighbours(myConn):
    """Return list of (interface, neighbour_hostname, neighbour_interface) from Nokia SR Linux."""
    myOutput = myConn.send_command("show system lldp neighbor")
    myRows = []
    for myLine in myOutput.splitlines():
        myParts = myLine.split()
        if len(myParts) >= 3 and myParts[0].startswith("ethernet"):
            myRows.append((myParts[0], myParts[1], myParts[2]))
    return myRows


def getMikrotikNeighbours(myConn):
    """Return list of (interface, neighbour_hostname, neighbour_interface) from Mikrotik."""
    myOutput = myConn.send_command("/ip neighbor print")
    myRows = []
    for myLine in myOutput.splitlines():
        if "interface=" in myLine or myLine.strip().startswith("#"):
            continue
        myParts = myLine.split()
        if len(myParts) >= 3:
            myRows.append((myParts[1] if len(myParts) > 1 else "?",
                           myParts[2] if len(myParts) > 2 else "?",
                           myParts[3] if len(myParts) > 3 else "?"))
    return myRows


# ──────────────────────────────────────────────
# INTERFACES
# ──────────────────────────────────────────────

def getAristaInterfaces(myConn):
    """Return list of (interface, status, ip, mask) from Arista."""
    myOutput = myConn.send_command("show ip interface brief")
    myRows = []
    for myLine in myOutput.splitlines():
        myParts = myLine.split()
        if len(myParts) >= 4 and myParts[0].startswith("Et") or myParts[0].startswith("Lo"):
            myIpMask = myParts[3].split("/") if "/" in myParts[3] else [myParts[3], ""]
            myRows.append((myParts[0], myParts[2], myIpMask[0],
                           myIpMask[1] if len(myIpMask) > 1 else ""))
    return myRows


def getNokiaInterfaces(myConn):
    """Return list of (interface, status, ip, mask) from Nokia SR Linux."""
    myOutput = myConn.send_command("show interface brief")
    myRows = []
    for myLine in myOutput.splitlines():
        myParts = myLine.split()
        if len(myParts) >= 2 and (myParts[0].startswith("ethernet") or myParts[0].startswith("lo")):
            myStatus = myParts[1] if len(myParts) > 1 else "unknown"
            myIp = myParts[2] if len(myParts) > 2 else ""
            myIpMask = myIp.split("/") if "/" in myIp else [myIp, ""]
            myRows.append((myParts[0], myStatus, myIpMask[0],
                           myIpMask[1] if len(myIpMask) > 1 else ""))
    return myRows


def getMikrotikInterfaces(myConn):
    """Return list of (interface, status, ip, mask) from Mikrotik."""
    myOutput = myConn.send_command("/ip address print")
    myRows = []
    for myLine in myOutput.splitlines():
        if myLine.strip().startswith("#") or not myLine.strip():
            continue
        myParts = myLine.split()
        if len(myParts) >= 3:
            myIpMask = myParts[1].split("/") if "/" in myParts[1] else [myParts[1], ""]
            myRows.append((myParts[-1], "up", myIpMask[0],
                           myIpMask[1] if len(myIpMask) > 1 else ""))
    return myRows


# ──────────────────────────────────────────────
# RUNNING CONFIG
# ──────────────────────────────────────────────

def getRunningConfig(myConn, myDeviceType):
    """Return running configuration string from device."""
    if myDeviceType == "arista_eos":
        return myConn.send_command("show running-config")
    elif myDeviceType == "nokia_srl":
        return myConn.send_command("info flat")
    elif myDeviceType == "mikrotik_routeros":
        return myConn.send_command("/export")
    return ""


# ──────────────────────────────────────────────
# PER-DEVICE WORKER
# ──────────────────────────────────────────────

def collectDevice(myDevice):
    """Connect to a single device and collect all required information."""
    myHost = myDevice["host"]
    myTs   = getTimestamp()
    print(f"[{myHost}] Connecting...")

    myConnParams = {
        "device_type": myDevice["type"],
        "host":        myHost,
        "port":        int(myDevice["port"]),
        "username":    myDevice["user"],
        "password":    myDevice["password"],
        "secret":      myDevice.get("enable_password", ""),
        "timeout":     120,          # <-- Subimos para 120 segundos
        "conn_timeout": 60,          # <-- Subimos para 60 segundos
        "global_delay_factor": 8,    # <-- Subimos para 8 
        #"session_log": f"{myHost}_debug.log", # Debug num file
    }

    # Se for o Nokia SR Linux, dizemos ao Netmiko qual é o prompt exato!
    if myDevice["type"] == "nokia_srl":
        # regex para apanhar "r3#" ou "R3#" no fim da linha
        myConnParams["session_log"] = f"{myHost}_debug.log"

    try:
        myConn = ConnectHandler(**myConnParams)
        myType = myDevice["type"]

        # ── Software version ──────────────────
        if myType == "arista_eos":
            myVersion = getAristaVersion(myConn)
        elif myType == "nokia_srl":
            myVersion = getNokiaVersion(myConn)
        else:
            myVersion = getMikrotikVersion(myConn)

        # ── LLDP neighbours ───────────────────
        if myType == "arista_eos":
            myNeighbours = getAristaNeighbours(myConn)
        elif myType == "nokia_srl":
            myNeighbours = getNokiaNeighbours(myConn)
        else:
            myNeighbours = getMikrotikNeighbours(myConn)

        myNeighbourCsv = "Interface,NeighbourHostname,NeighbourInterface\n"
        for myRow in myNeighbours:
            myNeighbourCsv += ",".join(myRow) + "\n"
        saveToFile(f"neighbours_{myHost}_{myTs}.txt", myNeighbourCsv)

        # ── Interfaces ───────────────────────
        if myType == "arista_eos":
            myInterfaces = getAristaInterfaces(myConn)
        elif myType == "nokia_srl":
            myInterfaces = getNokiaInterfaces(myConn)
        else:
            myInterfaces = getMikrotikInterfaces(myConn)

        myInterfaceCsv = "Interface,Status,Ip,Mask\n"
        for myRow in myInterfaces:
            myInterfaceCsv += ",".join(myRow) + "\n"
        saveToFile(f"interfaces_{myHost}_{myTs}.txt", myInterfaceCsv)

        # ── Running config ───────────────────
        myConfig = getRunningConfig(myConn, myType)
        saveToFile(f"conf_{myHost}_{myTs}.txt", myConfig)

        myConn.disconnect()
        print(f"[{myHost}] Done.")
        return myHost, myVersion, None

    except (NetmikoTimeoutException, NetmikoAuthenticationException, Exception) as myErr:
        print(f"[{myHost}] SKIPPED – {myErr}")
        return myHost, None, str(myErr)


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────

def main():
    """Main entry point – collect info from all devices concurrently."""
    myStartTime = time.time()
    myDevices   = readDevices(CSV_FILE)
    myTs        = getTimestamp()

    print(f"\n{'='*60}")
    print(f"  NetOps Part 1 – Information Collection")
    print(f"  Devices: {len(myDevices)}  |  Started: {myTs}")
    print(f"{'='*60}\n")

    myVersionRows = []

    # Run all devices in parallel (bonus: multithreaded)
    with ThreadPoolExecutor(max_workers=4) as myExecutor:
        myFutures = {myExecutor.submit(collectDevice, myDev): myDev for myDev in myDevices}
        for myFuture in as_completed(myFutures):
            myHost, myVersion, myError = myFuture.result()
            if myVersion:
                myVersionRows.append((myHost, myVersion))
            else:
                myVersionRows.append((myHost, f"ERROR: {myError}"))

    # Save consolidated versions file
    myVersionCsv = "Host,SwVersion\n"
    for myRow in myVersionRows:
        myVersionCsv += f"{myRow[0]},{myRow[1]}\n"
    saveToFile(f"versions_{myTs}.txt", myVersionCsv)

    myElapsed = time.time() - myStartTime
    print(f"\n{'='*60}")
    print(f"  Collection complete in {myElapsed:.1f}s")
    print(tabulate(myVersionRows, headers=["Host", "SW Version"], tablefmt="rounded_outline"))
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
