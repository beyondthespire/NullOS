#!/bin/bash
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run this on a disposable Debian 13 build VM as root'; exit 1; }
. /etc/os-release
[[ ${ID:-} == debian && ${VERSION_ID:-} == 13 ]] || { echo 'Debian 13 required for this recipe'; exit 1; }
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
work_dir="$source_dir/build"
[[ ! -e "$work_dir" ]] || { echo 'build/ already exists. Use a fresh source extraction to rebuild.'; exit 1; }
apt-get update
apt-get install -y live-build debootstrap squashfs-tools xorriso isolinux syslinux-common grub-pc-bin grub-efi-amd64-bin mtools dosfstools
mkdir "$work_dir"
cd "$work_dir"
lb config --mode debian --distribution trixie --architectures amd64 \
  --binary-images iso-hybrid --debian-installer live --archive-areas main \
  --bootappend-live 'boot=live components username=nullos hostname=NullOS'
mkdir -p config/package-lists config/includes.chroot/opt/nullos config/hooks/live
cat > config/package-lists/nullos.list.chroot <<'EOF'
linux-image-amd64
live-boot
live-config
live-config-systemd
systemd-sysv
python3
openvswitch-switch
iproute2
iputils-ping
openssh-server
openssl
sudo
vim-tiny
less
ethtool
pciutils
EOF
cp -a "$source_dir/src" "$source_dir/packaging" config/includes.chroot/opt/nullos/
cat > config/hooks/live/0100-nullos.hook.chroot <<'EOF'
#!/bin/sh
set -eu
bash /opt/nullos/packaging/install-files.sh
# No stock DHCP clients or interface managers should compete for switch ports.
# The live session starts at a local console; SSH stays off until configured.
mkdir -p /etc/network
printf 'auto lo\niface lo inet loopback\n' > /etc/network/interfaces
systemctl disable networking.service systemd-networkd.service NetworkManager.service 2>/dev/null || true
# Live console bootstrap only; never grant this to SSH users.
printf 'nullos ALL=(root) NOPASSWD: /usr/local/sbin/nullos-root ""\n' >> /etc/sudoers.d/nullos
rm -rf /opt/nullos
EOF
chmod +x config/hooks/live/0100-nullos.hook.chroot
lb build
install -m 644 live-image-amd64.hybrid.iso "$source_dir/NullOS-0.1.0-alpha.2-amd64.iso"
cd "$source_dir"
sha256sum NullOS-0.1.0-alpha.2-amd64.iso > NullOS-0.1.0-alpha.2-amd64.iso.sha256
