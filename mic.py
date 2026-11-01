"""Mic backend for iOS setup — always the no-mic stub."""

from __future__ import annotations

from ios_mic import (  # noqa: F401
    list_input_devices,
    mic_backend_name,
    record_microphone_wav,
)
