# Tempmail Server

An inbound-only mail server and REST API for integrating with apps or building temp-mail sites in minutes.

Powering https://mailbucket.cc

## Documentation

- **[API Server](docs/api-server.md)** - REST API overview and quick start
- **[MX Server](docs/mx-server.md)** - SMTP server details
- **[Deployment](docs/deployment.md)** - Production deployment guide
- **[Interactive API Docs](https://lm36.github.io/tempmail-server)** - Full Swagger/OpenAPI documentation (auto-generated)

## Features
- **RFC Compliant MX SMTP server** - Receive mail from any email provider
- **One-command deployment** - Setup script handles everything
- **Custom or random usernames** - Choose your own username or auto-generate
- **Multi-domain support** - Configure and select from multiple domains
- **Token-based API access** - No user authentication needed
- **Auto-expiration** - Addresses and emails deleted after 24h (configurable)
- **Full MIME support** - HTML, plain text, attachments
- **Email validation** - DKIM, SPF, DMARC checking (results stored, not enforced)
- **PostgreSQL storage** - Reliable, concurrent-safe
- **Docker-based** - Simple deployment with Docker Compose

## Quick Start

### Prerequisites

- Domain name with DNS access
- VPS with public IP
- Docker and Docker Compose installed
- Git installed

### Deploy

```bash
# Clone the repository
git clone https://github.com/lm36/tempmail-server.git
cd tempmail-server

# Run the interactive setup script
./setup.sh

# The script will:
# 1. Ask for your domains
# 2. Generate config and DNS records
# 3. Deploy everything with Docker
```

## API Usage

### Generate a temporary email address

```bash
# Random username (8 characters)
curl -X POST http://localhost:8000/api/v1/addresses

# Custom username
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "john.doe"}'

# Custom username with domain selection
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "myemail", "domain": "temp.example.com"}'

# Response:
# {
#   "email": "myemail@temp.example.com",
#   "token": "hbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
#   "expires_at": "2025-11-18T12:00:00Z"
# }
```

The "token" is used for fetching emails for and managing that address

### List available domains

```bash
curl http://localhost:8000/api/v1/domains

# Response:
# {
#   "domains": ["example.com", "temp.example.com"]
# }
```

### List emails for an address

```bash
curl http://localhost:8000/api/v1/{token}/emails

# Response:
# {
#   "emails": [
#     {
#       "id": "uuid",
#       "subject": "Welcome!",
#       "from": "sender@example.com",
#       "received_at": "2025-11-17T10:30:00Z",
#       "is_read": false,
#       "has_attachments": true
#     }
#   ],
#   "total": 1,
#   "page": 1,
#   "per_page": 50
# }
```

### Get email details

```bash
curl http://localhost:8000/api/v1/{token}/emails/{email_id}

# Response includes:
# - Full headers
# - Plain text body
# - HTML body
# - Validation results (DKIM, SPF, DMARC)
# - Attachment list
```
## Configuration

Configuration is managed via `config.yaml`:

```yaml
domains:
  - example.com
  - temp.example.com

database:
  url: postgresql://tempmail:CHANGE_THIS_PASSWORD@postgres:5432/tempmail
  pool_size: 10
  max_overflow: 20

server:
  api_host: 127.0.0.1
  api_port: 8000
  mx_port: 25
  max_message_size_mb: 10
  hostname: mail.example.com
  docs_enabled: true

cors:
  allow_origins:
    - "*"  # In production, specify your frontend domains
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"

tls:
  enabled: false
  cert_file: /config/certs/cert.pem
  key_file: /config/certs/key.pem

tempmail:
  address_lifetime_hours: 24
  max_emails_per_address: 100
  cleanup_interval_hours: 1
  address_format: random
  allow_custom_usernames: true
  min_username_length: 3
  max_username_length: 64
  reserved_usernames:
    - admin
    - postmaster
    - abuse
    - noreply
    - no-reply
    - root
    - webmaster
    - hostmaster
    - mailer-daemon
    - info
    - support
    - security
    - sales
    - contact

validation:
  check_dkim: true
  check_spf: true
  check_dmarc: true
  store_results: true
```

## Development

### Local development

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f api
docker compose logs -f mx

# Stop services
docker compose down
```

### Run tests

```bash
# API tests (Python)
cd api
pytest -v --cov=app tests/

# MX server tests (Go)
cd mx
go test -v -cover ./...
```

## License

[MIT License](LICENSE)
