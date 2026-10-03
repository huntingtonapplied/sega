# SEGA Examples

This directory contains comprehensive examples and demonstrations of SEGA platform capabilities. These examples serve both as documentation and as integration tests to ensure platform functionality.

## Directory Structure

```
examples/
 README.md                    # This file
 basic/                       # Simple getting-started examples
 web-app/                     # Web application deployment examples
 ml-pipeline/                 # Machine learning pipeline examples
 firmware-edge/              # Firmware/edge device examples
 hybrid-system/              # Multi-component system examples
 enterprise/                 # Enterprise integration examples
 test-integration/           # Test configurations for examples
```

## Example Categories

### 1. Basic Examples (`basic/`)
- Simple deployment configurations
- Minimal viable project setups
- Core feature demonstrations

### 2. Web Application Examples (`web-app/`)
- React/Node.js applications
- Django/Flask applications
- Container-based deployments
- Blue-green deployment strategies

### 3. ML Pipeline Examples (`ml-pipeline/`)
- TensorFlow/PyTorch models
- Data processing pipelines
- Model deployment and serving
- GPU-accelerated training

### 4. Firmware/Edge Examples (`firmware-edge/`)
- ESP/Arduino projects
- RTOS-based systems
- IoT device deployments
- Over-the-air updates

### 5. Hybrid System Examples (`hybrid-system/`)
- Multi-domain projects
- Web + firmware integration
- FPGA + Software systems
- End-to-end IoT solutions

### 6. Enterprise Examples (`enterprise/`)
- Multi-region deployments
- High-availability configurations
- Security compliance examples
- Large-scale orchestration

## Testing Integration

All examples are automatically tested as part of the CI/CD pipeline:

1. **Configuration Validation**: Ensures all sega.yaml files are valid
2. **Build Testing**: Verifies projects can be built successfully
3. **Deployment Testing**: Tests deployment strategies in sandbox environments
4. **Feature Testing**: Validates specific SEGA features work as documented

## Usage

Each example directory contains:
- `sega.yaml` - Main configuration file
- `README.md` - Specific instructions and explanation
- Application source code (if applicable)
- Test configurations
- Expected outputs/behaviors

To use an example:

```bash
# Copy example to your project
cp -r examples/web-app/simple-express ./my-project
cd my-project

# Initialize and deploy
sega init
sega deploy --target development
```

## Contributing Examples

When adding new examples:

1. Create appropriate directory structure
2. Include comprehensive README.md
3. Add test configurations in `test-integration/`
4. Update this main README.md
5. Ensure example works end-to-end

## Testing Examples Locally

```bash
# Run example validation tests
python scripts/validate_examples.py

# Test specific example
sega test --example web-app/simple-express

# Run all example integration tests
make test-examples
```
