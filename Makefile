DATASET ?= data/Market-cloudbed-1
QUERIES ?= $(DATASET)/dev/query_dev.csv
OUT     ?= out/dev
PY      ?= python3

.PHONY: help dev score cost check ablate docker clean
.DEFAULT_GOAL := help

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

dev: ## run the agent over the dev split -> $(OUT)
	$(PY) run.py --dataset $(DATASET) --queries $(QUERIES) --out $(OUT) \
	  $(if $(N),--limit $(N),) $(if $(AGENT),--agent $(AGENT),)

score: ## score $(OUT) with OpenRCA's own evaluator
	$(PY) score.py --predictions $(OUT)/predictions.csv --queries $(QUERIES)

cost: ## dollars per case and per model, from $(OUT)/usage.jsonl
	$(PY) cost.py $(OUT)/usage.jsonl

check: ## THE GATE: is this submission judgeable? (run dev first)
	$(PY) eval/gate.py --out $(OUT) --queries $(QUERIES)

ablate: ## measure each decision separately -> eval/results.md
	$(PY) eval/ablate.py --dataset $(DATASET)

docker: ## build and run exactly as the judges do, on 2 cases
	docker build -t rca-submission .
	rm -rf out/docker && mkdir -p out/docker
	docker run --rm -e FEATHERLESS_API_KEY -e FEATHERLESS_BASE_URL \
	  -v "$(CURDIR)/$(DATASET)":/data:ro -v "$(CURDIR)/out/docker":/out \
	  rca-submission \
	  python run.py --dataset /data --queries /data/dev/query_dev.csv --out /out --limit 2
	@echo "evidence files: $$(ls out/docker/evidence | wc -l)"

clean:
	rm -rf out
