import pytest

from trigrix_studio.runtime import CapsuleError, decode_capsule, encode_capsule


def test_context_capsule_round_trip_and_hmac() -> None:
    payload = {"p": "abc123", "n": 17, "vars": {"service": "03"}, "request_id": "VM-K7F4P2"}
    encoded = encode_capsule(payload, "123:secret")
    decoded = decode_capsule(encoded, "123:secret")
    assert decoded["vars"]["service"] == "03"
    assert decoded["v"] == 1


def test_context_capsule_rejects_tampering() -> None:
    encoded = encode_capsule({"n": 2}, "123:secret")
    damaged = ("A" if encoded[0] != "A" else "B") + encoded[1:]
    with pytest.raises(CapsuleError):
        decode_capsule(damaged, "123:secret")


def test_context_capsule_rejects_wrong_key() -> None:
    encoded = encode_capsule({"n": 2}, "123:secret")
    with pytest.raises(CapsuleError):
        decode_capsule(encoded, "other")

