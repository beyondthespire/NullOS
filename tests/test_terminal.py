"""Exercise actual GNU readline Tab behavior through a pseudo-terminal."""
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import tempfile
import time
import unittest

class TerminalTest(unittest.TestCase):
    def test_tab_completes_and_enters_configuration(self):
        master,slave=pty.openpty()
        with tempfile.TemporaryDirectory() as temp:
            proc=subprocess.Popen([sys.executable,str(Path(__file__).parents[1]/'src/nullos.py'),'--demo','--state-dir',temp],stdin=slave,stdout=slave,stderr=slave,env={**os.environ,'TERM':'xterm'})
            os.close(slave)
            def expect(fragment):
                data=b''; deadline=time.monotonic()+5
                while fragment not in data and time.monotonic()<deadline:
                    if select.select([master],[],[],0.1)[0]:data+=os.read(master,4096)
                self.assertIn(fragment,data)
            try:
                expect(b'@NullOS> ')
                os.write(master,b'conf\t\n');expect(b'@NullOS# ')
                os.write(master,b'set system host-n\tTerminalTest\n');expect(b'@NullOS# ')
                os.write(master,b'commit\n');expect(b'@TerminalTest# ')
                os.write(master,b'exit\n');expect(b'@TerminalTest> ')
                os.write(master,b'exit\n');proc.wait(timeout=5)
                self.assertEqual(proc.returncode,0)
            finally:
                if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
                os.close(master)
