# Application Memory Leak Troubleshooting

Symptoms:
- Memory continuously increases.
- Application instances restart.
- OOM events.
- Heap profiles show retained objects.

Investigation:
1. Compare memory before and after deployment.
2. Inspect recent code changes.
3. Generate and inspect heap profiles.
4. Check global maps and caches.
5. Inspect middleware object lifecycle.

Mitigation:
Rollback a suspected faulty release following approval.
Preserve logs and heap profiles.

Prevention:
Memory soak testing and bounded caches.