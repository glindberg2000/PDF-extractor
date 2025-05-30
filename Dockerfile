FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements/base.txt .
RUN pip install -r base.txt

FROM base AS dev
COPY requirements/dev.txt .
RUN pip install -r dev.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS prod
RUN pip install gunicorn
COPY . .
RUN mkdir -p /static
RUN python manage.py collectstatic --noinput --verbosity 0
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "ledgerflow.wsgi:application"] 