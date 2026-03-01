"""Unit tests for auth pure functions — no DB or network required."""
import uuid

import pytest

from app.services.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("secret")
        assert hashed != "secret"

    def test_verify_correct_password(self):
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_same_password_produces_different_hashes(self):
        # bcrypt uses a random salt
        assert hash_password("pw") != hash_password("pw")


class TestJWTTokens:
    def test_access_token_roundtrip(self):
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_decode_invalid_token_returns_none(self):
        assert decode_token("not.a.token") is None

    def test_decode_tampered_token_returns_none(self):
        token = create_access_token(uuid.uuid4())
        tampered = token[:-4] + "xxxx"
        assert decode_token(tampered) is None

    def test_access_and_refresh_tokens_differ(self):
        user_id = uuid.uuid4()
        assert create_access_token(user_id) != create_refresh_token(user_id)
