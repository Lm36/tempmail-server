package main

import (
	"bytes"
	"fmt"
	"log"
	"net"
	"strings"

	"github.com/emersion/go-msgauth/dkim"
)

// Validator handles email validation (DKIM, SPF, DMARC)
type Validator struct {
	cfg *Config
}

// ValidationResult holds the results of email validation
type ValidationResult struct {
	DKIMValid   *bool  // nullable - true/false if checked, nil if not checked
	SPFResult   string // pass, fail, softfail, neutral, none, temperror, permerror
	DMARCResult string // pass, fail, none
}

// NewValidator creates a new validator
func NewValidator(cfg *Config) *Validator {
	return &Validator{cfg: cfg}
}

// ValidateEmail performs configured validation checks on an email
func (v *Validator) ValidateEmail(rawMessage []byte, from string, clientIP string, heloName string) *ValidationResult {
	result := &ValidationResult{
		SPFResult:   "none",
		DMARCResult: "none",
	}

	// DKIM validation
	if v.cfg.Validation.CheckDKIM {
		dkimValid := v.validateDKIM(rawMessage)
		result.DKIMValid = &dkimValid
	}

	// SPF validation
	if v.cfg.Validation.CheckSPF {
		result.SPFResult = v.validateSPF(clientIP, heloName, from)
	}

	// DMARC validation (requires SPF and DKIM results)
	if v.cfg.Validation.CheckDMARC {
		fromDomain := extractDomain(from)
		result.DMARCResult = v.validateDMARC(fromDomain, result.SPFResult, result.DKIMValid)
	}

	return result
}

// validateDKIM checks DKIM signatures
func (v *Validator) validateDKIM(rawMessage []byte) bool {
	verifications, err := dkim.Verify(bytes.NewReader(rawMessage))
	if err != nil {
		log.Printf("DKIM: No signatures found - %v", err)
		return false
	}

	if len(verifications) == 0 {
		log.Printf("DKIM: No signatures present")
		return false
	}

	// Check if at least one signature is valid
	for i, verification := range verifications {
		if verification.Err == nil {
			log.Printf("DKIM: Signature %d VALID (domain=%s)", i+1, verification.Domain)
			return true
		} else {
			log.Printf("DKIM: Signature %d INVALID - %v", i+1, verification.Err)
		}
	}

	return false
}

// validateSPF performs basic SPF validation
func (v *Validator) validateSPF(clientIP, heloName, from string) string {
	// Extract domain from sender
	domain := extractDomain(from)
	if domain == "" {
		return "none"
	}

	// Parse client IP
	ip := net.ParseIP(clientIP)
	if ip == nil {
		log.Printf("SPF: Invalid client IP: %s", clientIP)
		return "none"
	}

	// Look up SPF record
	spfRecord, err := lookupSPFRecord(domain)
	if err != nil {
		log.Printf("SPF: No record found for %s - %v", domain, err)
		return "none"
	}

	// Basic SPF evaluation
	// For tempmail, we just check if the IP is authorized
	// We don't do full SPF evaluation since it's complex
	result := evaluateBasicSPF(ip, spfRecord, domain)
	log.Printf("SPF: %s (domain=%s, ip=%s)", result, domain, clientIP)

	return result
}

// validateDMARC performs basic DMARC validation
func (v *Validator) validateDMARC(domain string, spfResult string, dkimValid *bool) string {
	if domain == "" {
		return "none"
	}

	// Look up DMARC policy
	dmarcRecord, err := lookupDMARCRecord(domain)
	if err != nil {
		log.Printf("DMARC: No policy found for %s", domain)
		return "none"
	}

	// Basic DMARC evaluation
	// DMARC passes if either SPF or DKIM passes
	spfPass := (spfResult == "pass")
	dkimPass := (dkimValid != nil && *dkimValid)

	var result string
	if spfPass || dkimPass {
		result = "pass"
	} else {
		result = "fail"
	}

	log.Printf("DMARC: %s (policy=%s, spf=%s, dkim=%v)", result, dmarcRecord, spfResult, dkimPass)
	return result
}

// lookupSPFRecord retrieves SPF record from DNS
func lookupSPFRecord(domain string) (string, error) {
	txtRecords, err := net.LookupTXT(domain)
	if err != nil {
		return "", fmt.Errorf("DNS lookup failed: %w", err)
	}

	// Find SPF record (starts with "v=spf1")
	for _, record := range txtRecords {
		if strings.HasPrefix(record, "v=spf1") {
			return record, nil
		}
	}

	return "", fmt.Errorf("no SPF record found")
}

// evaluateBasicSPF performs simplified SPF evaluation
// Full SPF is complex - this is a basic implementation
func evaluateBasicSPF(ip net.IP, spfRecord, domain string) string {
	// Parse SPF mechanisms
	mechanisms := strings.Fields(spfRecord)

	for _, mech := range mechanisms[1:] { // Skip "v=spf1"
		// Check for common mechanisms
		if strings.HasPrefix(mech, "ip4:") || strings.HasPrefix(mech, "ip6:") {
			// IP match
			ipRange := strings.TrimPrefix(mech, "ip4:")
			ipRange = strings.TrimPrefix(ipRange, "ip6:")
			if matchIP(ip, ipRange) {
				return "pass"
			}
		} else if mech == "a" || mech == "+a" {
			// A record match (simplified)
			return "neutral"
		} else if mech == "-all" {
			return "fail"
		} else if mech == "~all" {
			return "softfail"
		} else if mech == "?all" {
			return "neutral"
		}
	}

	return "neutral"
}

// matchIP checks if IP matches range (simplified)
func matchIP(ip net.IP, ipRange string) bool {
	// Simple exact match or CIDR
	if strings.Contains(ipRange, "/") {
		_, network, err := net.ParseCIDR(ipRange)
		if err == nil && network.Contains(ip) {
			return true
		}
	} else {
		testIP := net.ParseIP(ipRange)
		if testIP != nil && testIP.Equal(ip) {
			return true
		}
	}
	return false
}

// lookupDMARCRecord retrieves DMARC policy from DNS
func lookupDMARCRecord(domain string) (string, error) {
	// DMARC records are at _dmarc.<domain>
	dmarcDomain := "_dmarc." + domain

	txtRecords, err := net.LookupTXT(dmarcDomain)
	if err != nil {
		return "", fmt.Errorf("DNS lookup failed: %w", err)
	}

	// Find DMARC record (starts with "v=DMARC1")
	for _, record := range txtRecords {
		if strings.HasPrefix(record, "v=DMARC1") {
			return record, nil
		}
	}

	return "", fmt.Errorf("no DMARC record found")
}

// extractDomain extracts domain from email address
func extractDomain(email string) string {
	// Remove angle brackets
	email = strings.Trim(email, "<>")

	// Split by @
	parts := strings.Split(email, "@")
	if len(parts) == 2 {
		return strings.ToLower(parts[1])
	}

	return ""
}
