from test_nullos import n,PORTS,BASE
from unittest.mock import patch
import unittest

class LabTest(unittest.TestCase):
    def test_isolated_commands_and_cleanup(self):
        calls=[]
        def fake(*args,**kw):
            calls.append(args)
            return '[]' if '-j' in args else ''
        with patch.object(n,'run',side_effect=fake),patch.object(n.os,'geteuid',return_value=0):
            lab=n.LabBackend(PORTS);lab.start()
            lab.apply(n.Config(PORTS).validate(BASE),{})
            lab.address('ge-0/0/0','192.0.2.10/24')
            self.assertEqual(len(lab.owned),5)
            self.assertTrue(any('pvid' in c and 'untagged' in c for c in calls))
            self.assertTrue(all(c[:3]==('ip','netns','exec') or c[:3] in [('ip','netns','add'),('ip','netns','del')] for c in calls))
            lab.stop();self.assertEqual(lab.owned,[])
    def test_nonroot_rejected(self):
        with patch.object(n.os,'geteuid',return_value=1000),patch.object(n,'run') as r:
            with self.assertRaises(ValueError):n.LabBackend(PORTS).start()
            r.assert_not_called()
    def test_start_failure_cleans_created_namespaces(self):
        with patch.object(n.os,'geteuid',return_value=0),patch.object(n,'run',side_effect=['',ValueError('failed'), '']):
            lab=n.LabBackend(PORTS)
            with self.assertRaises(ValueError):lab.start()
            self.assertEqual(lab.owned,[])
