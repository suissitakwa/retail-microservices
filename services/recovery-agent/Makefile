# Evaluation needs recovery-db running; the model arm needs OPENAI_API_KEY in the environment.
.PHONY: test lint eval-dev eval-heldout benchmark

test:
	uv run pytest -q

lint:
	uv run ruff check .

# Build-time evaluation: tune against this split freely
eval-dev:
	uv run python -m recovery_agent.evaluation.run --split dev
	uv run python -m recovery_agent.evaluation.report

# Reported benchmark: run once on the frozen split, never tune against it
eval-heldout:
	uv run python -m recovery_agent.evaluation.run --split heldout --confirm-heldout
	uv run python -m recovery_agent.evaluation.report

benchmark:
	uv run python -m recovery_agent.evaluation.report
