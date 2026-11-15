from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess,CalledProcessError
import os
import tempfile
import unittest
from unittest.mock import patch
import launch

class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.python=self.root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        self.python.parent.mkdir(parents=True)
        self.python.touch()
    def tearDown(self):
        self.tmp.cleanup()

    def test_installed_environment_is_reused_without_install(self):
        with patch.object(launch,'ROOT',self.root),patch('launch.subprocess.run',return_value=CompletedProcess([],0)) as run,patch('launch.subprocess.call',return_value=0) as call,patch('launch.venv.create') as create:
            self.assertEqual(launch.main(),0)
        create.assert_not_called()
        self.assertEqual(run.call_count,1)
        call.assert_called_once_with([str(self.python),str(self.root/'main.py')],cwd=self.root)

    def test_interrupted_environment_without_pip_is_repaired(self):
        results=[CompletedProcess([],1),CompletedProcess([],1),CompletedProcess([],0),CompletedProcess([],0)]
        with patch.object(launch,'ROOT',self.root),patch('launch.subprocess.run',side_effect=results) as run,patch('launch.subprocess.call',return_value=0),redirect_stdout(StringIO()):
            self.assertEqual(launch.main(),0)
        commands=[c.args[0] for c in run.call_args_list]
        self.assertIn([str(self.python),'-m','ensurepip','--upgrade'],commands)
        self.assertTrue(any('install' in command for command in commands))

    def test_failed_install_does_not_attempt_to_launch(self):
        results=[CompletedProcess([],1),CompletedProcess([],0),CalledProcessError(1,['pip'])]
        with patch.object(launch,'ROOT',self.root),patch('launch.subprocess.run',side_effect=results),patch('launch.subprocess.call') as call,redirect_stdout(StringIO()):
            self.assertEqual(launch.main(),1)
        call.assert_not_called()

if __name__=='__main__':
    unittest.main()
