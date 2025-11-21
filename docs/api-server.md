# API Server

The Tempmail Server API is a FastAPI-based REST service for managing temporary email addresses and retrieving emails.

## Quick Start

Generate an address and retrieve emails:

```bash
# Generate random temporary email
curl -X POST http://localhost:8000/api/v1/addresses

# Generate with custom username
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "myemail"}'

# Generate with custom username and domain
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "myemail", "domain": "temp.example.com"}'

# List available domains
curl http://localhost:8000/api/v1/domains

# List emails (replace {token} with the token from above)
curl http://localhost:8000/api/v1/{token}/emails

# Get email details
curl http://localhost:8000/api/v1/{token}/emails/{email_id}
```

## Interactive Documentation

Full API documentation with interactive examples:

- **Swagger UI**: https://lm36.github.io/tempmail-server
- **Local**: http://localhost:8000/docs (when running locally)

## Key Features

- **Token-based auth** - No user registration required
- **Custom usernames** - Choose your own email username or use random generation
- **Multi-domain** - Configure and select from multiple domains
- **Auto-expiration** - Addresses expire after 24h (configurable)
- **Username reuse** - Expired usernames become available again
- **Full MIME support** - HTML, plain text, attachments
- **Email validation** - DKIM, SPF, DMARC results stored
- **Search & filter** - Find emails by subject, sender, content

## Creating Addresses

### Random Generation

The simplest way to create a temporary email address:

```bash
curl -X POST http://localhost:8000/api/v1/addresses
```

Returns a random 8-character username like `a8f3k9x2@tempmail.com`.

### Custom Username

Specify your own username (3-64 characters, alphanumeric + `.` `_` `-`):

```bash
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "john.doe"}'
```

Returns: `john.doe@tempmail.com`

**Username Rules:**
- Length: 3-64 characters
- Allowed characters: letters, numbers, `.` `_` `-`
- Reserved names blocked: `admin`, `postmaster`, `abuse`, etc.
- Case insensitive (converted to lowercase)
- Must be unique among active addresses

### Domain Selection

Choose from available domains (list with `GET /api/v1/domains`):

```bash
# With custom username and domain
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"username": "myemail", "domain": "mail.example.org"}'

# Random username with specific domain
curl -X POST http://localhost:8000/api/v1/addresses \
  -H "Content-Type: application/json" \
  -d '{"domain": "mail.example.org"}'
```

### Expired Username Reuse

When an address expires, its username becomes available:

1. Address `john@example.com` expires after 24h
2. Username `john` can be claimed again
3. New token and clean inbox for the new owner

## Configuration

Configure in `config.yaml`:

```yaml
server:
  api_host: 127.0.0.1
  api_port: 8000
  docs_enabled: true

cors:
  allow_origins:
    - "*"  # In production, specify your frontend domains
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"

tempmail:
  address_lifetime_hours: 24
  max_emails_per_address: 100
  cleanup_interval_hours: 1

  # Custom username settings
  allow_custom_usernames: true
  min_username_length: 3
  max_username_length: 64
  reserved_usernames:
    - admin
    - postmaster
    - abuse
    # ... more reserved names
```

### CORS Configuration

Configure which origins can access your API to prevent unauthorized cross-origin requests.

**Development (allow all):**
```yaml
cors:
  allow_origins:
    - "*"
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"
```

**Production (specific domains):**
```yaml
cors:
  allow_origins:
    - "https://yourapp.com"
    - "https://www.yourapp.com"
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"
```

**Multiple frontends:**
```yaml
cors:
  allow_origins:
    - "https://app.example.com"
    - "https://admin.example.com"
    - "http://localhost:3000"  # For local development
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"
```

**Security Note:** Using `"*"` for `allow_origins` permits any website to make requests to your API. For production deployments, always specify the exact domains of your frontend applications.

## Development

Run locally:

```bash
cd api
pip install -r requirements.txt
python -m app.main
```

Run tests:

```bash
cd api
pytest -v --cov=app tests/
```
