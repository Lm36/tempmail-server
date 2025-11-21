# Deployment

Deploy Tempmail Server on any VPS with Docker support.

## Prerequisites

- Domain name with DNS access
- VPS with public IP
- Docker and Docker Compose installed

## Quick Deployment

```bash
git clone https://github.com/lm36/tempmail-server.git
cd tempmail-server
./setup.sh
```

The setup script will:
1. Prompt for your domain(s)
2. Generate configuration
3. Show DNS records to create
4. Deploy with Docker Compose

## DNS Configuration

After running setup.sh, it will output these DNS records for you to register with your doamin:

```
# MX record (required)
@    MX    10    mail.example.com.

# A record for MX hostname (required)
mail    A    YOUR_VPS_IP
```

**Important**: Wait for DNS propagation (5-60 minutes) before testing.

## Manual Setup

If you prefer manual configuration:

### 1. Create .env (secrets only)

```bash
# .env
DB_PASSWORD=your_secure_random_password
```

### 2. Create config.yaml

```yaml
domains:
  - example.com

database:
  url: postgresql://tempmail:your_secure_random_password@postgres:5432/tempmail
  pool_size: 10
  max_overflow: 20

server:
  api_host: 127.0.0.1  # Bind to localhost (use 0.0.0.0 for all interfaces)
  api_port: 8000
  mx_port: 25
  hostname: mail.example.com
  max_message_size_mb: 10
  docs_enabled: true

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

### 3. (Optional) TLS Certificates for MX Server

To enable TLS/STARTTLS for the MX server:

```bash
# Place certificates in ./certs/ directory (on host)
mkdir -p certs
cp your-cert.pem certs/cert.pem
cp your-key.pem certs/key.pem
```

**Path mapping:** The `./certs/` directory on your host is mounted to `/config/certs/` inside the container. So:
- Host: `./certs/cert.pem` → Container: `/config/certs/cert.pem`
- Config file references the *container* path: `/config/certs/cert.pem`

Enable in config.yaml:
```yaml
tls:
  enabled: true
  cert_file: /config/certs/cert.pem  # Path inside container
  key_file: /config/certs/key.pem
```

### 4. Deploy with Docker Compose

```bash
docker compose up -d
```

### 5. Verify deployment

```bash
# Check services
docker compose ps

# Check API health
curl http://localhost:8000/health

# View logs
docker compose logs -f
```

## Port Requirements

- **25**: SMTP (MX server) - binds to 0.0.0.0:25
- **8000**: HTTP API - binds to 127.0.0.1:8000 by default (localhost only)
- **5432**: PostgreSQL - not exposed externally, Docker network only

**Security**: By default, only the MX server (port 25) is exposed publicly. The API is only accessible from localhost. Use a reverse proxy (nginx/Caddy) for HTTPS access to the API.

## Reverse Proxy (Recommended)

The API binds to `127.0.0.1:8000` by default for security. Use nginx/Caddy for HTTPS access:

**To expose API publicly without reverse proxy**: Set `API_BIND=0.0.0.0` in your environment before running docker compose.

### Nginx Example

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Testing Email Reception

```bash
# Generate test address
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/addresses)
EMAIL=$(echo $RESPONSE | jq -r '.email')
TOKEN=$(echo $RESPONSE | jq -r '.token')

echo "Send a test email to: $EMAIL"

# Wait a few seconds, then check
curl "http://localhost:8000/api/v1/$TOKEN/emails" | jq
```

## Production Recommendations

### Security
- Use strong database passwords
- Enable firewall (allow ports 25, 80, 443)
- Restrict API CORS origins
- Consider rate limiting

### Monitoring
- Set up logging aggregation
- Monitor disk space (emails/attachments)
- Alert on MX server downtime
- Track database size growth

### Scaling
- Increase `database.pool_size` for high load
- Run multiple API containers (scale horizontally)
- MX server runs single instance (SMTP is stateless)
- Use managed PostgreSQL for reliability

### Backup
- Regular PostgreSQL dumps
- Backup `config.yaml`
- Consider email retention policy

## Troubleshooting

### Emails not arriving

1. Check DNS records: `dig MX example.com`
2. Test SMTP: `telnet mail.example.com 25`
3. Check MX logs: `docker compose logs mx`
4. Verify address exists: `curl http://localhost:8000/api/v1/addresses`

### API errors

1. Check health: `curl http://localhost:8000/health`
2. View logs: `docker compose logs api`
3. Verify database: `docker compose ps postgres`


## Updating

```bash
git pull
docker compose pull
docker compose up -d
```

## Uninstalling

```bash
docker compose down -v  # -v removes volumes (deletes data)
```
