FROM ubuntu:latest

# to avoid user prompts when installing tzdata
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && apt install -y \
    git \
    make \
    build-essential \
    python3 \
    python3-pip
RUN ln -s /usr/bin/python3 /usr/bin/python
RUN pip install --break-system-packages \
    numpy \
    lalsuite \
    python-ligo-lw

COPY . /rift
WORKDIR /rift
RUN pip install --break-system-packages .

ENV PATH=/rift/MonteCarloMarginalizeCode/Code/bin:$PATH
