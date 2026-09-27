FROM python:3.9-slim

WORKDIR /app

# تنصيب dependencies النظام
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# نسخ requirements الأول (عشان caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي الملفات
COPY . .

# إنشاء مجلد logs
RUN mkdir -p /app/logs

# Expose port
EXPOSE 8080

# متغيرات بيئة
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV LOG_TO_FILE=true
ENV LOG_DIR=/app/logs

# تشغيل
CMD ["python", "main.py"]
