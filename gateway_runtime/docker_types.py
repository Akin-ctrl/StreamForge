"""Lightweight protocols for optional Docker SDK interactions.

These protocols keep the runtime/container managers typed without forcing the
docker SDK to be installed at import time. They intentionally model only the
small subset of the client and container surface that the runtime uses.
"""

from __future__ import annotations

from typing import Protocol, Sequence


class DockerContainerLike(Protocol):
    """Minimal container interface used by runtime managers."""

    name: str
    id: str
    status: str
    labels: dict[str, str]
    attrs: dict[str, object]

    def start(self) -> object: ...
    def stop(self, timeout: int = 0) -> object: ...
    def remove(self) -> object: ...
    def exec_run(self, command: Sequence[str]) -> object: ...


class DockerContainersApiLike(Protocol):
    """Minimal container collection interface used by runtime managers."""

    def get(self, target: str) -> DockerContainerLike: ...
    def list(self, all: bool = False) -> Sequence[DockerContainerLike]: ...
    def run(self, **kwargs: object) -> DockerContainerLike: ...


class DockerClientLike(Protocol):
    """Minimal Docker client interface used by runtime managers."""

    containers: DockerContainersApiLike
