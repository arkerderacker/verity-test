"""iOS / aShell mic stub — no CLI microphone access."""

from __future__ import annotations


def mic_backend_name() -> str:
    return "OFF (iOS — chat only, no !talk mic)"


def list_input_devices() -> list[str]:
    return ["[iOS] No microphone — type chat to Verity"]


def record_microphone_wav(_device=None, _seconds: float = 5.0) -> str:
    raise RuntimeError(
        "iOS cannot record the mic. Type chat to Verity instead of !talk."
    )
