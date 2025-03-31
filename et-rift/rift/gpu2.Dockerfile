FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

RUN apt-get update -y && \
   apt-get install -y \
           build-essential \
           cmake \
           g++ \
           wget \
           python3.10 \
           python3.10-venv \
           python3-pip \
           curl \
           bc \
           locales \
           git

RUN locale-gen en_US.UTF-8
RUN ln -s /usr/bin/python3.10 /usr/local/bin/python3
RUN ln -s /usr/bin/python3 /usr/local/bin/python

WORKDIR /opt
RUN mkdir installed_RIFT
WORKDIR /opt/installed_RIFT
RUN git clone https://github.com/oshaughn/research-projects-RIT.git
WORKDIR /opt/installed_RIFT/research-projects-RIT
RUN pip3 install --upgrade pip
RUN pip3 install --upgrade setuptools --break-system-packages
RUN pip3 install -e .

RUN apt install libgsl-dev -y
RUN pip3 install pyseobnr

RUN pip3 install asimov>=0.5.6 \
                 asimov-gwdata>=0.4.0 \
       	         cupy-cuda11x \
                 gwdatafind==1.2.0 \
                 gwosc>=0.7.1 \
                 lalsuite>=7.26 \
                 numpy>=1.24.4 \
                 natsort \
                 pybind11>=2.12 \
                 scipy>=1.9.3 \
                 vegas \
                 cython

RUN  CFLAGS='-std=c99' python3 -m pip --no-cache-dir install -U gwsurrogate
RUN python3 -c "import gwsurrogate; gwsurrogate.catalog.pull('NRHybSur3dq8')"
RUN python3 -c "import gwsurrogate; gwsurrogate.catalog.pull('NRSur7dq4')"
RUN python3 -m pip install -U NRSur7dq2

COPY . /rift
WORKDIR /rift
RUN pip3 install --no-cache-dir .

ENV PATH=/rift/MonteCarloMarginalizeCode/Code/bin:$PATH
