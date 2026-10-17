#Create python 3.13 base image
FROM python:3.13-slim

# Set the working directory
WORKDIR /streamlit

# Copy files in the directory
COPY * ./

# Install libraries and packages
RUN pip install -r requirements.txt

# Expose port
EXPOSE 8501

#Run streamlit application
CMD ["streamlit", "run", "dashboard.py", "--server.address", "0.0.0.0", "--server.port", "8501"]