FROM python:3.9-slim

WORKDIR /usr/src/app
COPY requirements.txt requirements.txt

# PostgreSQL 클라이언트 라이브러리 설치
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8002

# 프로덕션 환경 설정
ENV ENVIRONMENT=prod
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]