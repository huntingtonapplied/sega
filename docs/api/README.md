# SEGA API Documentation

API specifications for SEGA services.

## REST API

- [api.yaml](api.yaml) - OpenAPI specification

### Base URL
- Production: `https://api.sega.example.com/v1/`
- Staging: `https://api-staging.sega.example.com/v1/`

### Authentication
OAuth 2.0 with JWT Bearer tokens

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/status` | System health and deployment status |
| POST | `/deploy` | Trigger deployment |
| GET | `/projects` | List managed projects |
| POST | `/test` | Execute test suites |
| GET | `/metrics` | Performance metrics |

## gRPC Streaming API

- **Service**: `sega.v1.MetricsService`
- **Port**: 5001
- **Protocol**: gRPC with protobuf serialization

Used for real-time metrics streaming and deployment status updates.

## TCP Protobuf (Telemetry Integration)

- **Port**: 3308
- **Protocol**: TCP with protobuf serialization
- **Purpose**: High-performance metrics collection

## Rate Limiting

- 1000 requests per hour per user
- Burst: 100 requests per minute
