import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('nullos',Path(__file__).parents[1]/'src/nullos.py')
n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
PORTS={f'ge-0/0/{i}':f'ens{18+i}' for i in range(4)}
BASE=[['vlans','TEST','vlan-id','100'],['interfaces','ge-0/0/0','unit','0','family','ethernet-switching','vlan','members','TEST']]
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.s=n.Store(self.tmp.name,PORTS,True);self.c=self.s.cfg
    def test_display_set_completion(self):
        self.assertEqual(self.c.complete('show configuration | display '),['set'])
        self.assertIn('|',self.c.complete('show configuration '))
        cli=n.CLI(self.s)
        with patch('builtins.print') as output:
            cli.execute('show configuration | display set')
            output.assert_called_once_with('')
    def test_ping(self):
        cli=n.CLI(self.s);self.s.backend.demo=False
        with patch.object(n.subprocess,'run') as run:
            cli.execute('ping 192.0.2.1 count 3 source 192.0.2.2')
            self.assertEqual(run.call_args.args[0],['ping','-4','-n','-c','3','-W','2','-I','192.0.2.2','--','192.0.2.1'])
        for cmd in ['ping','ping -f','ping localhost count 0','ping localhost count 1 count 2','ping localhost bad value']:
            with self.assertRaises(ValueError):cli.execute(cmd)
    def test_access(self):
        c=self.c.validate(BASE);self.assertEqual(c['ports']['ge-0/0/0']['mode'],'access')
    def test_unknown_commands_rejected(self):
        for line in [['system','services','telnet'],['interfaces','ge-0/0/8','disable']]:
            with self.assertRaises(ValueError):self.c.validate([line])
    def test_bad_vlans(self):
        for vid in ['0','4095','x']:
            with self.assertRaises(ValueError):self.c.validate([['vlans','X','vlan-id',vid]])
        with self.assertRaises(ValueError):self.c.validate(BASE+[['vlans','Y','vlan-id','100']])
    def test_undefined_vlan(self):
        with self.assertRaises(ValueError):self.c.validate(BASE[1:])
    def test_access_rejects_multiple_members(self):
        lines=BASE+[['vlans','Y','vlan-id','200'],BASE[1][:-1]+['Y']]
        with self.assertRaises(ValueError):self.c.validate(lines)
        c=self.c.validate(lines+[BASE[1][:6]+['interface-mode','trunk']])
        self.assertEqual(len(c['ports']['ge-0/0/0']['members']),2)
    def test_set_replaces_scalar(self):
        self.assertEqual(self.c.set(BASE,['vlans','TEST','vlan-id','200'])[0],BASE[1])
        self.assertEqual(len(self.c.set(BASE,BASE[1])),2)
    def test_completion(self):
        self.assertIn('configure',self.c.complete('conf'))
        self.assertEqual(self.c.complete('show interfaces '),['terse'])
        self.assertIn('ge-0/0/0',self.c.complete('set interfaces ge-',True,lines=BASE))
        self.assertIn('TEST',self.c.complete('set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members ',True,lines=BASE))
        self.assertIn('host-name',self.c.complete('set h',True,['system']))
        self.assertIn('vlan-id',self.c.complete('set ',True,['vlans','TEST'],BASE))
    def test_management(self):
        lines=BASE+[['vlans','TEST','l3-interface','irb.0'],['interfaces','irb','unit','0','family','inet','address','192.0.2.2/24']]
        self.c.validate(lines)
        with self.assertRaises(ValueError):self.c.validate(lines+[['routing-options','static','route','0.0.0.0/0','next-hop','198.51.100.1']])
    def test_ssh_requires_user(self):
        with self.assertRaises(ValueError):self.c.validate([['system','services','ssh']])
    def test_commit_and_stale_session(self):
        self.s.commit(BASE,0)
        with self.assertRaises(ValueError):self.s.commit(BASE,0)
        self.assertEqual(self.s.load()['active'],BASE)
        self.assertEqual(self.s.load()['history'],[[]])
    def test_confirmed_timeout(self):
        self.s.commit(BASE,0,1)
        s=self.s.load();s['pending']['deadline']=0;self.s.save(s)
        self.s.recover();self.assertEqual(self.s.load()['active'],[])
    def test_confirm_and_boot(self):
        self.s.commit(BASE,0,1);self.s.commit(BASE,1)
        self.s.recover(boot=True);self.assertEqual(self.s.load()['active'],BASE)
    def test_unconfirmed_boot_restores(self):
        self.s.commit(BASE,0,1);self.s.recover(boot=True)
        self.assertEqual(self.s.load()['active'],[])
    def test_failed_apply_preserves_state(self):
        with patch.object(self.s.backend,'apply',side_effect=[ValueError('bad'),None]):
            with self.assertRaises(ValueError):self.s.commit(BASE,0)
        self.assertEqual(self.s.load()['revision'],0)
        self.assertEqual(self.s.load()['active'],[])
    def test_failed_restore_keeps_recovery_intent(self):
        with patch.object(self.s.backend,'apply',side_effect=ValueError('backend unavailable')):
            with self.assertRaises(n.RestoreFailed):self.s.commit(BASE,0)
        self.assertIsNotNone(self.s.load()['pending'])
    def test_password_redaction(self):
        self.assertNotIn('$secret',''.join(n.display([['system','login','user','admin','authentication','encrypted-password','$secret']])))
    def test_backend_vlan_plan(self):
        b=n.Backend(PORTS);calls=[]
        with patch.object(n,'run',side_effect=lambda *a,**kw:calls.append(a) or ''):
            b.apply(self.c.validate(BASE),self.c.validate([]))
        ovs=calls[0]
        self.assertIn('tag=100',ovs);self.assertIn('vlan_mode=access',ovs)
        self.assertNotIn('ens19',ovs[ovs.index('add-port'):ovs.index('add-port')+4])
    def test_cli_workflow(self):
        cli=n.CLI(self.s)
        for command in ['configure','set vlans TEST vlan-id 100','edit interfaces ge-0/0/0','set unit 0 family ethernet-switching vlan members TEST','top','commit check','commit','exit']:
            cli.execute(command)
        self.assertFalse(cli.editing);self.assertEqual(self.s.load()['revision'],1)
if __name__=='__main__':unittest.main()
