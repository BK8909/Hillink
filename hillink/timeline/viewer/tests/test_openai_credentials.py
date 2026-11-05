import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from timeline.viewer.openai_credentials import OpenAIConfigError, read_key_file


class LocalOpenAICredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "openai.env"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, content, mode=0o600):
        self.path.write_text(content, encoding="utf-8")
        self.path.chmod(mode)

    def test_reads_key_without_logging_it(self):
        self.write("OPENAI_API_KEY=sk-test_fake_credential_123456789\n")
        self.assertEqual(read_key_file(self.path), "sk-test_fake_credential_123456789")

    def test_empty_key_has_clear_redacted_error(self):
        self.write("OPENAI_API_KEY=\n")
        with self.assertRaisesRegex(OpenAIConfigError, "empty or malformed") as caught:
            read_key_file(self.path)
        self.assertNotIn("sk-test", str(caught.exception))

    def test_duplicate_assignment_is_rejected(self):
        self.write("OPENAI_API_KEY=one\nOPENAI_API_KEY=two\n")
        with self.assertRaisesRegex(OpenAIConfigError, "one OPENAI_API_KEY"):
            read_key_file(self.path)

    def test_group_or_world_access_is_rejected(self):
        self.write("OPENAI_API_KEY=sk-test_fake_credential_123456789\n", 0o644)
        with self.assertRaisesRegex(OpenAIConfigError, "permissions"):
            read_key_file(self.path)

    def test_missing_file_has_clear_error(self):
        with self.assertRaisesRegex(OpenAIConfigError, "file is missing"):
            read_key_file(self.path)

    def test_external_llm_requires_explicit_opt_in_before_loading_key(self):
        import sys
        viewer = Path(__file__).resolve().parents[1]
        exp = viewer.parent / "experiments" / "persona_live"
        sys.path.insert(0, str(exp))
        from operator_choice.autonomy_v1 import llm_layer
        from operator_choice.operator_world_v1_1 import stay_planner
        with patch.dict(os.environ, {"HILLINK_LLM_ENABLED": "1"}, clear=False):
            os.environ.pop("HILLINK_LLM_EXTERNAL_OPT_IN", None)
            self.assertFalse(llm_layer.cfg()["has_key"])
            self.assertIn("차단됨", llm_layer.cfg()["key_error"])
            with patch.object(stay_planner, "load_openai_api_key", side_effect=AssertionError("key loader must not run")):
                self.assertFalse(stay_planner.llm_available())
                with self.assertRaisesRegex(RuntimeError, "차단됨"):
                    stay_planner.plan_llm({}, [], {}, {})
            from timeline.viewer import llm_pilot
            with patch.object(llm_pilot, "load_openai_api_key", side_effect=AssertionError("key loader must not run")):
                with self.assertRaisesRegex(SystemExit, "EXTERNAL_OPT_IN"):
                    llm_pilot.api_key()
            prior_cfg, prior_calls = llm_layer.USAGE.cfg, llm_layer.USAGE.calls
            llm_layer.USAGE.cfg = {"model": "offline", "mock": False, "replay": False, "cache": None,
                                   "enabled": True, "key_present": True, "max_calls": 20, "max_cost": 2}
            llm_layer.USAGE.calls = []
            try:
                from types import SimpleNamespace
                self.assertIsNone(llm_layer._call(SimpleNamespace(pid="TEST"), "offline guard check"))
                self.assertEqual(llm_layer.USAGE.cfg["key_present"], True)
                self.assertIn("opt-in", llm_layer.USAGE.calls[-1]["error"])
            finally:
                llm_layer.USAGE.cfg, llm_layer.USAGE.calls = prior_cfg, prior_calls

    def test_credential_shim_blocks_direct_load_and_auth_without_opt_in(self):
        from timeline.viewer import openai_credentials
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(openai_credentials, "_call", side_effect=AssertionError("loader must not run")):
            with self.assertRaisesRegex(OpenAIConfigError, "EXTERNAL_OPT_IN"):
                openai_credentials.load_openai_api_key()
            with self.assertRaisesRegex(OpenAIConfigError, "EXTERNAL_OPT_IN"):
                openai_credentials.verify_openai_auth()

    def test_key_file_is_sufficient_without_a_home_directory_python_module(self):
        from timeline.viewer import openai_credentials as C, openai_key_file as K
        self.write('OPENAI_API_KEY="sk-test_fake_credential_123456789"\n')
        self.assertEqual(Path(C._loader().__file__).resolve(), Path(K.__file__).resolve())
        with patch.object(K, 'KEY_FILE', self.path), patch.dict(os.environ, {'HILLINK_LLM_EXTERNAL_OPT_IN':'1'}, clear=True):
            self.assertEqual(C.load_openai_api_key(), 'sk-test_fake_credential_123456789')
            self.assertEqual(os.environ['OPENAI_API_KEY'], 'sk-test_fake_credential_123456789')

    def test_direct_implementation_also_requires_opt_in(self):
        from timeline.viewer import openai_key_file as K
        with patch.dict(os.environ, {}, clear=True), patch.object(K, 'read_key_file', side_effect=AssertionError('no key read')):
            with self.assertRaisesRegex(K.OpenAIConfigError, 'EXTERNAL_OPT_IN'):
                K.load_openai_api_key()
            with self.assertRaisesRegex(K.OpenAIConfigError, 'EXTERNAL_OPT_IN'):
                K.verify_openai_auth()

    def test_auth_error_does_not_return_provider_body_or_key(self):
        from timeline.viewer import openai_credentials as C, openai_key_file as K
        from urllib.error import HTTPError
        from io import BytesIO
        self.write('OPENAI_API_KEY=sk-test_fake_credential_123456789\n')
        error = HTTPError('https://api.openai.com/v1/models',401,'sensitive error body',{},BytesIO(b'sk-secret-do-not-return'))
        with patch.object(K, 'KEY_FILE', self.path), patch.dict(os.environ, {'HILLINK_LLM_EXTERNAL_OPT_IN':'1'}, clear=True), patch.object(K, 'urlopen', side_effect=error):
            self.assertEqual(C.verify_openai_auth(), 'INVALID_KEY_401')


if __name__ == "__main__":
    unittest.main()
