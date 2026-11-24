# TLS Certificate Troubleshooting

Symptoms:
- TLS handshake failure.
- Certificate has expired.
- Authentication failures.

Investigation:
1. Inspect certificate expiration.
2. Verify certificate subject and issuer.
3. Validate full certificate chain.
4. Check gateway replicas.
5. Verify hostname.

Resolution:
Renew certificate through approved certificate authority.
Deploy using staged rollout.
Verify external TLS connectivity.

Prevention:
Automated renewal and expiry alerts.