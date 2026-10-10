from __future__ import annotations
import json
import pathlib
import sys
import unittest

MEMORY=pathlib.Path(__file__).resolve().parents[1]
ROOT=MEMORY.parent
if str(MEMORY) not in sys.path:sys.path.insert(0,str(MEMORY))
import service_manager as manager

class ServiceManagerUnitTests(unittest.TestCase):
    def test_formal_paths_and_interpreter(self):
        self.assertIsNone(manager.config_issue())
        self.assertEqual(manager.PYTHON,(ROOT/".venv/Scripts/python.exe").resolve())
        self.assertEqual(manager.RUN_SCRIPT,(MEMORY/"run.py").resolve())
    def test_state_fields_and_identity(self):
        state=manager.load_state();self.assertIsInstance(state,dict)
        for key in ["pid","process_create_time","python_path","script_path","working_directory","service_url","database_path","started_at"]:self.assertIn(key,state)
        valid,reason,info=manager.validate_state(state);self.assertTrue(valid,reason);self.assertIsNotNone(info)
    def test_status_and_health(self):
        code,status=manager.status_command();self.assertEqual(code,0);self.assertEqual(status.get("status"),"ready")
        code,health=manager.health_command();self.assertEqual(code,0);self.assertTrue(health.get("healthy"))

if __name__=="__main__":unittest.main()
