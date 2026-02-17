"""Tests for JWT token lifecycle."""
import time
import uuid
from datetime import timedelta

import jwt

from src.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_access_token,
    verify_refresh_token,
)

JWT_DECODE_OPTS = {
    "algorithms": [ALGORITHM],
    "issuer": "homeoffice-shop",
    "audience": "homeoffice-shop",
}


class TestCreateAccessToken:
    def test_creates_valid_jwt(self):
        user_id = str(uuid.uuid4())
        token = create_access_token(user_id, "user@example.com", "employee")
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert payload["sub"] == user_id
        assert payload["email"] == "user@example.com"
        assert payload["role"] == "employee"
        assert payload["type"] == "access"

    def test_includes_jti(self):
        token = create_access_token(str(uuid.uuid4()), "u@x.com", "admin")
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert "jti" in payload
        uuid.UUID(payload["jti"])  # must be valid UUID

    def test_custom_expiry(self):
        token = create_access_token(
            str(uuid.uuid4()), "u@x.com", "employee",
            expires_delta=timedelta(minutes=5),
        )
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert payload["exp"] is not None

    def test_unique_jti_per_call(self):
        uid = str(uuid.uuid4())
        t1 = create_access_token(uid, "u@x.com", "employee")
        t2 = create_access_token(uid, "u@x.com", "employee")
        p1 = jwt.decode(t1, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        p2 = jwt.decode(t2, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert p1["jti"] != p2["jti"]

    def test_includes_iss_and_aud(self):
        token = create_access_token(str(uuid.uuid4()), "u@x.com", "employee")
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert payload["iss"] == "homeoffice-shop"
        assert payload["aud"] == "homeoffice-shop"


class TestCreateRefreshToken:
    def test_returns_token_and_jti(self):
        user_id = str(uuid.uuid4())
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(user_id, family)
        assert isinstance(token, str)
        assert isinstance(jti, str)
        uuid.UUID(jti)  # must be valid UUID

    def test_refresh_type(self):
        token, jti = create_refresh_token(str(uuid.uuid4()), str(uuid.uuid4()))
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_family_embedded(self):
        family = str(uuid.uuid4())
        token, _ = create_refresh_token(str(uuid.uuid4()), family)
        payload = jwt.decode(token, "test-secret-key-for-unit-tests-must-be-32-chars", **JWT_DECODE_OPTS)
        assert payload["token_family"] == family


class TestVerifyAccessToken:
    def test_valid_access_token(self):
        uid = str(uuid.uuid4())
        token = create_access_token(uid, "u@x.com", "employee")
        payload = verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["type"] == "access"

    def test_rejects_refresh_token(self):
        token, _ = create_refresh_token(str(uuid.uuid4()), str(uuid.uuid4()))
        assert verify_access_token(token) is None

    def test_rejects_invalid_token(self):
        assert verify_access_token("garbage.token.data") is None

    def test_rejects_expired_token(self):
        token = create_access_token(
            str(uuid.uuid4()), "u@x.com", "employee",
            expires_delta=timedelta(seconds=-1),
        )
        assert verify_access_token(token) is None

    def test_rejects_wrong_secret(self):
        token = create_access_token(str(uuid.uuid4()), "u@x.com", "employee")
        tampered = jwt.encode(
            {"sub": "hacker", "type": "access", "exp": 9999999999,
             "iss": "homeoffice-shop", "aud": "homeoffice-shop"},
            "wrong-secret",
            algorithm=ALGORITHM,
        )
        assert verify_access_token(tampered) is None


class TestVerifyRefreshToken:
    def test_valid_refresh_token(self):
        uid = str(uuid.uuid4())
        family = str(uuid.uuid4())
        token, jti = create_refresh_token(uid, family)
        payload = verify_refresh_token(token)
        assert payload is not None
        assert payload["sub"] == uid
        assert payload["type"] == "refresh"
        assert payload["jti"] == jti

    def test_rejects_access_token(self):
        token = create_access_token(str(uuid.uuid4()), "u@x.com", "employee")
        assert verify_refresh_token(token) is None

    def test_rejects_invalid_token(self):
        assert verify_refresh_token("not.a.token") is None

    def test_rejects_expired_refresh(self):
        token, _ = create_refresh_token(
            str(uuid.uuid4()), str(uuid.uuid4()),
            expires_delta=timedelta(seconds=-1),
        )
        assert verify_refresh_token(token) is None


class TestDecodeToken:
    def test_decodes_valid_token(self):
        uid = str(uuid.uuid4())
        token = create_access_token(uid, "u@x.com", "admin")
        payload = decode_token(token)
        assert payload["sub"] == uid
        assert payload["role"] == "admin"
