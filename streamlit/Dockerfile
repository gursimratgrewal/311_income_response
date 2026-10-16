#Create python 3.13 base image
FROM python:3.13-slim

# Set the a working directory
WORKDIR /streamlit

# Copy environment.yml
COPY * ./

# Install libraries and packages
RUN pip install -r requirements.txt

# Expose port
EXPOSE 8501

#Run streamlit application
CMD ["streamlit", "run", "dashboard.py", "--server.address", "0.0.0.0", "--server.port", "8501"]