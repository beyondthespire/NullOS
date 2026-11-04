# Temporary networking in demo mode

This experimental Linux backend creates a private network namespace with a
VLAN-aware Linux bridge, virtual Ethernet ports, and one endpoint namespace per
port. Physical NICs, the host default route and host firewall are untouched.
There is no Internet uplink: 8.8.8.8 is not reachable from this isolated lab.
System accounts, hostname and SSH configuration remain simulated.

Install iproute2 and iputils-ping on Debian/Ubuntu (iproute and iputils on Fedora).
Start a small lab first; each configured port consumes kernel resources.
Use a dedicated state directory and do not run another CLI/watchdog against it
while the temporary backend is active.

```bash
git pull --ff-only
sudo python3 src/nullos.py --demo --ports 4 --state-dir /var/tmp/nullos-lab-demo
```

Inside NullOS:

```text
request lab start
configure
set vlans TEST vlan-id 100
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members TEST
set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members TEST
commit
exit
request lab host ge-0/0/0 address 192.0.2.10/24
request lab host ge-0/0/1 address 192.0.2.11/24
request lab ping ge-0/0/0 192.0.2.11
```

The last command sends four real probes from the first virtual host to the second.
Change a port VLAN or disable it and commit to test isolation. Endpoint addresses
are temporary, not part of saved switch configuration. Endpoints use untagged
Ethernet; tagged endpoint configuration is not yet exposed.

Ordinary `ping <IPv4>` runs from the isolated switch namespace while the backend
is active. Configure an irb.0 address and matching VLAN binding first to give the
switch an IP source. `request lab ping` instead runs from the selected endpoint.

```text
request lab stop
```

Stop removes the session's namespaces and links. Normal CLI exit also cleans up;
SIGKILL, a crash or a terminated terminal may leave namespaces behind. The start
message prints the unique nullos- namespace prefix; inspect `sudo ip netns list`
and delete only that session's names with `sudo ip netns delete <exact-name>`.
Saved configuration is retained. Confirmed commits are rejected while the lab is
active because the separate demo watchdog does not own its temporary backend.
Status/MAC display commands retain their demo output in this version.

Validation: command-plan, privilege rejection and failed-start cleanup tests pass.
Real kernel forwarding tests could not run in the development environment because
network namespace privileges are unavailable. Validate the example in a Linux VM.
