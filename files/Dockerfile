FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

WORKDIR /app
COPY files/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY files .

ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "-b", "0.0.0.0:8080", "--timeout", "120", "app:app"]
