# Redis Cache Stampede Troubleshooting

Symptoms:
- Redis hit ratio suddenly decreases.
- PostgreSQL read QPS increases.
- Inventory lookup latency increases.

Investigation:
1. Inspect key expiration patterns.
2. Check TTL distribution.
3. Inspect popular keys.
4. Compare Redis misses with database reads.

Mitigation:
- Warm frequently accessed keys.
- Use request coalescing.
- Apply TTL jitter.
- Use stale-while-revalidate when business rules allow.