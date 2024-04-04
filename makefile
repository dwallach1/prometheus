

build-docker:
	docker build -t prometheus-trader .

run-docker:
	docker run --rm -it \
	-e MONGO_URI=$(MONGO_URI)
	-e DB_NAME=$(DB_NAME)
	-e DB_COLLECTION=$(DB_COLLECTION)
	-e COINBASE_API_KEY=$(COINBASE_API_KEY)
	-e COINBASE_API_SECRET=$(COINBASE_API_SECRET)
	 prometheus-trader



set-env:
	export $(grep -v '^#' .env | xargs)