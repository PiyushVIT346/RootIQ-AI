# Knowledge Graph Relationships

checkout-api DEPENDS_ON payment-api
checkout-api DEPENDS_ON inventory-service
checkout-api DEPENDS_ON order-service
checkout-api DEPENDS_ON auth-service

payment-api CONNECTS_TO pg-primary-01
order-service CONNECTS_TO pg-primary-01
order-service PUBLISHES_TO kafka-orders
inventory-service USES redis-cache-01
inventory-service CONNECTS_TO pg-primary-01
auth-service ROUTED_THROUGH ingress-gateway

INC-1001 AFFECTED checkout-api
INC-1001 RELATED_TO INC-1002
INC-1001 CAUSED_BY database_connection_exhaustion

INC-1002 AFFECTED payment-api
INC-1002 CAUSED_BY database_connection_exhaustion

INC-1003 AFFECTED auth-service
INC-1003 CAUSED_BY certificate_expiry

INC-1004 AFFECTED order-service
INC-1004 CAUSED_BY kafka_consumer_rebalance

INC-1005 AFFECTED inventory-service
INC-1005 CAUSED_BY cache_stampede

INC-1006 AFFECTED payment-api
INC-1006 CAUSED_BY memory_leak

INC-1007 AFFECTED pg-primary-01
INC-1007 CAUSED_BY database_disk_pressure

INC-1008 AFFECTED ingress-gateway
INC-1008 CAUSED_BY route_configuration_regression