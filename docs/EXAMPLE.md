# First configuration

Use the Proxmox console for initial setup. Commands below work in the demo too,
except demo networking/account/SSH operations are deliberately no-ops.

```text
configure
set system host-name NullOS
set vlans MANAGEMENT vlan-id 100
set vlans CLIENTS vlan-id 200
set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members MANAGEMENT
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members CLIENTS
set interfaces ge-0/0/1 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/1 unit 0 family ethernet-switching vlan members CLIENTS
set interfaces ge-0/0/2 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/2 unit 0 family ethernet-switching vlan members CLIENTS
set interfaces ge-0/0/3 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/3 unit 0 family ethernet-switching vlan members MANAGEMENT
set vlans MANAGEMENT l3-interface irb.0
set interfaces irb unit 0 family inet address 192.0.2.2/24
set routing-options static route 0.0.0.0/0 next-hop 192.0.2.1
set system login user admin class super-user
set system login user admin authentication plain-text-password
set system services ssh
show | compare
commit check
commit confirmed 5
```

Enter a matching password of at least 12 characters when prompted. Substitute
an actual management subnet/address/gateway before testing networking. The
example 192.0.2.0/24 network is documentation space.

Verify access, then issue `commit` in configuration mode before five minutes
elapse. This confirms the change. Do not stop the rollback watchdog.

```text
commit
exit
show interfaces terse
show vlans
show ethernet-switching table
show configuration
show system commit
```

To restore a previous commit, use `configure`, `rollback 1`, `show | compare`,
then `commit`. `rollback 0` discards candidate edits but does not change the live
configuration. `exit discard` leaves configuration mode without committing.
