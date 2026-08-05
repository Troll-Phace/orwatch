"""Prove the offline network guard is wired up and actually blocks sockets."""

import socket

import pytest
from conftest import NetworkAccessDenied


def test_network_guard_blocks_unmarked_socket_connection():
    """An unmarked test that calls socket.create_connection must be denied."""
    with pytest.raises(NetworkAccessDenied):
        socket.create_connection(("example.com", 443))


def test_network_guard_blocks_raw_socket_connect():
    """The low-level socket.socket().connect path is denied too, not just the
    create_connection helper. The guard patches both surfaces (conftest)."""
    with socket.socket() as s, pytest.raises(NetworkAccessDenied):
        s.connect(("example.com", 443))
