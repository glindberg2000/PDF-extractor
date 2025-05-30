.PHONY: up down build logs test clean

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

test:
	docker-compose exec web python manage.py test

migrate:
	docker-compose exec web python manage.py migrate

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

shell:
	docker-compose exec web python manage.py shell

backup:
	docker-compose exec db pg_dump -U ${DB_USER} -d ${DB_NAME} -Fc --clean > backup_$(shell date +%Y%m%d_%H%M%S).dump

restore:
	docker-compose exec -T db pg_restore -U ${DB_USER} -d ${DB_NAME} --clean --no-owner --no-privileges < $(file)

clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	find . -type d -name "*.egg-info" -exec rm -r {} + 