# PostgreSQL Connection Exhaustion Troubleshooting

Symptoms:
- Too many clients already.
- Connection acquisition timeout.
- High database active sessions.
- Increased payment API latency.

Investigation:
1. Check PostgreSQL active connections.
2. Group sessions by application name.
3. Inspect application connection pool usage.
4. Check retry attempts and worker concurrency.
5. Review recent deployments.

Mitigation:
1. Notify Database Operations.
2. Reduce excessive retries.
3. Apply exponential backoff with jitter.
4. Reduce application concurrency if required.
5. Monitor database connection count.

Never terminate all database sessions blindly.
Do not increase max_connections without capacity review.

Recovery:
- Active connections return below service budget.
- Payment API p95 latency below 400ms.
- Checkout 5xx rate below 1%.