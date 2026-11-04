# Proxmox lab and build instructions

This is an alpha source release. **No compiled or boot-tested ISO is included.**
The quickest privileged test is installing the files into a fresh Debian 13 VM.
The ISO recipe is the next packaging path and needs build/boot verification.

## VM layout

Start with 2 vCPU (host CPU type), 2 GiB RAM, an 8 GiB disk and four VirtIO NICs.
Use the Proxmox console throughout bootstrap. Disable Secure Boot for the initial
ISO test. Do not pass a production management interface through to this guest.

Create four isolated Proxmox bridges without physical uplinks or host IPs, and
connect one NullOS NIC to each. Connect test endpoint VMs to those bridges.
Two NullOS ports on the same Proxmox bridge can create a switching loop; avoid
that topology. Traffic between endpoints on one host bridge may bypass NullOS.

For the trunk port, use a VLAN-aware Proxmox bridge that permits VLANs 100 and
200 and do not set a Proxmox access VLAN tag on the NullOS NIC. Access ports in
the example carry untagged guest traffic. Check the Proxmox firewall allows the
test traffic. VirtIO may report 10 Gb/s even when your test target is 1 Gb/s;
that displayed value is not a throughput cap or measured result.

## Install into a disposable Debian 13 guest

Copy/extract this source directory into the guest before taking over interfaces.
Do not run this on the Proxmox host. At the guest console as root:

```bash
apt-get update
apt-get install -y python3 openvswitch-switch iproute2 iputils-ping openssh-server openssl sudo vim-tiny
bash packaging/install-files.sh
ip -br link
```

Create `/etc/nullos/ports.json` explicitly with vim, matching the actual Linux
NIC names and MAC addresses from Proxmox Hardware. Example only:

```json
{
  "ge-0/0/0": "ens18",
  "ge-0/0/1": "ens19",
  "ge-0/0/2": "ens20",
  "ge-0/0/3": "ens21"
}
```

If absent, first boot maps NICs in sorted PCI-device-path order and saves the
mapping. Use an explicit mapping when port order matters. Names are logical
aliases; Linux interfaces are not renamed. NIC removal causes startup to fail
rather than silently remapping ports.

Remove the four mapped NICs from Debian's `/etc/network/interfaces` and any
networkd/NetworkManager configuration. The only ifupdown entry needed in a
dedicated guest is:

```text
auto lo
iface lo inet loopback
```

From the **guest console**, stop any DHCP client/interface manager controlling
these four ports. Reboot after removing their configuration. NullOS owns these
ports; competing DHCP or IP configuration is unsupported. Initially there is no
network access and SSH is off. Login through the console, then:

```bash
systemctl status nullos-boot nullos-watch --no-pager
sudo /usr/local/sbin/nullos-root
```

Use EXAMPLE.md to configure the switch. The installed Debian bootstrap account
remains a normal Linux account for console maintenance. Configured NullOS users
get the CLI when logging in via SSH; SSH is restricted to the `nullos-admin` group.
All supported NullOS accounts have full administrative configuration privileges.
Verify `net.ipv4.ip_forward=0` and `net.ipv6.conf.all.forwarding=0` in this dedicated
guest; routing is outside this release's scope.

## Build an installer ISO

Use a separate disposable **Debian 13 amd64 build VM**, not the switch VM or
Proxmox host. Allocate approximately 4 vCPU, 4 GiB RAM, and 20 GiB free disk for
the build (planning estimate). It needs Internet access and root mount/chroot
privileges. From the source directory:

```bash
sudo bash build-iso.sh
```

Expected output, if the unverified recipe succeeds:

```text
NullOS-0.1.0-alpha.1-amd64.iso
NullOS-0.1.0-alpha.1-amd64.iso.sha256
```

Upload the ISO to Proxmox ISO storage, attach it to a disposable VM, and boot.
The Debian live-build recipe requests a live image plus Debian's live installer.
The live console user is `nullos`; launch the CLI with
`sudo /usr/local/sbin/nullos-root`. Live mode is for testing; configuration is not
persistent across reboot unless installed or explicitly given persistence.
No default remotely usable administrative password is supplied.

Installation is via Debian's installer, not a custom NullOS installer UI. Create
a separate bootstrap account (not named `nullos`) during installation. After
installation, verify/remove installer-added DHCP configuration on switch ports
before enabling the NullOS network configuration. Then use the installed-guest
bootstrap instructions above. Boot modes, installer behavior, account setup,
network ownership, and service ordering must all pass ACCEPTANCE.md before
calling the ISO ready for use.
