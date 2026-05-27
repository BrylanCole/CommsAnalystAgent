FROM python:3.11-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

ENV HOST=0.0.0.0
ENV PORT=8080
ENV OUTPUT_DIR=/app/outputs

EXPOSE 8080

CMD ["python", "-m", "comms_analyst_agent.web", "--require-auth"]
