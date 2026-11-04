#!/usr/bin/python3
"""Map ports once; retain every detected NIC."""
import json
from pathlib import Path
path=Path('/etc/nullos/ports.json')
if not path.exists():
    ports=sorted((p for p in Path('/sys/class/net').iterdir() if (p/'device').exists()),key=lambda p:str((p/'device').resolve()))
    if not len(ports) >= 1:
        raise SystemExit('NullOS needs at least one NIC; configure /etc/nullos/ports.json manually')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({f'ge-0/0/{i}':p.name for i,p in enumerate(ports)},indent=2)+'\n')
