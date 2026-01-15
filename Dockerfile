FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# Копируем зависимости и ставим их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем сам код
COPY main.py .

# Запускаем
CMD ["python", "main.py"]