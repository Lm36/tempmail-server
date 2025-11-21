"""Configuration management using YAML file"""

import os
from typing import List
import yaml


class Config:
    """Application configuration loaded from YAML file"""

    def __init__(self, config_path: str):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Domains
        self.DOMAINS: List[str] = config.get('domains', [])

        # Database
        db_config = config.get('database', {})
        self.DATABASE_URL: str = db_config.get('url', '')
        self.DB_POOL_SIZE: int = db_config.get('pool_size', 10)
        self.DB_MAX_OVERFLOW: int = db_config.get('max_overflow', 20)

        # Server
        server_config = config.get('server', {})
        self.API_HOST: str = server_config.get('api_host', '127.0.0.1')
        self.API_PORT: int = server_config.get('api_port', 8000)
        self.MX_PORT: int = server_config.get('mx_port', 25)
        self.MAX_MESSAGE_SIZE_MB: int = server_config.get('max_message_size_mb', 10)
        self.HOSTNAME: str = server_config.get('hostname', 'mail.tempmail.local')
        self.DOCS_ENABLED: bool = server_config.get('docs_enabled', True)

        # Tempmail settings
        tempmail_config = config.get('tempmail', {})
        self.ADDRESS_LIFETIME_HOURS: int = tempmail_config.get('address_lifetime_hours', 24)
        self.MAX_EMAILS_PER_ADDRESS: int = tempmail_config.get('max_emails_per_address', 100)
        self.CLEANUP_INTERVAL_HOURS: int = tempmail_config.get('cleanup_interval_hours', 1)
        self.ADDRESS_FORMAT: str = tempmail_config.get('address_format', 'random')
        self.ALLOW_CUSTOM_USERNAMES: bool = tempmail_config.get('allow_custom_usernames', True)
        self.MIN_USERNAME_LENGTH: int = tempmail_config.get('min_username_length', 3)
        self.MAX_USERNAME_LENGTH: int = tempmail_config.get('max_username_length', 64)
        self.RESERVED_USERNAMES: List[str] = tempmail_config.get('reserved_usernames', [
            'admin', 'postmaster', 'abuse', 'noreply', 'no-reply',
            'root', 'webmaster', 'hostmaster', 'mailer-daemon',
            'info', 'support', 'security', 'sales', 'contact'
        ])

        # Validation
        validation_config = config.get('validation', {})
        self.CHECK_DKIM: bool = validation_config.get('check_dkim', True)
        self.CHECK_SPF: bool = validation_config.get('check_spf', True)
        self.CHECK_DMARC: bool = validation_config.get('check_dmarc', True)
        self.STORE_VALIDATION_RESULTS: bool = validation_config.get('store_results', True)

        # Logging
        logging_config = config.get('logging', {})
        self.LOG_LEVEL: str = logging_config.get('level', 'info')
        self.LOG_FORMAT: str = logging_config.get('format', 'json')

        # CORS
        cors_config = config.get('cors', {})
        self.CORS_ALLOW_ORIGINS: List[str] = cors_config.get('allow_origins', ['*'])
        self.CORS_ALLOW_CREDENTIALS: bool = cors_config.get('allow_credentials', True)
        self.CORS_ALLOW_METHODS: List[str] = cors_config.get('allow_methods', ['*'])
        self.CORS_ALLOW_HEADERS: List[str] = cors_config.get('allow_headers', ['*'])


def load_config() -> Config:
    """Load configuration from YAML file"""
    # In test mode, return a minimal test configuration
    if os.getenv('TESTING'):
        return create_test_config()

    config_path = os.getenv('CONFIG_PATH', '/config/config.yaml')

    # For local development, try relative path
    if not os.path.exists(config_path):
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config.yaml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    return Config(config_path)


def create_test_config() -> Config:
    """Create a minimal configuration for testing"""
    # Create a mock config object without requiring a file
    config = Config.__new__(Config)

    # Set minimal test values
    config.DOMAINS = ['tempmail.example.com']
    config.DATABASE_URL = 'sqlite:///:memory:'
    config.DB_POOL_SIZE = 5
    config.DB_MAX_OVERFLOW = 10
    config.API_HOST = '127.0.0.1'
    config.API_PORT = 8000
    config.MX_PORT = 25
    config.MAX_MESSAGE_SIZE_MB = 10
    config.HOSTNAME = 'mail.test.local'
    config.DOCS_ENABLED = True
    config.ADDRESS_LIFETIME_HOURS = 24
    config.MAX_EMAILS_PER_ADDRESS = 100
    config.CLEANUP_INTERVAL_HOURS = 1
    config.ADDRESS_FORMAT = 'random'
    config.ALLOW_CUSTOM_USERNAMES = True
    config.MIN_USERNAME_LENGTH = 3
    config.MAX_USERNAME_LENGTH = 64
    config.RESERVED_USERNAMES = [
        'admin', 'postmaster', 'abuse', 'noreply', 'no-reply',
        'root', 'webmaster', 'hostmaster', 'mailer-daemon',
        'info', 'support', 'security', 'sales', 'contact'
    ]
    config.CHECK_DKIM = False
    config.CHECK_SPF = False
    config.CHECK_DMARC = False
    config.STORE_VALIDATION_RESULTS = False
    config.LOG_LEVEL = 'info'
    config.LOG_FORMAT = 'json'
    config.CORS_ALLOW_ORIGINS = ['*']
    config.CORS_ALLOW_CREDENTIALS = True
    config.CORS_ALLOW_METHODS = ['*']
    config.CORS_ALLOW_HEADERS = ['*']

    return config


# Global config instance
settings = load_config()
