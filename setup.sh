#!/bin/bash

# Tempmail Server Setup Script
# Interactive deployment wizard

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║                                                       ║"
echo "║        Tempmail Server Setup Wizard                   ║"
echo "║        Production Tempmail Backend                    ║"
echo "║                                                       ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

echo "✓ Docker found"
echo "✓ Docker Compose found"
echo ""

# Check if config.yaml already exists
if [ -f "config.yaml" ]; then
    echo "⚠ config.yaml already exists"
    echo ""
    read -p "Do you want to override the existing configuration? [y/N]: " OVERRIDE_CONFIG
    if [[ ! "$OVERRIDE_CONFIG" =~ ^[Yy]$ ]]; then
        echo "Skipping configuration setup, proceeding to build..."
        echo ""
        # Skip to deployment
        docker compose up -d
        echo ""
        echo "╔═══════════════════════════════════════════════════════╗"
        echo "║                Build Complete!                         ║"
        echo "╚═══════════════════════════════════════════════════════╝"
        echo ""
        echo "Using existing configuration. Services started."
        echo ""
        echo "Useful commands:"
        echo "  - View logs:    docker compose logs -f"
        echo "  - Stop:         docker compose stop"
        echo "  - Restart:      docker compose restart"
        echo "  - Remove all:   docker compose down -v"
        echo ""
        exit 0
    fi
fi

# Configuration
echo "Configuration"
echo "============="
echo ""

# 1. Domains
echo "Enter your domains (comma-separated, e.g., example.com,temp.example.com):"
read -r DOMAINS_INPUT

# Convert to YAML array format
IFS=',' read -ra DOMAINS_ARRAY <<< "$DOMAINS_INPUT"
DOMAINS_YAML=""
for domain in "${DOMAINS_ARRAY[@]}"; do
    # Trim whitespace
    domain=$(echo "$domain" | xargs)
    DOMAINS_YAML+="  - $domain"$'\n'
done

# 2. Server IP (for DNS instructions)
echo ""
echo "Enter your server's public IP address (for DNS setup):"
read -r SERVER_IP

# 3. Database password
echo ""
echo "Generating secure database password..."
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
echo "✓ Generated: ${DB_PASSWORD:0:8}... (will be saved in .env)"

# 4. Address lifetime
echo ""
echo "Address lifetime in hours (default: 24):"
read -r ADDRESS_LIFETIME
ADDRESS_LIFETIME=${ADDRESS_LIFETIME:-24}

# 5. Max message size
echo ""
echo "Maximum message size in MB (default: 10):"
read -r MAX_MSG_SIZE
MAX_MSG_SIZE=${MAX_MSG_SIZE:-10}

# 6. Max emails per address
echo ""
echo "Maximum emails per address (default: 100):"
read -r MAX_EMAILS
MAX_EMAILS=${MAX_EMAILS:-100}

# 7. Server hostname
echo ""
echo "Mail server hostname (e.g., mail.tempmail.com):"
read -r HOSTNAME

# 8. CORS Configuration
echo ""
echo "CORS allowed origins (comma-separated URLs, or * for all):"
echo "Examples: https://yourapp.com,https://www.yourapp.com"
echo "Default: * (allows all origins - NOT recommended for production)"
read -r CORS_ORIGINS_INPUT
CORS_ORIGINS_INPUT=${CORS_ORIGINS_INPUT:-*}

# Convert to YAML array format
if [ "$CORS_ORIGINS_INPUT" = "*" ]; then
    CORS_ORIGINS_YAML="  - \"*\""
else
    IFS=',' read -ra CORS_ORIGINS_ARRAY <<< "$CORS_ORIGINS_INPUT"
    CORS_ORIGINS_YAML=""
    for origin in "${CORS_ORIGINS_ARRAY[@]}"; do
        # Trim whitespace
        origin=$(echo "$origin" | xargs)
        CORS_ORIGINS_YAML+="  - \"$origin\""$'\n'
    done
    # Remove trailing newline
    CORS_ORIGINS_YAML=$(echo "$CORS_ORIGINS_YAML" | sed -e :a -e '/^\n*$/{$d;N;ba' -e '}')
fi

# 9. API Documentation
echo ""
echo "Enable API documentation endpoints? (Swagger/ReDoc)"
read -p "Enable API docs? [y/N]: " DOCS_ENABLED_INPUT
if [[ "$DOCS_ENABLED_INPUT" =~ ^[Yy]$ ]]; then
    DOCS_ENABLED="true"
else
    DOCS_ENABLED="false"
fi

# 10. TLS Configuration
echo ""
echo "TLS/STARTTLS Configuration"
echo "==========================="
echo ""
echo "Do you want to enable TLS/STARTTLS for secure email transmission?"
echo "1) Yes, with Let's Encrypt (automatic, requires public domain)"
echo "2) Yes, with self-signed certificate (for testing/internal use)"
echo "3) No, disable TLS (not recommended for production)"
read -p "Choose option [1-3]: " TLS_CHOICE

TLS_ENABLED="false"
CERT_TYPE="none"

case $TLS_CHOICE in
    1)
        TLS_ENABLED="true"
        CERT_TYPE="letsencrypt"
        echo ""
        echo "Let's Encrypt Configuration"
        echo "----------------------------"
        echo "Enter your email for Let's Encrypt notifications:"
        read -r LETSENCRYPT_EMAIL
        echo ""
        echo "IMPORTANT: Ensure that:"
        echo "  - Port 80 is open and accessible from the internet"
        echo "  - DNS A record for ${HOSTNAME} points to ${SERVER_IP}"
        echo "  - You're running this on the production server"
        echo ""
        ;;
    2)
        TLS_ENABLED="true"
        CERT_TYPE="selfsigned"
        echo ""
        echo "Self-signed certificate will be generated for ${HOSTNAME}"
        echo "⚠ Note: Self-signed certificates will trigger warnings in most email clients"
        echo "   and may be rejected by some mail servers."
        ;;
    3)
        TLS_ENABLED="false"
        CERT_TYPE="none"
        echo ""
        echo "⚠ WARNING: TLS is disabled. Email transmission will be UNENCRYPTED."
        echo "   This is NOT recommended for production use."
        ;;
    *)
        echo "Invalid choice. Defaulting to disabled TLS."
        TLS_ENABLED="false"
        CERT_TYPE="none"
        ;;
esac

# Create config.yaml
echo ""
echo "Creating config.yaml..."

cat > config.yaml <<EOF
# Tempmail Server Configuration
# Generated on $(date)

domains:
$DOMAINS_YAML
database:
  url: postgresql://tempmail:${DB_PASSWORD}@postgres:5432/tempmail?sslmode=disable
  pool_size: 10
  max_overflow: 20

server:
  api_host: 127.0.0.1
  api_port: 8000
  mx_port: 25
  max_message_size_mb: ${MAX_MSG_SIZE}
  hostname: ${HOSTNAME}
  docs_enabled: ${DOCS_ENABLED}

cors:
  allow_origins:
${CORS_ORIGINS_YAML}
  allow_credentials: true
  allow_methods:
    - "*"
  allow_headers:
    - "*"

tls:
  enabled: ${TLS_ENABLED}
  cert_file: /config/certs/cert.pem
  key_file: /config/certs/key.pem

tempmail:
  address_lifetime_hours: ${ADDRESS_LIFETIME}
  max_emails_per_address: ${MAX_EMAILS}
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
EOF

echo "✓ config.yaml created"

# Create .env for docker compose (secrets only)
cat > .env <<EOF
# Database password - generated by setup.sh
DB_PASSWORD=${DB_PASSWORD}
EOF
echo "✓ .env created (contains DB password only)"

# Create certs directory
mkdir -p certs
chmod 755 certs  # Allow Docker container to read the directory

# Generate certificates based on choice
if [ "$CERT_TYPE" = "selfsigned" ]; then
    echo ""
    echo "Generating self-signed certificate..."

    # Generate private key
    openssl genrsa -out certs/key.pem 2048 2>/dev/null

    # Generate self-signed certificate (valid for 365 days)
    openssl req -new -x509 -key certs/key.pem -out certs/cert.pem -days 365 \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=${HOSTNAME}" \
        2>/dev/null

    chmod 644 certs/key.pem  # Docker container needs to read the key
    chmod 644 certs/cert.pem

    echo "✓ Self-signed certificate generated"
    echo "  Certificate: certs/cert.pem"
    echo "  Private key: certs/key.pem"
    echo "  Valid for: 365 days"
    echo ""
    echo "NOTE: Private key is readable (644) to allow Docker container access."
    echo "      Ensure the certs directory is not publicly accessible on the host."

elif [ "$CERT_TYPE" = "letsencrypt" ]; then
    echo ""
    echo "Setting up Let's Encrypt certificate..."

    # Check if certbot is installed
    if ! command -v certbot &> /dev/null; then
        echo "Installing certbot..."
        if command -v apt-get &> /dev/null; then
            sudo apt-get update -qq
            sudo apt-get install -y certbot > /dev/null
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot
        else
            echo "❌ Cannot install certbot automatically."
            echo "   Please install certbot manually and run:"
            echo "   certbot certonly --standalone -d ${HOSTNAME} --email ${LETSENCRYPT_EMAIL} --agree-tos"
            echo ""
            echo "   Then copy the certificates:"
            echo "   sudo cp /etc/letsencrypt/live/${HOSTNAME}/fullchain.pem certs/cert.pem"
            echo "   sudo cp /etc/letsencrypt/live/${HOSTNAME}/privkey.pem certs/key.pem"
            echo "   sudo chown $(whoami):$(whoami) certs/*.pem"
            exit 1
        fi
    fi

    echo "Requesting Let's Encrypt certificate for ${HOSTNAME}..."
    echo "This will use port 80 temporarily for domain validation."
    echo ""
    echo "IMPORTANT: Before continuing, verify that:"
    echo "  - Port 80 is open and accessible from the internet"
    echo "  - DNS A record for ${HOSTNAME} points to ${SERVER_IP}"
    echo "  - You're running this on the production server"
    echo "  - No other service is currently using port 80"
    echo ""
    read -p "Have you confirmed DNS is properly configured? [y/N]: " DNS_CONFIRMED
    if [[ ! "$DNS_CONFIRMED" =~ ^[Yy]$ ]]; then
        echo ""
        echo "❌ Setup cancelled. Please configure DNS and re-run the script."
        echo ""
        echo "To check your DNS configuration, run:"
        echo "  dig ${HOSTNAME} +short"
        echo "  (should return ${SERVER_IP})"
        exit 1
    fi
    echo ""

    # Request certificate
    sudo certbot certonly --standalone \
        -d "${HOSTNAME}" \
        --email "${LETSENCRYPT_EMAIL}" \
        --agree-tos \
        --non-interactive \
        --preferred-challenges http

    if [ $? -eq 0 ]; then
        # Copy certificates to our certs directory
        sudo cp "/etc/letsencrypt/live/${HOSTNAME}/fullchain.pem" certs/cert.pem
        sudo cp "/etc/letsencrypt/live/${HOSTNAME}/privkey.pem" certs/key.pem
        sudo chown $(whoami):$(whoami) certs/*.pem
        chmod 644 certs/key.pem  # Docker container needs to read the key
        chmod 644 certs/cert.pem

        echo "✓ Let's Encrypt certificate obtained successfully"
        echo "  Certificate: certs/cert.pem"
        echo "  Private key: certs/key.pem"
        echo ""
        echo "NOTE: Let's Encrypt certificates expire in 90 days."
        echo "      Set up auto-renewal with: sudo certbot renew --quiet"
        echo "      Consider adding to crontab: 0 0 * * * certbot renew --quiet && cp /etc/letsencrypt/live/${HOSTNAME}/*.pem /path/to/tempmail-server/certs/ && chmod 644 /path/to/tempmail-server/certs/*.pem"
        echo ""
        echo "NOTE: Private key is readable (644) to allow Docker container access."
        echo "      Ensure the certs directory is not publicly accessible on the host."
    else
        echo "❌ Failed to obtain Let's Encrypt certificate."
        echo "   Please check:"
        echo "   - DNS A record for ${HOSTNAME} points to this server"
        echo "   - Port 80 is accessible from the internet"
        echo "   - No other service is using port 80"
        exit 1
    fi
else
    echo ""
    echo "⚠ TLS disabled - no certificates generated"
fi

# Display DNS records
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                 DNS Configuration                      ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "Add these DNS records to your domain(s):"
echo ""

# Start DNS records file
cat > generated_dns.txt <<DNSEOF
Tempmail Server DNS Configuration
Generated on $(date)
Server IP: ${SERVER_IP}
Mail Hostname: ${HOSTNAME}

═══════════════════════════════════════════════════════════

DNSEOF

for domain in "${DOMAINS_ARRAY[@]}"; do
    domain=$(echo "$domain" | xargs)
    echo "For domain: $domain"
    echo "─────────────────────────────────────────────────────"
    echo "MX Record:"
    echo "  ${domain}.  IN  MX  10  ${HOSTNAME}."
    echo ""
    echo "A Record:"
    echo "  ${HOSTNAME}.  IN  A  ${SERVER_IP}"
    echo ""
    
    # Append to DNS records file
    cat >> generated_dns.txt <<DNSEOF
For domain: $domain
─────────────────────────────────────────────────────

MX Record:
  ${domain}.  IN  MX  10  ${HOSTNAME}.

A Record:
  ${HOSTNAME}.  IN  A  ${SERVER_IP}

DNSEOF
done

# Add reverse DNS instructions
cat >> generated_dns.txt <<DNSEOF
═══════════════════════════════════════════════════════════

REVERSE DNS (PTR Record) - IMPORTANT!
─────────────────────────────────────────────────────
Configure reverse DNS for your VPS IP address with your hosting provider.
cd
PTR Record should point:
  ${SERVER_IP}  →  ${HOSTNAME}

═══════════════════════════════════════════════════════════
DNSEOF

echo "REVERSE DNS (PTR Record) - IMPORTANT!"
echo "─────────────────────────────────────────────────────"
echo "Configure reverse DNS for your VPS IP address with your hosting provider."
echo ""
echo "PTR Record should point:"
echo "  ${SERVER_IP}  →  ${HOSTNAME}"
echo ""
echo "Contact your VPS provider (DigitalOcean, AWS, Vultr, etc.) to set this up."
echo ""
echo "═══════════════════════════════════════════════════════"
echo ""
echo "✓ DNS records saved to: generated_dns.txt"
echo ""

# Ask to continue
echo "Press ENTER when DNS is configured (or to continue anyway)..."
read -r

# Deploy with Docker Compose
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                   Deployment                           ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

echo "Starting Tempmail Server services..."
docker compose up -d

echo ""
echo "Waiting for services to be healthy..."
sleep 10

# Check health
echo ""
echo "Checking service health..."

# Check API
if curl -f http://localhost:8000/health &> /dev/null; then
    echo "✓ API is running"
else
    echo "⚠ API health check failed (may still be starting)"
fi

# Check MX
if nc -z localhost 25 &> /dev/null; then
    echo "✓ MX server is running"
else
    echo "⚠ MX server health check failed (may still be starting)"
fi

# Display summary
echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                Setup Complete!                         ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "Tempmail Server is running!"
echo ""
echo "Services:"
echo "  - API:       http://localhost:8000"
echo "  - API Docs:  http://localhost:8000/docs"
echo "  - MX Server: Port 25"
echo ""
echo "Example API usage:"
echo ""
echo "  # Generate a temporary email address"
echo "  curl -X POST http://localhost:8000/api/v1/addresses"
echo ""
echo "  # List emails for an address (use token from above)"
echo "  curl http://localhost:8000/api/v1/{token}/emails"
echo ""
echo "Useful commands:"
echo "  - View logs:    docker compose logs -f"
echo "  - Stop:         docker compose stop"
echo "  - Restart:      docker compose restart"
echo "  - Remove all:   docker compose down -v"
echo ""
echo "Documentation: See README.md and docs/"
echo ""
