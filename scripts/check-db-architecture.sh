#!/bin/sh
set -eu

container_name="${1:-}"

normalize_architecture() {
    case "$1" in
        aarch64) printf '%s\n' arm64 ;;
        x86_64) printf '%s\n' amd64 ;;
        *) printf '%s\n' "$1" ;;
    esac
}

if [ -z "$container_name" ]; then
    container_name="$(docker compose ps -q db)"
fi

if [ -z "$container_name" ]; then
    printf '%s\n' 'Database container is not running; pass its name or start Compose first.' >&2
    exit 1
fi

server_architecture="$(normalize_architecture "$(docker info --format '{{.Architecture}}')")"
container_architecture="$(normalize_architecture "$(docker exec "$container_name" uname -m)")"

if [ "$server_architecture" != "$container_architecture" ]; then
    printf 'Database architecture mismatch: Docker server=%s, DB container=%s.\n' \
        "$server_architecture" "$container_architecture" >&2
    printf '%s\n' \
        'Cross-architecture PostgreSQL is unsupported for this project.' >&2
    exit 1
fi

printf 'Database architecture match: Docker server=%s, DB container=%s\n' \
    "$server_architecture" "$container_architecture"
