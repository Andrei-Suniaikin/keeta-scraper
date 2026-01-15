FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

COPY requirments.txt .
RUN pip install --no-cache-dir -r requirments.txt

COPY order_parser.py .

CMD ["python", "main.py"]