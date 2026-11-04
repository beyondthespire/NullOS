# Install NullOS

## Recommended: clone and run the configuration simulator

Use Linux with Python 3.11 or newer, or a Linux VM. Windows users can use WSL.
On Debian/Ubuntu install prerequisites:

```bash
sudo apt-get update
sudo apt-get install -y git python3 openssl
git clone https://github.com/beyondthespire/NullOS.git
cd NullOS
python3 src/nullos.py --demo --ports 48
```

No root privileges or physical interfaces are needed to run the simulator.
Tab completes supported commands and interface names. Start with `configure`.
See CMDS.md for the full command guide.

## Choose the number of ports

```bash
python3 src/nullos.py --demo --ports 128
```

Ports are named ge-0/0/0 through ge-0/0/127 in this example. Any positive count is
accepted; practical scale depends on machine resources. The default initial
inventory is 48 ports. Inventory persists in ~/.nullos-demo/ports.json, so later
launches can omit --ports. Shrinking an inventory is rejected if removed ports
are referenced by active configuration or rollback history.

Separate labs can have separate configuration and inventory:

```bash
python3 src/nullos.py --demo --state-dir "$HOME/nullos-labs/lab-a" --ports 96
```

For timed confirmed-commit rollback, keep a second terminal running the watchdog
with the same state directory:

```bash
python3 src/nullos.py --demo --state-dir "$HOME/nullos-labs/lab-a" --watch
```

Simulated ports have no physical links and do not carry traffic. Ping is unavailable
in simulation. Use a Linux networking lab when testing actual packet forwarding.

## Linux forwarding installation

Use a dedicated Debian 13 guest and its console. Clone the repository there, then:

```bash
sudo apt-get update
sudo apt-get install -y python3 openssl openvswitch-switch iproute2 iputils-ping openssh-server sudo
sudo bash packaging/install-files.sh
```

Follow docs/PROXMOX.md to map existing interfaces, remove competing network
configuration and activate the services. There is no fixed port-count limit.
The installer does not create virtual Linux links. Only mapped interfaces are
managed. Do not install the forwarding backend on the hypervisor host.

## Update

Exit CLI sessions before updating:

```bash
cd NullOS
git pull --ff-only
python3 src/nullos.py --demo
```

Configuration is stored outside the checkout. Back up the state directory before
upgrading. For an installed forwarding backend, rerun packaging/install-files.sh
from the console and restart nullos-watch after updating; configuration restore
or restarting nullos-boot can interrupt traffic.

## Developer checks

```bash
python3 -m unittest discover -s tests -v
```

Additional installation methods are planned. The current ISO recipe is unverified;
use the clone workflow above first.

## Temporary networking inside demo mode

See [docs/TEMPORARY-LAB.md](docs/TEMPORARY-LAB.md) for setup, real endpoint ping,
VLAN tests, privileges, and cleanup. It is isolated and has no Internet uplink.
