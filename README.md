# NullOS

An experimental configuration simulator and Linux software switch with a
hierarchical CLI, context-aware Tab completion, VLAN configuration, commits,
confirmed commits and rollback.

Start with [INSTALL.md](INSTALL.md). See [CMDS.md](CMDS.md) for commands.

```bash
git clone https://github.com/beyondthespire/NullOS.git
cd NullOS
python3 src/nullos.py --demo --ports 48
```

Simulation needs no physical ports or root privileges. Choose any positive port
count; there is no fixed product cap. Available memory and CPU determine practical
scale. Inventory persists per state directory. Simulation validates configuration
but does not forward packets or simulate connected hosts.

The Linux backend can manage existing virtual or physical interfaces using Open
vSwitch. It does not automatically create Linux virtual links. For Windows, use
WSL; for other systems use a Linux VM. Native Windows execution is not supported.

This is alpha software. CLI tests pass; full forwarding, ISO installation and
throughput qualification remain outstanding. The ISO build recipe is optional;
git clone is the recommended installation method.
