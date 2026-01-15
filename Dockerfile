FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

COPY requirments.txt .
RUN pip install --no-cache-dir -r requirments.txt

RUN playwright install chromium
RUN playwright install-deps

COPY order_parser.py .

CMD ["python", "order_parser.py"]