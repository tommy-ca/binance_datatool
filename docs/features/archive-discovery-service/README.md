# Archive Discovery Service
# Intelligent Data Discovery Microservice | Version 1.0.0 (MICROSERVICE)
# ================================================================

## 📋 Overview

The Archive Discovery Service is a specialized microservice responsible for intelligent discovery and cataloging of available archive data across multiple cryptocurrency exchanges and data sources. Extracted from Enhanced Archive Collection for better separation of concerns and independent scaling.

**Service Status**: ✅ **MICROSERVICE EXTRACTED**  
**Architecture**: Microservice (Discovery Domain)  
**Version**: 1.0.0 (Initial microservice extraction)

## 🎯 Service Responsibilities

### Core Discovery Capabilities
- **Automated Discovery**: Continuous scanning of exchange archives for new data
- **Data Cataloging**: Structured metadata collection and indexing
- **Source Monitoring**: Real-time monitoring of data source availability
- **Smart Filtering**: Intelligent filtering based on collection criteria
- **Change Detection**: Detecting new archives and data updates

### Service Boundaries
| Responsibility | In Scope | Out of Scope |
|----------------|----------|--------------|
| **Data Discovery** | ✅ Archive scanning, metadata extraction | ❌ Data collection/download |
| **Cataloging** | ✅ Metadata storage, indexing | ❌ Actual data storage |
| **Monitoring** | ✅ Source availability, change detection | ❌ Collection workflow orchestration |
| **APIs** | ✅ Discovery results, catalog queries | ❌ Collection task management |

## 🏗️ Microservice Architecture

### Service Type
- **Pattern**: Domain-Driven Microservice
- **Domain**: Data Discovery and Cataloging
- **Communication**: Event-driven + REST APIs
- **Data**: Read-heavy with periodic writes
- **Scaling**: CPU-bound with network I/O

### Technology Stack
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Runtime** | Python 3.12+ | Discovery logic and web scraping |
| **Framework** | FastAPI | REST API and async operations |
| **Database** | PostgreSQL | Metadata catalog and indexing |
| **Cache** | Redis | Discovery results caching |
| **Messaging** | RabbitMQ | Event publishing to orchestrator |

## 📊 Service Specifications

### 📋 Phase 1: Discovery Specifications (01-specs/)
- **[Service Requirements](./01-specs/functional-requirements.yml)** - Discovery service functional requirements
- **[API Specifications](./01-specs/api-requirements.yml)** - REST and event API definitions
- **[Data Specifications](./01-specs/data-requirements.yml)** - Metadata schema and catalog structure

### 🏗️ Phase 2: Service Design (02-design/)
- **[Service Architecture](./02-design/service-architecture.yml)** - Microservice design and patterns
- **[Data Model](./02-design/data-model.yml)** - Discovery metadata and catalog schemas
- **[API Design](./02-design/api-design.yml)** - REST endpoints and event schemas

## 🎯 Service Performance Targets

### Discovery Performance
| Metric | Target | Measurement |
|--------|--------|-------------|
| **Discovery Latency** | < 30 minutes for new data | Source scanning frequency |
| **Catalog Query Time** | < 100ms for 99th percentile | API response monitoring |
| **Source Coverage** | 100% of configured exchanges | Coverage validation |
| **Change Detection** | < 5 minutes for updates | Event publishing latency |

### Service Reliability
| Metric | Target | Implementation |
|--------|--------|----------------|
| **Service Availability** | 99.5% uptime | Health checks and auto-recovery |
| **Discovery Accuracy** | 99.9% metadata accuracy | Validation and verification |
| **Fault Isolation** | Single source failure tolerance | Circuit breaker patterns |

## 🔗 Service Integration

### Service Dependencies
- **[Infrastructure Platform](../infrastructure-platform/)** - Platform runtime and storage APIs
- **External Data Sources** - Exchange APIs and archive repositories
- **Configuration Service** - Discovery rules and source configurations

### Service Consumers
- **[Archive Collection Orchestrator](../archive-collection-orchestrator/)** - Consumes discovery events
- **[Data Collection Workers](../data-collection-workers/)** - Queries catalog for collection targets
- **Analytics Dashboard** - Queries catalog for data availability insights

### Event Publishing
```yaml
Events Published:
  - archive_discovered: New archive data detected
  - source_unavailable: Data source becomes unavailable  
  - metadata_updated: Archive metadata changes detected
  - discovery_completed: Periodic discovery cycle finished
```

### REST APIs
```yaml
REST Endpoints:
  - GET /catalog/archives: Query discovered archives
  - GET /catalog/sources: List configured data sources
  - GET /discovery/status: Service health and discovery status
  - POST /discovery/trigger: Manual discovery trigger
```

## 🚀 Service Benefits

### Specialized Performance
- **Focused Optimization**: Service optimized specifically for discovery operations
- **Independent Scaling**: Scale discovery capacity independent of collection
- **Specialized Caching**: Discovery-specific caching strategies
- **Domain Expertise**: Deep focus on data source patterns and behaviors

### Operational Excellence
- **Fault Isolation**: Discovery failures don't impact collection operations
- **Independent Deployment**: Deploy discovery improvements without affecting collection
- **Specialized Monitoring**: Discovery-specific metrics and alerting
- **Domain Testing**: Focused testing on discovery scenarios and edge cases

---

**🔍 Intelligent Discovery | 📊 Microservice Architecture | 🎯 Domain-Focused | 🚀 Independent Scaling**

**Extraction Date**: July 24, 2025  
**Service Status**: ✅ Microservice ready for independent development  
**Domain**: Data Discovery and Cataloging