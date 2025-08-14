FROM python:3.11-slim

# Ensure no .pyc and buffered logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (if you ever need gcc, add: build-essential)
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose Flask port
EXPOSE 5000

# Render/Heroku use $PORT; default to 5000 locally
ENV PORT=5000

CMD ["python", "app.py"]
