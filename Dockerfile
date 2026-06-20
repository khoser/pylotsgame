FROM python:3.14-alpine

WORKDIR /app

COPY requirements.txt .

RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./*.py .

CMD ["uvicorn", "game_api:app", "--host", "0.0.0.0", "--port", "8000"]