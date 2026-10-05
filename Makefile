.PHONY: sync download build smoke test lint verify package proto

sync:
	uv sync --all-groups

download:
	uv run monatendard fetch

build:
	uv run monatendard build --all
	uv run monatendard build-nerd --all

smoke:
	uv run monatendard build --variants Regular
	uv run monatendard build-nerd --variants Regular

test:
	uv run pytest

lint:
	uv run ruff check .

verify:
	uv run monatendard verify
	uv run monatendard verify --nerd

package:
	uv run monatendard package --version 0.2.3

PROTO_VARIANTS = Light Regular Bold

proto:
	for profile in proto-a proto-b proto-c; do \
		uv run monatendard build --profile $$profile --variants $(PROTO_VARIANTS) && \
		uv run monatendard build-nerd --profile $$profile --variants $(PROTO_VARIANTS) && \
		uv run monatendard verify --profile $$profile && \
		uv run monatendard verify --profile $$profile --nerd || exit 1; \
	done
	uv run python tools/render_comparison.py
