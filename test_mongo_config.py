"""Run directly with Python; no app imports, credentials, or database are needed."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.mongo_config import resolve_mongo_config


class MongoConfigTests(unittest.TestCase):
    host = "mongodb+srv://example.invalid/?retryWrites=true&w=majority"

    def test_existing_uri_credentials_are_left_unchanged(self):
        uri = "mongodb://fixture-user:fixture-password@example.invalid:27017/app?authSource=app"
        self.assertEqual(resolve_mongo_config({"MONGO_URL": uri}), (uri, {}))

    def test_empty_optional_credentials_keep_uri_mode(self):
        self.assertEqual(
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "", "MONGO_PASSWORD": "", "MONGO_PASSWORD_ENV": ""}),
            (self.host, {}),
        )

    def test_separate_credentials_use_atlas_auth_source(self):
        uri, options = resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "MONGO_PASSWORD": "fixture-password"})
        self.assertEqual(uri, self.host)
        self.assertEqual(options, {"username": "fixture-user", "password": "fixture-password", "authSource": "admin"})

    def test_password_whitespace_and_special_characters_are_preserved(self):
        password = "  fixture:@/$%+#? password  "
        _, options = resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "MONGO_PASSWORD": password})
        self.assertEqual(options["password"], password)

    def test_existing_secret_can_be_referenced_explicitly(self):
        password = " fixture-secret:@/ "
        _, options = resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "MONGO_PASSWORD_ENV": "EXISTING_DB_SECRET", "EXISTING_DB_SECRET": password})
        self.assertEqual(options["password"], password)
        self.assertEqual(options["username"], "fixture-user")

    def test_username_does_not_implicitly_select_a_secret(self):
        with self.assertRaisesRegex(RuntimeError, "wajib diatur bersama"):
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "fixture-user": "fixture-secret"})

    def test_username_without_password_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "wajib diatur bersama"):
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user"})

    def test_password_without_username_is_rejected_without_disclosure(self):
        password = "fixture-private-password"
        with self.assertRaises(RuntimeError) as caught:
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_PASSWORD": password})
        self.assertNotIn(password, str(caught.exception))
        self.assertNotIn(self.host, str(caught.exception))

    def test_missing_or_empty_referenced_secret_is_rejected(self):
        for values in ({}, {"EXISTING_DB_SECRET": ""}):
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, "secret kata sandi yang tersedia"):
                resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "MONGO_PASSWORD_ENV": "EXISTING_DB_SECRET", **values})

    def test_two_password_sources_are_rejected_without_disclosure(self):
        direct, referenced = "fixture-direct-private", "fixture-referenced-private"
        with self.assertRaises(RuntimeError) as caught:
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_USERNAME": "fixture-user", "MONGO_PASSWORD": direct, "MONGO_PASSWORD_ENV": "EXISTING_DB_SECRET", "EXISTING_DB_SECRET": referenced})
        self.assertNotIn(direct, str(caught.exception))
        self.assertNotIn(referenced, str(caught.exception))

    def test_referenced_password_requires_a_username(self):
        with self.assertRaisesRegex(RuntimeError, "wajib diatur bersama"):
            resolve_mongo_config({"MONGO_URL": self.host, "MONGO_PASSWORD_ENV": "EXISTING_DB_SECRET", "EXISTING_DB_SECRET": "fixture-secret"})

    def test_missing_or_blank_uri_is_rejected(self):
        for values in ({}, {"MONGO_URL": ""}, {"MONGO_URL": "  "}):
            with self.subTest(values=values), self.assertRaisesRegex(RuntimeError, "MONGO_URL wajib diatur"):
                resolve_mongo_config(values)


if __name__ == "__main__":
    unittest.main()
