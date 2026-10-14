FROM python:3.13-slim

WORKDIR /API_SERVER

COPY * ./
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["fastapi", "run", "process_sf311.py", "--port=8000", "--host=0.0.0.0"]