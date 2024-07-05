FROM python:3

WORKDIR /eb-estops-docker

EXPOSE 80

COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY . .


CMD ["python", "app.py"]
#["panel", "serve", "app.py", "--address", "0.0.0.0", "--port", "80", "--allow-websocket-origin=*"]
