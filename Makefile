.PHONY: install test test-integration finance panel
install:
	python -m pip install -r requirements.lock.txt
test:
	python -m pytest -m "not integration" -q
test-integration:
	python -m pytest -m integration -q
finance:
	python run.py finance
panel:
	python run.py panel
