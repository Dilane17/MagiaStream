import os
import time
import unittest
from pathlib import Path

from magia_stream.utils import sanitize_filename, tenacity_retry, ensure_directory


class UtilsTests(unittest.TestCase):
    def test_sanitize_filename(self):
        raw = "My File: / unsafe *name?.mp4"
        out = sanitize_filename(raw)
        self.assertNotIn(" ", out)
        self.assertNotIn("/", out)

    def test_ensure_directory(self):
        p = Path(".tmp/test_dir")
        if p.exists():
            for child in p.iterdir():
                child.unlink()
            p.rmdir()
        ensure_directory(p)
        self.assertTrue(p.exists())
        # cleanup
        for child in p.iterdir():
            child.unlink()
        p.rmdir()

    def test_retry_fallback(self):
        calls = {"n": 0}

        @tenacity_retry(retries=3, min_wait=0, max_wait=0, retry_exceptions=ValueError)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("fail")
            return True

        start = time.time()
        res = flaky()
        end = time.time()
        self.assertTrue(res)
        self.assertGreaterEqual(calls["n"], 3)


if __name__ == "__main__":
    unittest.main()
