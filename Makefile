up:
	docker compose up --build -d

down:
	docker compose down -v

restart:
	docker compose restart web
