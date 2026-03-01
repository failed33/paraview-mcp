# =============================================================================
# Stage 1: Build ParaView from source
# This layer is expensive (~30 min) and cached independently. It only
# invalidates when the base image, Qt version, or ParaView version changes.
# =============================================================================
FROM ubuntu:24.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive

ARG PARAVIEW_VERSION=v6.0.1

# Build-time dependencies only (not carried to runtime image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    ninja-build \
    git \
    ca-certificates \
    python3-dev \
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

# =============================================================================
# Stage 2: Runtime SDK image
# Changes here (adding tools, packages) do NOT rebuild ParaView.
# =============================================================================
FROM ubuntu:24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive

# Runtime libraries (Qt6, GL, X11) + dev tools for plugin builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ninja-build \
    python3-dev \
    python3-pip \
    libgl1-mesa-dev \
    libosmesa6 \
    libfontconfig1 \
    libxkbcommon0 \
    libxt6 \
    libxext6 \
    qt6-base-dev \
    qt6-tools-dev \
    libqt6svg6-dev \
    libqt6opengl6-dev \
    git \
    curl \
    gpg \
    lcov \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages cmake==3.31.4

COPY --from=builder /opt/paraview /opt/paraview

ENV PATH="/opt/paraview/bin:${PATH}"
ENV CMAKE_PREFIX_PATH="/opt/paraview/lib/cmake"
ENV LD_LIBRARY_PATH="/opt/paraview/lib"
ENV ParaView_DIR="/opt/paraview/lib/cmake/paraview-6.0"

WORKDIR /workspace
CMD ["/bin/bash"]
