FROM python:3.12.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /pruebatecno

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel\
 && pip install --no-cache-dir --default-timeout=300 -r requirements.txt --index-url https://pypi.org/simple

COPY . .

CMD [ "gunicorn", "--chdir", "/pruebatecno", "pruebatecno.wsgi:application", "--bind", "0.0.0.0:8000" ]
