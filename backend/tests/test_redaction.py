import unittest

from backend.utils.redaction import redact_code_excerpt, redact_context


class SecretRedactionTests(unittest.TestCase):
    def test_multiline_assignments_preserve_adjacent_source(self):
        for prefix, quote in (("", '"""'), ("r", "'''"), ("fr", '"""')):
            with self.subTest(prefix=prefix, quote=quote):
                source = (
                    f"password = {prefix}{quote}fake-secret\n"
                    f"second-secret-line{quote}\nlabel = 'visible'"
                )
                expected = 'password = "[REDACTED]"\nlabel = \'visible\''
                self.assertEqual(redact_code_excerpt(source), expected)
                self.assertEqual(redact_context({"body_text": source}), {"body_text": expected})

    def test_excerpt_cut_inside_multiline_secret(self):
        excerpt = 'api_key = """fake-secret\nsecond-secret-line\\'
        self.assertEqual(redact_code_excerpt(excerpt), 'api_key = "[REDACTED]"')

    def test_single_line_secret_forms_still_redact(self):
        source = "password = 'fake-secret'\nTOKEN=fake-token\napi_key=r'fake-key'"
        self.assertEqual(
            redact_code_excerpt(source),
            'password = "[REDACTED]"\nTOKEN="[REDACTED]"\napi_key="[REDACTED]"',
        )
