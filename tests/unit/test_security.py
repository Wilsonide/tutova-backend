from app.core.security import hash_password, verify_password, hash_refresh_token, new_refresh_token, create_access_token, decode_access_token
def test_argon2_password_hashing():
    encoded = hash_password("a-long-and-unique-test-password")
    assert encoded != "a-long-and-unique-test-password"
    assert verify_password("a-long-and-unique-test-password", encoded)
    assert not verify_password("incorrect-password", encoded)
def test_refresh_tokens_are_random_and_hashed():
    first, second = new_refresh_token(), new_refresh_token()
    assert first != second
    assert hash_refresh_token(first) != first
    assert hash_refresh_token(first) != hash_refresh_token(second)
def test_access_token_contains_subject_and_role():
    token = create_access_token("00000000-0000-0000-0000-000000000001", "PARENT")
    payload = decode_access_token(token)
    assert payload["sub"].endswith("0001") and payload["role"] == "PARENT" and payload["type"] == "access"
