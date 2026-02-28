# Stage 1: Build dependencies
FROM ubuntu:24.04 AS base
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    wget \
    ca-certificates \
    python3-dev \
    python3-pip \
    libgl1-mesa-dev \
    libosmesa6-dev \
    libglvnd-dev \
    libfontconfig1-dev \
    libx11-dev \
    libxext-dev \
    libxt-dev \
    libxkbcommon-dev \
    libxcb-xkb-dev \
    qt6-base-dev \
    qt6-tools-dev \
    qt6-tools-dev-tools \
    libqt6svg6-dev \
    libqt6opengl6-dev \
    && rm -rf /var/lib/apt/lists/*

# Stage 2: Build ParaView from source
FROM base AS builder

ARG PARAVIEW_VERSION=v6.0.1
WORKDIR /src

RUN git clone --recursive --branch ${PARAVIEW_VERSION} --depth 1 \
    https://gitlab.kitware.com/paraview/paraview.git

WORKDIR /build/paraview
RUN cmake -S /src/paraview -B . \
    -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/opt/paraview \
    -DBUILD_SHARED_LIBS=ON \
    -DBUILD_TESTING=OFF \
    -DPARAVIEW_BUILD_QT_GUI=ON \
    -DPARAVIEW_USE_QT=ON \
    -DPARAVIEW_ENABLE_PYTHON=ON \
    -DPARAVIEW_USE_MPI=OFF \
    -DPARAVIEW_ENABLE_WEB=OFF \
    -DPARAVIEW_ENABLE_EXAMPLES=OFF \
    -DVTK_WRAP_PYTHON=ON \
    && cmake --build . --parallel $(nproc) \
    && cmake --install .

# Stage 3: Runtime SDK image
FROM ubuntu:24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    ninja-build \
    build-essential \
    python3-dev \
    libgl1-mesa-dev \
    libosmesa6 \
    libfontconfig1 \
    libxkbcommon0 \
    libxt6 \
    libxext6 \
    python3-pip \
    qt6-base-dev \
    qt6-tools-dev \
    libqt6svg6-dev \
    libqt6opengl6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/paraview /opt/paraview

ENV PATH="/opt/paraview/bin:${PATH}"
ENV CMAKE_PREFIX_PATH="/opt/paraview/lib/cmake"
ENV LD_LIBRARY_PATH="/opt/paraview/lib"
ENV ParaView_DIR="/opt/paraview/lib/cmake/paraview-6.0"

WORKDIR /workspace
CMD ["/bin/bash"]
