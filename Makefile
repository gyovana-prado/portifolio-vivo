.PHONY: help validate build dev preview check test install drain

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install site + mcp dependencies
	cd site && npm install
	cd mcp && uv sync

validate: ## Validate content/ against the schemas (fails on missing translations)
	uv run --project mcp python mcp/validate_content.py

build: validate ## Validate then build the static site
	cd site && npm run build

dev: ## Run the Astro dev server
	cd site && npm run dev

preview: ## Preview the built site locally
	cd site && npm run preview

test: ## Run the MCP server unit tests
	uv run --project mcp pytest -q

check: validate test ## Full local gate: validate content + run tests
	@echo "✓ All checks passed."

drain: ## Evaluate captured sessions (headless claude -p → drafts via MCP)
	python3 hooks/drain_queue.py
