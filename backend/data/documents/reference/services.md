# Enterprise Service Catalog

checkout-api:
Owner: Commerce Platform
Dependencies: payment-api, inventory-service, order-service, auth-service
Criticality: Tier 1

payment-api:
Owner: Payments Team
Dependencies: pg-primary-01
Criticality: Tier 1

order-service:
Owner: Commerce Platform
Dependencies: kafka-orders, pg-primary-01

inventory-service:
Owner: Supply Systems
Dependencies: redis-cache-01, pg-primary-01

auth-service:
Owner: Identity Team
Dependencies: ingress-gateway

Infrastructure:
pg-primary-01: PostgreSQL primary database
redis-cache-01: Redis cache
kafka-orders: Kafka order event cluster
ingress-gateway: API routing and TLS termination