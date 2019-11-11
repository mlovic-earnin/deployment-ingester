FROM ubuntu:16.04

RUN apt-get update -y && \
    apt-get install -y \
      python3 \
      python3-pip \
      libpq-dev

RUN pip3 install --upgrade pip

ENV PYTHONIOENCODING=utf-8

WORKDIR /app

COPY ./requirements.txt .

ARG NEXUS_USER
ARG NEXUS_PASSWORD
RUN pip3 install -r /app/requirements.txt --extra-index-url http://$NEXUS_USER:$NEXUS_PASSWORD@artifacts.k8s.us-west-2.dev.earnin.com/repository/debug-pypi/simple --trusted-host artifacts.k8s.us-west-2.dev.earnin.com

COPY ./main.py .

CMD [ "python3", "main.py" ]
