import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

class InventoryTest(unittest.TestCase):
    def test_large_inventory_persists(self):
        with tempfile.TemporaryDirectory() as d:
            command=[sys.executable,str(Path(__file__).parents[1]/'src/nullos.py'),'--demo','--state-dir',d]
            a=subprocess.run(command+['--ports','128'],input='exit\n',text=True,capture_output=True)
            self.assertEqual(a.returncode,0,a.stderr)
            self.assertEqual(len(json.loads((Path(d)/'ports.json').read_text())),128)
            b=subprocess.run(command,input='exit\n',text=True,capture_output=True)
            self.assertEqual(b.returncode,0,b.stderr)
            self.assertEqual(len(json.loads((Path(d)/'ports.json').read_text())),128)
            bad=subprocess.run(command+['--ports','0'],input='',text=True,capture_output=True)
            self.assertNotEqual(bad.returncode,0)
