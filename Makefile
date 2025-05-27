up:
	docker compose up --build -d

down:
	docker compose down -v

restart:
	docker compose restart web

logs:
	docker compose logs -f

logs-web:
	docker compose logs -f web

logs-chainlit:
	docker compose logs -f chainlit

logs-db:
	docker compose logs -f db

status:
	docker compose ps

rebuild:
	docker compose up --build --force-recreate -d

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

shell-web:
	docker compose exec web sh

shell-chainlit:
	docker compose exec chainlit sh

test-chainlit:
	curl -I http://localhost:8500

test-web:
	curl -I http://localhost:8000
