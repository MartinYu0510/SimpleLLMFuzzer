FROM --platform=linux/amd64 ubuntu:24.04
ARG TARGETARCH=x86_64

# 设置非交互模式
ENV DEBIAN_FRONTEND=noninteractive

# 安装依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        bash git sudo jq curl wget \
        build-essential cmake pkg-config clang lld libclang-common-18-dev libclang-rt-18-dev llvm llvm-runtime ninja-build \
        binutils-dev libunwind8-dev autoconf libtool libclang-dev zlib1g-dev \
        libicu-dev libcurl4-openssl-dev libssl-dev ruby-dev libreadline-dev \
        libyaml-dev ca-certificates ansifilter

# 初始化用户
#ARG USER_UID=1001
#ARG USER_GID=1001
#RUN groupadd -g ${USER_GID} myuser && \
#    useradd -u ${USER_UID} -g myuser -m -s /bin/bash myuser

# 初始化 Git 并配置 rbenv
#USER myuser
RUN git config --global user.email "example@example.com" && \
    git config --global user.name "example" && \
    git clone https://github.com/rbenv/rbenv.git ~/.rbenv && \
    cd ~/.rbenv && src/configure && make -C src && \
    echo 'export PATH="$HOME/.rbenv/bin:$PATH"' >> ~/.bashrc && \
    echo 'eval "$(rbenv init -)"' >> ~/.bashrc && \
    . ~/.bashrc && \
    git clone https://github.com/rbenv/ruby-build.git ~/.rbenv/plugins/ruby-build && \
    rbenv install 3.3.6 && \
    rbenv global 3.3.6 && \
    gem install github-linguist

# 添加 ls 文件指示符别名
RUN echo "alias ls='ls -F'" >> ~/.bashrc

# 安装 Miniconda
ENV PATH="/root/miniconda3/bin:${PATH}"
COPY docker/getconda.sh /tmp/getconda.sh
# 安装 Python 包
COPY requirements.txt /tmp/requirements.txt

RUN bash /tmp/getconda.sh ${TARGETARCH} && \
    bash miniconda.sh -b -p /root/miniconda3 && \
    rm -f /tmp/getconda.sh miniconda.sh && \
    echo ". /root/miniconda3/etc/profile.d/conda.sh" >> ~/.bashrc && \
    echo "conda activate python3.10" >> ~/.bashrc && \
    . /root/miniconda3/etc/profile.d/conda.sh && \
    conda init bash && \
    conda create -y -n python3.10 python=3.10 && \
    conda activate python3.10 && \
    pip install --no-cache-dir -r /tmp/requirements.txt && \
    conda clean --all -y

RUN echo "conda activate python3.10" >> ~/.bashrc

# 清理环境变量
ENV DEBIAN_FRONTEND=dialog

COPY tools/binary/external/building_check /usr/local/bin/building_check
COPY tools/file/bin/* /usr/local/bin/

# 如果需要设置代理，请取消注释以下行
# ENV http_proxy="http://172.17.0.1:7890"
# ENV https_proxy="http://172.17.0.1:7890"