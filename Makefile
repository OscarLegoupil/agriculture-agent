.PHONY: setup test lint typecheck fmt sim view ci clean

setup:
	uv sync --extra dev
	uv run pre-commit install

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy src

fmt:
	uv run ruff format .

sim:
	uv run python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720, 'seed': 0}); env.run(['pass', 'starter']); s = env.steps[-1]; print(f'Player 0: {s[0].reward:.0f}  Player 1: {s[1].reward:.0f}  status={s[0].status}')"

view:
	uv run kagg-view $(A) $(B) --seed $(if $(SEED),$(SEED),0)

ci: lint fmt-check typecheck test

fmt-check:
	uv run ruff format --check .

clean:
	uv run python -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in ['.pytest_cache', '.mypy_cache', '.ruff_cache', 'htmlcov', 'build', 'dist']]; [p.unlink() for p in pathlib.Path('.').rglob('*.egg-info') if p.is_file()]"
