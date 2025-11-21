package main

import (
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
)

func main() {
	log.Println("Tempmail Server MX Server starting...")

	// Get config path from environment or use default
	configPath := os.Getenv("CONFIG_PATH")
	if configPath == "" {
		configPath = "/config/config.yaml"
		// For local development, check if file exists
		if _, err := os.Stat(configPath); os.IsNotExist(err) {
			// Try relative path
			configPath = filepath.Join("..", "config.yaml")
		}
	}

	log.Printf("Loading configuration from: %s", configPath)
	cfg, err := LoadConfig(configPath)
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	log.Printf("Configuration loaded:")
	log.Printf("  Domains: %v", cfg.Domains)
	log.Printf("  MX Port: %d", cfg.Server.MXPort)
	log.Printf("  Hostname: %s", cfg.Server.Hostname)
	log.Printf("  Max message size: %d MB", cfg.Server.MaxMsgSizeMB)
	log.Printf("  Validation - DKIM: %v, SPF: %v, DMARC: %v",
		cfg.Validation.CheckDKIM, cfg.Validation.CheckSPF, cfg.Validation.CheckDMARC)

	// Connect to database
	db, err := NewDB(cfg.Database.URL, cfg.Database.PoolSize)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}
	defer db.Close()
	log.Println("Database connection established")

	// Create SMTP server
	server, err := NewSMTPServer(cfg, db)
	if err != nil {
		log.Fatalf("Failed to create SMTP server: %v", err)
	}

	// Start server in a goroutine
	errChan := make(chan error, 1)
	go func() {
		if err := server.Start(); err != nil {
			errChan <- err
		}
	}()

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	log.Println("Tempmail Server MX Server is ready to receive emails")

	select {
	case err := <-errChan:
		log.Fatalf("Server error: %v", err)
	case sig := <-sigChan:
		log.Printf("Received signal %v, shutting down gracefully...", sig)
		if err := server.Close(); err != nil {
			log.Printf("Error closing server: %v", err)
		}
	}

	log.Println("Tempmail Server MX Server stopped")
}
