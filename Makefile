.PHONY: validate upstreams test qualify oracle replay export-platform release-check

validate:
	python3 -m faraday_industrial_benchmark validate

upstreams:
	python3 -m faraday_industrial_benchmark upstreams --verify

test:
	python3 -m pytest -q

qualify:
	python3 -m faraday_industrial_benchmark qualify --output reports/qualification.json

oracle:
	python3 -m faraday_industrial_benchmark run --agent oracle --output reports/oracle-run.json --html reports/oracle-run.html

replay:
	python3 -m faraday_industrial_benchmark replay reports/oracle-run.json

export-platform:
	python3 -m faraday_industrial_benchmark export-harness --output runs/faraday-platform-harness.json

release-check: validate upstreams test qualify oracle replay
