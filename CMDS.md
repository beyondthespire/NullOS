# NullOS command reference

NullOS implements the command subset documented below.

Alpha.2 adds `show configuration | display set` (with Tab completion) and
`ping <host> [count <1-100>] [source <IPv4>]` in operational mode. Ping uses
the real IPv4 network, defaults to five probes, streams replies, and supports
Ctrl+C. Install `iputils-ping`. Demo mode explicitly does not send probes.
Hostname resolution requires working Linux DNS configuration.


This guide describes the implemented NullOS 0.1 command subset, not all NullOS
commands. Syntax is NullOS-style, but output and supported options differ.
Your successful test is a useful first validation; it does not yet establish
complete virtual switch compatibility or qualify 10 Gb/s forwarding.

## Conventions and completion

`>` is operational mode; `#` is configuration mode. Do not type the prompt.
Angle brackets in this document denote values you replace, not literal input.
Use Tab to complete commands, mapped ports, and existing VLAN names. Press Tab
again for ambiguous choices. Enter `?` at the end of a partial command and press
Enter for help. Full command names are required; abbreviations are not implemented.
Quote descriptions containing spaces. Semicolons and bracket-list syntax are not
supported. Changes take effect only after commit.

## Operational commands

| Command | What it does |
|---|---|
| `configure` | Copies active configuration into this session's candidate and enters configuration mode. |
| `show configuration` | Displays active configuration as `set` statements; password hashes are redacted. |
| `show interfaces terse` | Lists logical port, Linux NIC, and observed link state. Output is simplified; does not show NullOS logical-interface/address columns. |
| `show vlans` | Lists configured VLAN names, IDs, and management IRB binding. |
| `show ethernet-switching table` | Displays the actual OVS forwarding database; output uses OVS port numbering. Demo mode has no live table. |
| `show system commit` | Shows current revision, retained rollback count, and whether confirmation is pending. Not a timestamped NullOS commit log. |
| `show version` | Displays the NullOS version. |
| `exit` | Ends the CLI session. |

## Configuration commands

| Command | What it does |
|---|---|
| `set <path> <value>` | Adds a candidate statement; replaces scalar values at the same path. |
| `delete <path>` | Removes the matching candidate subtree. Commit is still required. |
| `edit <path>` | Moves to a supported configuration hierarchy; subsequent set/delete commands are relative to it. |
| `top` | Returns to the configuration root. |
| `up` | Removes one token from the current edit path (simplified behavior). |
| `show` | Displays candidate set statements within the current edit context. |
| `show \| compare` | Shows a unified diff between active and candidate configuration. Type a normal pipe character. |
| `commit check` | Validates syntax and references without applying; does not test backend availability. |
| `commit` | Applies and saves candidate configuration, or confirms a pending confirmed commit. |
| `commit confirmed` | Applies with a default 10-minute confirmation deadline. |
| `commit confirmed <minutes>` | Applies with a deadline of 1–60 minutes; watchdog restores previous configuration if not confirmed. |
| `rollback 0` | Reloads active configuration into candidate, discarding candidate edits. |
| `rollback <n>` | Loads retained previous configuration n into candidate; 1 is most recent. Up to 10 are retained. Commit to apply. |
| `exit` | At a nested edit context returns to root; at root leaves configuration mode if there are no uncommitted changes. |
| `exit discard` | Leaves configuration mode and discards candidate edits. |

A stale session cannot overwrite another session's commit: use `exit discard`
and `configure` to reload. Confirm a pending commit before making further changes.
The independent `nullos-watch` service must run for automatic timed rollback.
A reboot with an unconfirmed commit restores the previous configuration.

## System and accounts

Run these at `[edit]` (use `top` first).

| Statement | Meaning |
|---|---|
| `set system host-name <name>` | Sets hostname and CLI prompt after commit. |
| `set system login user <name> class super-user` | Creates/configures a full administrator; other classes are unsupported. |
| `set system login user <name> authentication plain-text-password` | Prompts twice without echo, requires 12+ characters, and stores a SHA-512 crypt hash. |
| `set system login user <name> authentication encrypted-password '<hash>'` | Accepts a SHA-512 crypt hash in the supported format. Prefer interactive password entry. |
| `set system services ssh` | Starts SSH after commit; requires at least one complete configured administrator. |
| `delete system services ssh` | Stops SSH after commit. |
| `delete system login user <name>` | Removes the managed account configuration; backend locks the account and disables its shell, preserving its home directory. |

Both class and password must exist before commit. Root, nullos, daemon and nobody
are reserved names. Existing unrelated Linux accounts cannot be adopted.
All supported users are administrators; SSH forwarding, SCP/SFTP and remote
command execution are disabled. Removing a user does not terminate existing sessions.
Do not delete your final administrator while SSH remains configured.

## VLANs and switch ports

Logical ports are `ge-0/0/0` through the last configured port (no fixed port-count cap).
These are aliases defined in `/etc/nullos/ports.json`; they are not speed settings.

| Statement | Meaning |
|---|---|
| `set vlans <name> vlan-id <id>` | Creates a named VLAN, IDs 1–4094. IDs must be unique. |
| `set interfaces <port> unit 0 family ethernet-switching interface-mode access` | Selects untagged access-port behavior. Exactly one explicit VLAN member is required. |
| `set interfaces <port> unit 0 family ethernet-switching interface-mode trunk` | Selects tagged trunk behavior. Explicit allowed VLAN membership is required. |
| `set interfaces <port> unit 0 family ethernet-switching vlan members <name>` | Adds a VLAN member. Repeat for multiple trunk VLANs. Referenced VLANs must exist. |
| `set interfaces <port> description "<text>"` | Saves a description in configuration; currently not applied as a Linux interface alias. |
| `set interfaces <port> disable` | Administratively disables the port after commit. |
| `delete interfaces <port> disable` | Removes the administrative disable; valid switching configuration is still required. |
| `delete interfaces <port> unit 0 family ethernet-switching vlan members <name>` | Removes that VLAN membership. |
| `delete interfaces <port>` | Removes port configuration; unconfigured ports do not forward. |
| `delete vlans <name>` | Removes a VLAN; remove port references and any IRB dependency first. |

No implicit default VLAN, `members all`, native VLAN or VLAN-range syntax exists.
STP is enabled in OVS as a fixed default; this is not a NullOS RSTP implementation.

## Management addressing

| Statement | Meaning |
|---|---|
| `set vlans <name> l3-interface irb.0` | Binds the single supported management IRB to this VLAN. |
| `set interfaces irb unit 0 family inet address <IPv4/prefix>` | Adds a static management address. Repeat for multiple addresses. |
| `set routing-options static route 0.0.0.0/0 next-hop <IPv4>` | Sets the management default gateway, which must lie within a configured management subnet. |
| `delete interfaces irb unit 0 family inet address <IPv4/prefix>` | Removes one address. |
| `delete routing-options static route 0.0.0.0/0` | Removes the default-gateway statement. |

Only one VLAN may bind irb.0. The binding and at least one address must be present
together. This is management addressing, not inter-VLAN routing. DHCP and IPv6
configuration are not implemented.

## Example: two access ports and a trunk

```text
configure
set vlans CLIENTS vlan-id 200
set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members CLIENTS
set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members CLIENTS
set interfaces ge-0/0/2 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members CLIENTS
commit check
show | compare
commit confirmed 5
commit
exit
show interfaces terse
show vlans
show ethernet-switching table
```

In a real test, verify forwarding and management access between `commit confirmed`
and `commit`. See `docs/EXAMPLE.md` for the full four-port management/SSH example.

## Relevant NullOS coverage still missing

These are backlog items, **not accepted commands**. Implementing a parser entry
alone would not provide their networking behavior.

| Area | Relevant commands/features to implement and test |
|---|---|
| Troubleshooting | `traceroute`, `show route`, `show arp`, interface counters/detail, counter clearing. |
| Config usability | hierarchical output, `run`, abbreviations, instant `?`, `load merge/replace`, save/export, rename/copy, activate/deactivate. |
| VLAN switching | Native VLANs, VLAN lists/ranges, `members all`, VLAN-filtered forwarding tables, MAC-table clearing. |
| Link operation | MTU, LACP/aggregated Ethernet, LLDP neighbors, configurable RSTP, storm control, loop protection. |
| Management | DHCP management, DNS, NTP, timezone, syslog, SNMP, reboot/shutdown commands. |
| Authentication | SSH keys, read-only roles, RADIUS, authentication order and local fallback. |
| Optional Layer 3 | Multiple IRBs, IPv6, static routes beyond the management default, ACLs and routing protocols. |
| Hardware-only | virtual switch chassis/ASIC/optics/Virtual Chassis operations cannot be reproduced faithfully on ordinary VirtIO NICs. |

This release does not contain every relevant external vendors command. Prioritize the
troubleshooting and configuration-usability groups next, then qualify each
additional switching feature against real forwarding tests. Additional features require implementation and testing.

## Simulated inventory

Launch with `python3 src/nullos.py --demo --ports 48` to create 48 configuration-only
ports. Use any positive count. Inventory persists per state directory. See INSTALL.md.

## Temporary network backend (demo only, Linux root required)

| Command | Purpose |
|---|---|
| `request lab start` | Creates isolated software switching and one endpoint per port. |
| `request lab host <port> address <IPv4/prefix>` | Assigns an untagged endpoint address. |
| `request lab ping <port> <IPv4>` | Sends four probes from that endpoint. |
| `request lab stop` | Removes the temporary network; retains saved configuration. |

See [the temporary lab walkthrough](docs/TEMPORARY-LAB.md). No Internet uplink
is created. Ordinary ping uses the isolated switch when the lab is running.
