"""認証依存（app.core.auth.get_current_user）の単体テスト。

- /health は無認証で 200 を返す
- 認証必須エンドポイント（例: /categories）はトークン無しで 401 を返す
- dependency_overrides でユーザーを差し替えれば 200 で通る
"""
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from jose import jwt

from app.core import auth as auth_module
from app.core.database import get_db
from app.models import User
from main import app


def _stub_user() -> User:
    user = User()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.email = "test@example.com"
    user.role = "owner"
    return user


def _override_db():
    """空のクエリ結果を返すスタブセッション。認証層が通った先で DB を触っても落ちない。"""
    session = MagicMock()
    session.query.return_value.order_by.return_value.all.return_value = []
    try:
        yield session
    finally:
        session.close()


class TestAuthDependency(unittest.TestCase):
    def setUp(self) -> None:
        # `get_current_user` は内部で DB を引くため、テストでは get_db をスタブに固定する。
        # DATABASE_URL 未設定の CI でも回るようにする狙い。
        app.dependency_overrides[get_db] = _override_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_health_does_not_require_auth(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_protected_endpoint_returns_401_without_token(self) -> None:
        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers.get("WWW-Authenticate"), "Bearer")

    def test_protected_endpoint_returns_401_with_invalid_token(self) -> None:
        response = self.client.get(
            "/categories",
            headers={"Authorization": "Bearer not-a-real-jwt"},
        )
        self.assertEqual(response.status_code, 401)

    def test_protected_endpoint_returns_500_when_hs256_secret_missing(self) -> None:
        token = jwt.encode(
            {
                "sub": "00000000-0000-0000-0000-000000000001",
                "aud": "authenticated",
                "iss": "https://example.supabase.co/auth/v1",
            },
            "test-secret",
            algorithm="HS256",
        )
        with (
            patch.object(auth_module, "SUPABASE_URL", "https://example.supabase.co"),
            patch.object(auth_module, "SUPABASE_JWT_SECRET", ""),
        ):
            response = self.client.get(
                "/categories",
                headers={"Authorization": f"Bearer {token}"},
            )
        self.assertEqual(response.status_code, 500)

    def test_dependency_override_allows_request(self) -> None:
        app.dependency_overrides[auth_module.get_current_user] = _stub_user

        response = self.client.get("/categories")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])


if __name__ == "__main__":
    unittest.main()
