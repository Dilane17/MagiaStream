import os
import tempfile
from pathlib import Path

import unittest

from magia_stream.config import Config
from magia_stream.exceptions import ConfigError


class ConfigFromEnvTests(unittest.TestCase):
    def setUp(self):
        # backup env
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_default_config(self):
        cfg = Config.from_env()
        self.assertTrue(cfg.BASE_URL.startswith("http"))

    def test_invalid_base_url(self):
        os.environ["BASE_URL"] = "not-a-url"
        with self.assertRaises(ConfigError):
            Config.from_env()

    def test_custom_dirs_and_types(self):
        tmp = tempfile.mkdtemp()
        os.environ["OUTPUT_DIR"] = tmp
        os.environ["TEMP_DIR"] = tmp
        os.environ["TIMEOUT_SECONDS"] = "10"
        cfg = Config.from_env()
        self.assertEqual(cfg.TIMEOUT_SECONDS, 10)
        self.assertEqual(str(cfg.OUTPUT_DIR), tmp)


if __name__ == "__main__":
    unittest.main()
