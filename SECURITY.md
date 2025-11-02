# Security Policy — WindFlow

## Supported Versions

We provide security updates for the following WindFlow versions:

| Version | Supported          | End of Support |
| ------- | ------------------ | -------------- |
| 1.x.x   | :white_check_mark: | TBD            |
| 0.x.x   | :x:                | 202x-12-31     |

## Reporting Vulnerabilities

We take WindFlow’s security very seriously. If you discover a security vulnerability, please follow the responsible disclosure process below.

### 🚨 Do **not** publicly disclose the vulnerability

### Secure Contact

**Primary email:** `security_at_windflow_dot_org`
**Alternate email:** `stephane_plus_security_at_apiou_dot_org`

Replace *plus*, *at*, and *dot* with the corresponding characters.

### PGP Encryption (Recommended for critical vulnerabilities)

**PGP Key:** [6003730D87EE5599672576C3DFDF4B84BE07B250](https://keys.openpgp.org/vks/v1/by-fingerprint/6003730D87EE5599672576C3DFDF4B84BE07B250)

### Information to Include

When reporting a vulnerability, please provide:

1. **Detailed description** of the vulnerability
2. **Exact reproduction steps**
3. **Potential impact** and exploitation scenarios
4. **Affected components** (backend, frontend, CLI, infrastructure)
5. **WindFlow version** affected
6. **Proof of concept** (if applicable and safe)
7. **Remediation suggestions** (optional)

### Acknowledgment

If you wish, we will publicly credit you for your responsible disclosure (unless you prefer to remain anonymous).

## What to Expect

| Step                   | Timeline    | Description                               |
| ---------------------- | ----------- | ----------------------------------------- |
| **Acknowledgment**     | 48 hours    | Confirmation that we received your report |
| **Initial assessment** | 7 days      | Classification and impact evaluation      |
| **Progress update**    | Weekly      | Information on remediation progress       |
| **Fix developed**      | 30 days     | Development and testing of the fix        |
| **Deployment**         | 72 hours    | Production rollout of the fix             |
| **Public disclosure**  | Max 90 days | Publication after full resolution         |

We are committed to keeping you informed throughout the process.

## Types of Vulnerabilities

### Critical Vulnerabilities (Immediate Fix)

* **Code injection:** SQL, NoSQL, OS command
* **Authentication bypass**
* **Remote Code Execution (RCE)**
* **Privilege escalation:** Unauthorized access to admin resources
* **Container escape:** Docker/Kubernetes
* **Secret exposure:** Leakage of API keys, tokens, passwords

### Important Vulnerabilities (Fix within 7 days)

* **Cross-Site Scripting (XSS):** Stored, Reflected, DOM-based
* **Cross-Site Request Forgery (CSRF)**
* **Server-Side Request Forgery (SSRF)**
* **Path Traversal:** Unauthorized file access
* **Malicious deployment:** Injection of malicious containers

### WindFlow-Specific Vulnerabilities

* **LLM/AI poisoning:** Manipulation of AI models
* **Infrastructure tampering:** Manipulation of infrastructure configurations
* **Secrets exposure:** Deployment secrets leaked via logs or API
* **Privilege escalation:** In target deployment environments

## Deployment Best Practices

When deploying WindFlow, please follow these security best practices:

### 1. Environment Variables

* Never commit `.env` files to version control
* Use strong, unique values for `SECRET_KEY` and other sensitive variables
* Rotate secrets regularly

### 2. Database Security

* Use strong passwords for database access
* Restrict database access to the application server only
* Enable TLS/SSL for database connections

### 3. API Security

* Use HTTPS in production
* Implement rate limiting to prevent abuse
* Keep dependencies up to date to avoid known vulnerabilities
* Configure HashiCorp Vault for secrets management

### 4. Authentication & Authorization

* Enforce strong password policies
* Implement multi-factor authentication (MFA/2FA)
* Set appropriate token expiration times
* Follow the principle of least privilege (RBAC)

### 5. Containers & Infrastructure

* Scan Docker images with tools like Trivy or Grype
* Use minimal, up-to-date base images
* Configure restrictive Kubernetes NetworkPolicies
* Apply appropriate Pod Security Policies
* Limit container resources (CPU, memory)

### 6. Monitoring & Audit

* Enable audit logs for all sensitive actions
* Monitor unauthorized access attempts
* Configure alerts for critical security events
* Store and protect audit logs

## Security Updates

We announce security updates via:

* **Gitea Security Advisories:** Check security issues on your Gitea instance
* **Release notes:** Technical details in each release

### Update Process

1. **Critical patches:** Immediate deployment (24–48h)
2. **Important patches:** Weekly deployment (Tuesdays)
3. **Minor patches:** Monthly deployment (first Tuesday of the month)
4. **Major upgrades:** Planned quarterly

## Bug Bounty Program

### Current Status

As a small volunteer team, we do not currently run a paid bug bounty program.

### Contribution Recognition

We recognize security contributions in several ways:

* **Hall of Fame:** Public list of security contributors
* **Thank-you mentions:** In release notes
* **Badges:** Special recognition on Gitea
* **Collaboration:** Invitation to join the security team

### Future Direction

We are evaluating the possibility of a formal bug bounty program as the project grows.

## Security Resources

### Technical Documentation

* [Secure Architecture](doc/spec/02-architecture.md) — Secure architectural principles
* [Security Specifications](doc/spec/13-security.md) — Detailed technical documentation
* [Authentication](doc/spec/05-authentication.md) — Complete authentication system
* [RBAC Access Control](doc/spec/06-rbac-permissions.md) — Permission management
* [Development Rules](.clinerules/README.md) — Secure coding standards

### Standards & Frameworks

* **OWASP Top 10:** Guide to the most critical web vulnerabilities
* **CIS Benchmarks:** Secure configuration standards
* **NIST Cybersecurity Framework:** Cybersecurity framework
* **Docker Security Best Practices:** Container best practices

## Emergency Contact

### In Case of an Active Security Incident

**Emergency email:** `security_minus_emergency_at_windflow_dot_dev`
**Required subject:** `[URGENT SECURITY] Short description`

We will acknowledge receipt within **1 hour** for security emergencies.

---

**Last updated:** 09/29/2025
**Policy version:** 1.1
**Next review:** 12/29/2025

This policy is a living document that evolves with the project. Suggestions for improvement are welcome via our secure communication channels.

**Thank you for helping keep WindFlow and its users secure!**
