DATASET ?= data/Market-cloudbed-1
QUERIES ?= $(DATASET)/dev/query_dev.csv
OUT     ?= out/dev
PY      ?= python3

.PHONY: help dev score cost check calib ablate significance probe compare webapp docker clean
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

calib: ## is the confidence word worth anything? -> eval/calibration.md
	$(PY) eval/calibration.py --out $(OUT) --queries $(QUERIES)

ablate: ## measure each decision separately -> eval/results.md
	$(PY) eval/ablate.py --dataset $(DATASET)

significance: ## which findings survive the sample size -> eval/significance.md
	$(PY) eval/significance.py

probe: ## what each GLM model actually does -> eval/models.md (needs the key)
	$(PY) eval/probe_models.py

compare: ## free vs routed vs single-model on 20 cases -> eval/routed_compare.md
	rm -rf out/free20 out/nothink out/think
	$(PY) run.py --dataset $(DATASET) --queries $(QUERIES) --out out/free20 \
	  --agent agents.rca --limit 20
	RCA_THINK=0 $(PY) run.py --dataset $(DATASET) --queries $(QUERIES) \
	  --out out/nothink --agent agents.routed --limit 20
	RCA_THINK=1 $(PY) run.py --dataset $(DATASET) --queries $(QUERIES) \
	  --out out/think --agent agents.routed --limit 20
	@for d in free20 nothink think; do \
	  echo "== $$d =="; \
	  $(PY) score.py --predictions out/$$d/predictions.csv --queries $(QUERIES) | head -4; \
	  test -f out/$$d/usage.jsonl && $(PY) cost.py out/$$d/usage.jsonl | tail -3 || true; \
	done

webapp: ## the RCA console on :8100 — solve free, grade with GLM (needs FEATHERLESS_API_KEY)
	$(PY) -m uvicorn webapp.server:app --host 127.0.0.1 --port 8100

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
