.PHONY: build up down logs ps restart clean backup restore

# Docker Compose commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

ps:
	docker-compose ps

restart:
	docker-compose restart

# Database operations
backup:
	./backup_database.sh

restore:
	@if [ -z "$(file)" ]; then \
		echo "Usage: make restore file=<backup_file.sql.gz>"; \
		exit 1; \
	fi
	./restore_database.sh $(file)

# Cleanup
clean:
	docker-compose down -v
	rm -rf staticfiles/
	rm -rf media/

# Development setup
setup:
	make build
	make up
	docker-compose exec web python manage.py migrate
	docker-compose exec web python manage.py createsuperuser
	docker-compose exec web python manage.py collectstatic --noinput

# Test commands
test:
	docker-compose exec web python manage.py test

# Database management
migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

# Shell access
shell:
	docker-compose exec web python manage.py shell

dbshell:
	docker-compose exec db psql -U postgres -d pdf_extractor 