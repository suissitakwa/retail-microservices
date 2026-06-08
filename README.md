# Retail Microservices

[![CI](https://github.com/suissitakwa/retail-microservices/actions/workflows/build.yml/badge.svg)](https://github.com/suissitakwa/retail-microservices/actions/workflows/build.yml)

Spring Boot 4 / Java 21 microservices layer for the retail platform. These services run alongside (and progressively replace) the Spring Boot monolith at `../retail/`.

## Services

| Service | Port | DB Port | Status |
|---|---|---|---|
| config-server | 8888 | — | Infrastructure |
| discovery (Eureka) | 8761 | — | Infrastructure |
| customer-service | 8083 | 5435 | Auth + profiles — only JWT issuer |
| payment-service | 8082 | 5434 | Payment lifecycle + Kafka |
| product-service | 8084 | 5436 | Products, categories, inventory (Redis cached) |
| order-service | 8085 | 5437 | Cart, orders, Stripe checkout |
| notification-service | 8086 | 5438 | Kafka consumers, notification REST API |
| copilot-service | 8087 | — | OpenAI GPT-4o-mini assistant |

## Quick Start

### Prerequisites

- Java 21
- Docker + Docker Compose
- `.env` file in this directory (see below)

### Environment

Create `.env` in the repo root (never commit this):

```env
JWT_SECRET_KEY=...
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
OPENAI_API_KEY=...
APP_FRONTEND_BASE_URL=http://localhost:3000
```

### Run everything

```bash
docker-compose up
```

### Run infrastructure only (then start services with mvnw)

```bash
docker-compose up -d zookeeper kafka redis customer-db payment-db product-db order-db notification-db
```

Then start each service in order:

```bash
cd services/config-server    && ./mvnw spring-boot:run   # start first
cd services/discovery        && ./mvnw spring-boot:run   # start second
# then any order:
cd services/customer-service && ./mvnw spring-boot:run
cd services/product-service  && ./mvnw spring-boot:run
cd services/order-service    && ./mvnw spring-boot:run
cd services/notification-service && ./mvnw spring-boot:run
cd services/copilot-service  && ./mvnw spring-boot:run
```

## Architecture

```mermaid
graph TB
    UI([React UI :3000])
    MON([retail monolith :8080])

    subgraph infra["⚙️ Infrastructure"]
        CFG[config-server :8888\nnative profile · serves configurations/]
        EUR[discovery / Eureka :8761\nservice registry]
    end

    subgraph svc["🔧 Business Services"]
        CUST[customer-service :8083\n🔑 only JWT issuer]
        PAY[payment-service :8082\npayment-db :5434]
        PROD[product-service :8084\nproduct-db :5436]
        ORD[order-service :8085\norder-db :5437]
        NOTIF[notification-service :8086\nnotification-db :5438]
        COP[copilot-service :8087\nno DB]
    end

    subgraph ext["☁️ External"]
        STRIPE[(Stripe)]
        OPENAI[(OpenAI GPT-4o-mini)]
        REDIS[(Redis cache)]
    end

    subgraph kafka["📨 Kafka"]
        OC[[order.created]]
        PP[[payment.processed]]
    end

    %% Config distribution
    CFG -.->|config at startup| CUST & PAY & PROD & ORD & NOTIF & COP

    %% Service registration
    CUST & PAY & PROD & ORD & NOTIF & COP -.->|register| EUR

    %% Client → service
    UI -->|JWT auth| CUST
    UI -->|browse / cart / orders| ORD
    UI -->|products| PROD
    UI -->|notifications| NOTIF
    UI -->|chat| COP

    %% Inter-service (sync)
    ORD -->|RestClient: product name + price| PROD
    COP -->|RestClient: order facts| ORD
    MON -->|internal: payment lifecycle| PAY

    %% Kafka publish
    ORD -->|publishes| OC
    PAY -->|publishes| PP

    %% Kafka consume
    OC -->|ORDER_PLACED notification| NOTIF
    OC -->|decrement inventory| MON
    PP -->|PAYMENT_PAID notification| NOTIF
    PP -->|mark payment PAID| MON

    %% External
    ORD -->|checkout session| STRIPE
    PAY -->|webhook: payment_intent.succeeded| STRIPE
    COP --> OPENAI
    PROD --> REDIS
```

### Tech Stack

- **Spring Boot 4.0.2** / **Java 21** / **Spring Cloud 2025.1.x**
- **Eureka** (service discovery) — all services register on startup
- **Config Server** (native profile) — serves `configurations/<service>.yml` to each service
- **Kafka** — async events between services
- **Redis** — product caching in product-service
- **RestClient** (Spring 6) — synchronous inter-service HTTP; no Feign

### JWT

`customer-service` is the **only** service that issues JWTs. All other services validate the token stateless (no DB call) — the role is embedded in the token claims as `[{authority: "ROLE_CUSTOMER"}]`.

### Kafka Event Flow

```
Order checkout
  → order-service publishes order.created
      → notification-service: saves ORDER_PLACED notification
      → retail monolith: decrements inventory

Stripe webhook (payment_intent.succeeded)
  → payment-service publishes payment.processed
      → notification-service: saves PAYMENT_PAID notification
      → retail monolith: marks payment PAID
```

### Service Ports Reference

| Service | Swagger UI |
|---|---|
| customer-service | http://localhost:8083/swagger-ui.html |
| product-service | http://localhost:8084/swagger-ui.html |
| order-service | http://localhost:8085/swagger-ui.html |
| notification-service | http://localhost:8086/swagger-ui.html |
| Eureka dashboard | http://localhost:8761 |
| Config server health | http://localhost:8888/actuator/health |
