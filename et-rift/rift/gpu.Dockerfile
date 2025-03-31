FROM nvidia/cuda:12.8.1-runtime-rockylinux9

# Disable prompts during package installation
ENV YUM_ARGS="-y"

RUN yum update $YUM_ARGS && yum install $YUM_ARGS \
    wget \
    epel-release \
    openblas \
    git \
    make \
    gcc \
    gcc-c++ \
    gcc-gfortran \
    zlib \
    zlib-devel \
    libjpeg-turbo \
    libjpeg-turbo-devel \
    python3 \
    python3-devel \
    python3-pip \
    which \
    gsl-devel \
    fftw-devel

RUN yum groupinstall -y "Development Tools"

WORKDIR /tmp
RUN wget https://github.com/xianyi/OpenBLAS/archive/refs/tags/v0.3.21.tar.gz
RUN tar -xzvf v0.3.21.tar.gz
WORKDIR /tmp/OpenBLAS-0.3.21
RUN make -j$(nproc) TARGET=HASWELL
RUN make install

WORKDIR /tmp
RUN wget ftp://ftp.gnu.org/gnu/gsl/gsl-2.7.1.tar.gz
RUN tar -xvzf gsl-2.7.1.tar.gz
WORKDIR /tmp/gsl-2.7.1
RUN ./configure --prefix=/usr/local
RUN make -j$(nproc)
RUN make install
RUN echo "/usr/local/lib" > /etc/ld.so.conf.d/gsl.conf
RUN ldconfig
ENV LD_PRELOAD=/usr/local/lib/libgsl.so

RUN ln -s /usr/bin/python3 /usr/bin/python

RUN pip3 install --no-cache-dir \
    numpy \
    lalsuite \
    python-ligo-lw

RUN python -m pip install \
    cupy-cuda12x \
    pygsl_lite \
    pyseobnr \
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
