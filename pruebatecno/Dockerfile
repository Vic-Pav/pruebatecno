FROM python:3.12.3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /pruebatecno

COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --no-cache-dir --default-timeout=100 -r requirements.txt

COPY . .

CMD [ "gunicorn", "--chdir", "pruebatecno.wsig:application", "--bind", "0.0.0.0:8000" ]
