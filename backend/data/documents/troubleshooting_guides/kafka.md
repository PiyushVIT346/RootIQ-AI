# Kafka Consumer Lag Troubleshooting

Symptoms:
- Increasing consumer lag.
- Delayed order status updates.
- Repeated consumer rebalances.
- Transaction timeouts.

Investigation:
1. Check lag by partition.
2. Compare producer and consumer throughput.
3. Inspect processing duration.
4. Check PostgreSQL write latency.
5. Review consumer batch size.

Mitigation:
Reduce batch size if transactions take too long.
Scale consumers only after verifying database capacity.

Recovery:
Consumer lag below 5000 and decreasing.
No repeated rebalances.
Order status delay below 2 minutes.