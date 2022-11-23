FROM python:latest

RUN mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

COPY . /usr/src/app/

EXPOSE 8080

RUN pip install flask
RUN pip install -U flask-cors
CMD ["python3", "main.py"]
