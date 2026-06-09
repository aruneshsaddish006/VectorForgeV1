FROM python:3.12-slim

WORKDIR /app

# Install system deps required by PyMuPDF and other document libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pip dependencies before copying source
# so this layer is cached on dependency-only changes.
COPY pyproject.toml uv.lock* ./
COPY README.md ./
COPY src/ ./src/
COPY app.py ./

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "app:app", \
     "--host", "0.0.0.0", "--port", "8000"]
