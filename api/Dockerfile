FROM python:3.13
WORKDIR /app
COPY api_data_fetch.py .
COPY data_types.py .
COPY requirements.txt .
RUN pip install -r requirements.txt
EXPOSE 8000
CMD ["fastapi", "run", "api_data_fetch.py", "--port=8000"]
