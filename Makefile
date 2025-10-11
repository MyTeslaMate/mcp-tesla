install:
	 cd app && pip3 install -r requirements.txt
prep:
	 cd app && python3 prep_data.py
run:
	 cd app && PYTHONPATH=../.. python3 -m main
test:
	 cd app && pytest evals.py -v

# dev
dev:
	uvicorn tesla_mcp.app:app --host 0.0.0.0 --port 8084 --reload
up:
	docker compose up --build
#	 --build
build:
	docker compose build
	 