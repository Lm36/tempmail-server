# MX Server

The Tempmail Server MX server is an RFC-compliant SMTP server that receives emails and stores them in the database.

## Overview

- **Language**: Go 1.21+
- **Protocol**: SMTP (RFC 5321)
- **Port**: 25 (configurable)
- **Features**: DKIM, SPF, DMARC validation

## How It Works

1. Receives SMTP connections on port 25
2. Validates recipient addresses against configured domains
3. Accepts email if recipient exists in database
4. Parses MIME content (plain text, HTML, attachments)
5. Validates email authenticity (DKIM, SPF, DMARC)
6. Stores email and attachments in PostgreSQL

## Configuration

Configure in `config.yaml`:

```yaml
server:
  mx_port: 25
  hostname: mail.example.com
  max_message_size_mb: 10

tls:
  enabled: false
  cert_file: /config/certs/cert.pem
  key_file: /config/certs/key.pem

validation:
  check_dkim: true
  check_spf: true
  check_dmarc: true
  store_results: true
```

## Email Validation

The MX server performs authentication checks:

- **DKIM**: Verifies cryptographic signatures
- **SPF**: Checks sender IP authorization
- **DMARC**: Validates domain-based authentication

Results are stored but not enforced (emails are accepted regardless).

## Development

Run locally:

```bash
cd mx
go mod download
go run .
```

Run tests:

```bash
cd mx
go test -v -cover ./...
```

## Security Notes

- Runs on port 25 (requires root/CAP_NET_BIND_SERVICE)
- Only accepts mail for configured domains
- Stores validation results for spam analysis
- No relay support (inbound-only)
