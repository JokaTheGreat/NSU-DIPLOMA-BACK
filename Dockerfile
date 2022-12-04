FROM python:latest

RUN mkdir -p /usr/src/app/
WORKDIR /usr/src/app/

COPY . /usr/src/app/

EXPOSE 3333

RUN pip install flask
RUN pip install -U flask-cors
RUN pip install paramiko
CMD ["python3", "main.py"]
