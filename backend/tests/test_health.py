import unittest

from fastapi.testclient import TestClient

from main import app


class TestHealth(unittest.TestCase):
    def test_health(self):
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()
