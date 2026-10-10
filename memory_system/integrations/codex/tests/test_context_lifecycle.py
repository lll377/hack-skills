from __future__ import annotations
import json
import pathlib
import sys
import unittest

HERE=pathlib.Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
from context_hook import infer_context, related, render_anchor, summarize_tool
from redact import redact_text, redact_value
from security_context_schema import normalize_context, validate_context

class ContextLifecycleUnitTests(unittest.TestCase):
    def context(self):
        return normalize_context({
            "project_name":"stage2","platform":"PortSwigger Web Security Academy","target":"Username enumeration via different responses","lab_name":"Username enumeration via different responses","vulnerability_type":"Authentication","objective":"username enumeration","actions":["compare two responses"],"observations":["stable response difference"],"confirmed_findings":["stable difference"],"unverified_items":["valid username"],"failed_attempts":["FAILED: stale csrf token"],"next_step":"fetch a fresh csrf token","tools":["shell_command"],"skills":["authbypass-authentication-flaws"],"status":"IN_PROGRESS","solved":False,
        })
    def test_schema_status_rules(self):
        context=self.context();self.assertTrue(validate_context(context)[0])
        solved=normalize_context({**context,"status":"SOLVED","solved":True,"evidence_paths":[]})
        self.assertEqual(solved["status"],"UNVERIFIED")
        self.assertFalse(solved["solved"])
    def test_related_and_unrelated(self):
        context=self.context();self.assertTrue(related("continue the previous lab",context));self.assertFalse(related("organize a local document index",context))
    def test_anchor_is_bounded_schema_projection(self):
        anchor=render_anchor(self.context());self.assertIn("PortSwigger Web Security Academy",anchor);self.assertIn("Username enumeration via different responses",anchor);self.assertNotIn("FULL_OUTPUT",anchor)
    def test_tool_summary_excludes_full_output(self):
        item=summarize_tool({"session_id":"s","turn_id":"t","tool_name":"shell_command","tool_input":{"operation":"verify"},"tool_response":{"success":True,"result_summary":"passed","output":"FULL_OUTPUT"+("X"*5000)}})
        encoded=json.dumps(item,ensure_ascii=False);self.assertNotIn("FULL_OUTPUT",encoded);self.assertLessEqual(len(item["result_summary"]),700)
    def test_redaction_forms(self):
        raw="Cookie: C1 Authorization: Bearer B1 csrf=C2 csrf_token=C3 password=P1 API Key: K1 eyJABCDEFGH.ijklMNOPQR.stuvWXYZ12"
        clean=redact_text(raw)
        for marker in ["C1","B1","C2","C3","P1","K1","eyJABCDEFGH.ijklMNOPQR.stuvWXYZ12"]:self.assertNotIn(marker,clean)
        nested=redact_value({"outer":{"token":"N1"},"body":"csrf%3DU1"});self.assertNotIn("N1",json.dumps(nested));self.assertNotIn("U1",json.dumps(nested))
    def test_inference_preserves_existing_objective(self):
        base=self.context();updated=infer_context({"prompt":"continue the previous lab"},base);self.assertEqual(updated["objective"],base["objective"])

if __name__=="__main__":unittest.main()
