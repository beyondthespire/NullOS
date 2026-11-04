# Release gates

## Completed in the source-development environment

- Python tests: command validation, contextual completion, config modes, VLAN
  references/ranges, access/trunk membership, management subnet checks, password
  redaction, optimistic concurrency, history, confirmation timeout/confirmation,
  unconfirmed reboot restoration, failed-apply restoration, backend command plan.
- Python compile and shell syntax checks.

## Required before an installable alpha release

1. Build ISO on Debian 13; record package versions and SHA-256 checksum.
2. Boot both SeaBIOS and OVMF (Secure Boot disabled), install to blank disk, detach
   ISO, and reboot. Check no live-session-only accounts/policies grant remote access.
3. Verify four NICs map to the intended MAC addresses. Test inventories of 4, 48 and 128 ports. Test NIC removal/reordering without silently changing port assignments.
4. Verify SSH is off before configuration, root SSH is rejected, configured users
   reach the CLI, passwords do not echo, and unsupported remote commands fail.
5. Verify same-VLAN forwarding through NullOS, cross-VLAN isolation, trunk tags,
   disabled ports, management VLAN isolation, and populated MAC table with captures.
6. Verify unconfigured ports do not forward and no default bridge-local untagged
   management path is exposed. Verify STP convergence and loop behavior in isolation.
7. Test successful and failing commits on real OVS, IP, SSH, hostname and account
   operations. Inject failures midway; inspect recovery logs and actual live state.
8. Lose SSH after `commit confirmed 1`; verify watchdog restores access. Repeat
   with process failure, a reboot, and a second session. Validate clock-change behavior.
9. Verify saved configuration, addresses, gateway, users and SSH state after reboot.
10. Measure TCP/UDP throughput, loss, latency and CPU in both directions using
    separate endpoints. Start at 1 Gb/s, then 10 Gb/s; include small packets,
    jumbo/non-jumbo MTUs, simultaneous flows and all configured ports. Report measured
    aggregate forwarding rather than inferring performance from NIC link speeds.

Known alpha risks: backend restoration is best-effort across multiple subsystems;
wall-clock-based confirmation deadlines are sensitive to clock changes; persistent
writes do not yet fsync the containing directory; installer behavior and complete
power-loss recovery are unqualified. No production support claim is made.
