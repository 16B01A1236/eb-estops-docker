#["panel", "serve", "app.py", "--address", "0.0.0.0", "--port", "80", "--allow-websocket-origin=*"]

# Use the official Python image from the Docker Hub
FROM python:3

# Set the working directory in the container
WORKDIR /eb-estops-docker

# Copy the current directory contents into the container at /app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip3 install -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable


# Run gunicorn server
CMD ["python", "app.py"]
#CMD ["gunicorn", "--bind", ":80", "--timeout", "10000", "app:application"]
