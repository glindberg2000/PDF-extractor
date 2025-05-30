# PDF Extractor Docker Setup

This is a Dockerized version of the PDF Extractor application. The setup includes:
- Django application
- PostgreSQL database
- Redis for caching

## Prerequisites

- Docker
- Docker Compose
- PostgreSQL client tools (for database operations)

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pdf-extractor
   ```

2. **Set up environment variables**
   Create a `.env` file in the root directory with:
   ```
   DEBUG=0
   SECRET_KEY=your-secret-key-here
   DATABASE_URL=postgres://postgres:postgres@db:5432/pdf_extractor
   REDIS_URL=redis://redis:6379/0
   ```

3. **Build and start the containers**
   ```bash
   docker-compose up --build
   ```

4. **Apply migrations**
   ```bash
   docker-compose exec web python manage.py migrate
   ```

5. **Create superuser**
   ```bash
   docker-compose exec web python manage.py createsuperuser
   ```

## Database Operations

### Creating a Backup
```bash
./backup_database.sh
```
This will create a compressed SQL backup in the `database_backups` directory.

### Restoring a Backup
```bash
./restore_database.sh database_backups/backup_YYYYMMDD_HHMMSS.sql.gz
```

## Development

- The application runs on port 8000
- Static files are served from `/staticfiles/`
- Database is accessible on port 5432
- Redis is accessible on port 6379

## Production Considerations

1. Change the `SECRET_KEY` in the `.env` file
2. Set `DEBUG=0` in production
3. Configure proper database credentials
4. Set up proper SSL/TLS
5. Configure proper static file serving

## Troubleshooting

1. **Database connection issues**
   - Check if PostgreSQL container is running
   - Verify database credentials
   - Check network connectivity

2. **Static files not loading**
   - Run `python manage.py collectstatic`
   - Check static file permissions
   - Verify nginx configuration

3. **Redis connection issues**
   - Check if Redis container is running
   - Verify Redis URL configuration
   - Check network connectivity 