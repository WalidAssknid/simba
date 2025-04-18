FROM python:3.13-alpine

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# Install build dependencies for Alpine
RUN apk add --no-cache build-base musl-dev libffi-dev rust cargo

COPY requirements.txt /code/
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . /code/

RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "simba.wsgi:application", "--bind", "0.0.0.0:8000"]
