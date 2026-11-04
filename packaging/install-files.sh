#!/bin/bash
set -euo pipefail
# Install files only. Does not install packages or take over networking.
[[ $EUID == 0 ]] || { echo 'Run as root'; exit 1; }
source_dir=$(cd -- "$(dirname -- "$0")/.." && pwd)
install -d -m 755 /usr/local/lib/nullos /etc/nullos /var/lib/nullos
chmod 700 /var/lib/nullos
install -m 644 "$source_dir/src/nullos.py" /usr/local/lib/nullos/nullos.py
install -m 755 "$source_dir/packaging/map-ports.py" /usr/local/lib/nullos/map-ports.py
cat > /usr/local/sbin/nullos-root <<'EOF'
#!/bin/sh
exec /usr/bin/python3 -I /usr/local/lib/nullos/nullos.py "$@"
EOF
cat > /usr/local/bin/nullos-login <<'EOF'
#!/bin/sh
# SSH remote commands and SCP/SFTP are deliberately unsupported.
[ "$#" -eq 0 ] || { echo 'Interactive NullOS sessions only'; exit 1; }
exec /usr/bin/sudo -n /usr/local/sbin/nullos-root
EOF
chmod 755 /usr/local/sbin/nullos-root /usr/local/bin/nullos-login
getent group nullos-admin >/dev/null || groupadd --system nullos-admin
cat > /etc/sudoers.d/nullos <<'EOF'
%nullos-admin ALL=(root) NOPASSWD: /usr/local/sbin/nullos-root ""
EOF
chmod 440 /etc/sudoers.d/nullos
visudo -cf /etc/sudoers.d/nullos
if ! grep -qxF /usr/local/bin/nullos-login /etc/shells; then echo /usr/local/bin/nullos-login >> /etc/shells; fi
cat > /etc/systemd/system/nullos-boot.service <<'EOF'
[Unit]
Description=NullOS port mapping and configuration restore
Requires=openvswitch-switch.service
After=openvswitch-switch.service local-fs.target
Before=nullos-watch.service
[Service]
Type=oneshot
ExecStartPre=/usr/bin/python3 -I /usr/local/lib/nullos/map-ports.py
ExecStart=/usr/local/sbin/nullos-root --boot
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/nullos-watch.service <<'EOF'
[Unit]
Description=NullOS confirmed-commit rollback watchdog
Requires=nullos-boot.service
After=nullos-boot.service
[Service]
ExecStart=/usr/local/sbin/nullos-root --watch
Restart=always
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF
install -d /etc/ssh/sshd_config.d
cat > /etc/ssh/sshd_config.d/00-nullos.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication yes
KbdInteractiveAuthentication no
AllowGroups nullos-admin
AllowTcpForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTunnel no
EOF
# Prevent the base distro from independently enabling SSH at boot.
systemctl disable ssh.service ssh.socket 2>/dev/null || true
systemctl enable nullos-boot.service nullos-watch.service
printf '%s\n' 'Files installed. Networking has not been activated. Follow docs/PROXMOX.md.'
