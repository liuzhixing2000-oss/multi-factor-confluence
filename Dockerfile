FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine.py app.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "app.py", "serve"]
