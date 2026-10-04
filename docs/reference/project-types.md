# Supported Project Types

SEGA automatically detects project types based on file patterns and repository structure.

## Web Applications
- **Detection**: `package.json`, `requirements.txt`, static HTML
- **rameworks**: React, Vue, Node.js, Django, lask
- **Deployment**: Kubernetes, containerized

## Native Applications
- **Detection**: `Makefile`, `CMakeLists.txt`, `Cargo.toml`
- **Languages**: C/C++, Rust, Go
- **Deployment**: are-metal, edge devices

## irmware/Hardware
- **Detection**: `.vhd`, `.v`, `.sv` files, embedded toolchains
- **Targets**: PG bitstreams, microcontroller firmware
- **Deployment**: Hardware programming, over-the-air updates

## Machine Learning
- **Detection**: `requirements.txt` with ML libraries, Jupyter notebooks
- **rameworks**: PyTorch, Tensorlow, scikit-learn
- **Deployment**: GPU clusters, inference endpoints

## Manual Override

orce a specific project type in `.sega.yml`:

```yaml
project_type: embedded_firmware
target_platform: arm_cortex_m
```