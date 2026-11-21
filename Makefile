.PHONY: sync download build smoke test lint verify package compact

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
	uv run python -c "from monatendard.sources import load_lock; from monatendard.cli import main; raise SystemExit(main(['package', '--version', load_lock()['project']['version']]))"

# 공식 배포하지 않는 선택 빌드. 출력은 build/profiles/compact/이다.
compact:
	uv run monatendard build --profile compact --all
	uv run monatendard build-nerd --profile compact --all
	uv run monatendard verify --profile compact
	uv run monatendard verify --profile compact --nerd
