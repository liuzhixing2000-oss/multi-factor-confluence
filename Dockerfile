FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY engine.py app.py research.py pullback.py research_pullback.py mtf_strategy.py research_mtf.py ./
ENV PYTHONUNBUFFERED=1
CMD ["python", "research_pullback.py"]
