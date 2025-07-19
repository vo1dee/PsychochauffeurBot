#!/usr/bin/env python3
"""
Security Audit and Penetration Testing Script

This script conducts comprehensive security testing including:
- Input validation and injection attack prevention
- Authentication and authorization mechanism validation
- Rate limiting and abuse prevention testing
- Secure handling of sensitive data and API keys
- Code vulnerability scanning
"""

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import hashlib
import secrets
import base64

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SecurityFinding:
    """Security finding data structure."""
    severity: str  # critical, high, medium, low, info
    category: str
    title: str
    description: str
    file_path: Optional[str]
    line_number: Optional[int]
    code_snippet: Optional[str]
    recommendation: str
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None


@dataclass
class SecurityAuditResult:
    """Security audit result data structure."""
    test_name: str
    findings: List[SecurityFinding]
    passed_checks: int
    failed_checks: int
    total_checks: int
    timestamp: datetime


class SecurityAuditor:
    """Comprehensive security auditing system."""
    
    def __init__(self):
        self.results: List[SecurityAuditResult] = []
        self.findings: List[SecurityFinding] = []
        
        # Security patterns to detect
        self.vulnerability_patterns = {
            'sql_injection': [
                r'execute\s*\(\s*["\'].*%.*["\']',
                r'query\s*\(\s*["\'].*\+.*["\']',
                r'cursor\.execute\s*\(\s*["\'].*%.*["\']'
            ],
            'command_injection': [
                r'os\.system\s*\(',
                r'subprocess\.call\s*\(',
                r'subprocess\.run\s*\(',
                r'eval\s*\(',
                r'exec\s*\('
            ],
            'hardcoded_secrets': [
                r'password\s*=\s*["\'][^"\']{8,}["\']',
                r'api_key\s*=\s*["\'][^"\']{20,}["\']',
                r'secret\s*=\s*["\'][^"\']{16,}["\']',
                r'token\s*=\s*["\'][^"\']{20,}["\']'
            ],
            'weak_crypto': [
                r'md5\s*\(',
                r'sha1\s*\(',
                r'random\.random\s*\(',
                r'random\.randint\s*\('
            ],
            'path_traversal': [
                r'open\s*\(\s*.*\+.*\)',
                r'file\s*\(\s*.*\+.*\)',
                r'\.\./',
                r'\.\.\\\\'
            ],
            'unsafe_deserialization': [
                r'pickle\.loads\s*\(',
                r'pickle\.load\s*\(',
                r'yaml\.load\s*\(',
                r'eval\s*\('
            ]
        }
        
        # Sensitive file patterns
        self.sensitive_files = [
            r'\.env',
            r'config\.py',
            r'settings\.py',
            r'secrets\.py',
            r'\.key',
            r'\.pem',
            r'\.p12'
        ]
    
    def scan_file_for_vulnerabilities(self, file_path: str) -> List[SecurityFinding]:
        """Scan a single file for security vulnerabilities."""
        findings = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check for vulnerability patterns
            for vuln_type, patterns in self.vulnerability_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    for match in matches:
                        line_num = content[:match.start()].count('\n') + 1
                        line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                        
                        severity = self._get_vulnerability_severity(vuln_type)
                        
                        finding = SecurityFinding(
                            severity=severity,
                            category=vuln_type,
                            title=f"Potential {vuln_type.replace('_', ' ').title()}",
                            description=f"Detected potential {vuln_type.replace('_', ' ')} vulnerability",
                            file_path=file_path,
                            line_number=line_num,
                            code_snippet=line_content.strip(),
                            recommendation=self._get_vulnerability_recommendation(vuln_type),
                            cwe_id=self._get_cwe_id(vuln_type)
                        )
                        findings.append(finding)
            
            # Check for hardcoded credentials
            findings.extend(self._check_hardcoded_credentials(file_path, content, lines))
            
            # Check for insecure configurations
            findings.extend(self._check_insecure_configurations(file_path, content, lines))
            
        except Exception as e:
            logger.warning(f"Could not scan {file_path}: {e}")
        
        return findings
    
    def _get_vulnerability_severity(self, vuln_type: str) -> str:
        """Get severity level for vulnerability type."""
        severity_map = {
            'sql_injection': 'critical',
            'command_injection': 'critical',
            'hardcoded_secrets': 'high',
            'weak_crypto': 'medium',
            'path_traversal': 'high',
            'unsafe_deserialization': 'high'
        }
        return severity_map.get(vuln_type, 'medium')
    
    def _get_vulnerability_recommendation(self, vuln_type: str) -> str:
        """Get recommendation for vulnerability type."""
        recommendations = {
            'sql_injection': 'Use parameterized queries or ORM methods to prevent SQL injection',
            'command_injection': 'Avoid executing system commands with user input. Use subprocess with shell=False',
            'hardcoded_secrets': 'Move secrets to environment variables or secure configuration files',
            'weak_crypto': 'Use cryptographically secure random generators and strong hash functions',
            'path_traversal': 'Validate and sanitize file paths. Use os.path.join() for path construction',
            'unsafe_deserialization': 'Avoid deserializing untrusted data. Use safe serialization formats like JSON'
        }
        return recommendations.get(vuln_type, 'Review and fix the identified security issue')
    
    def _get_cwe_id(self, vuln_type: str) -> Optional[str]:
        """Get CWE ID for vulnerability type."""
        cwe_map = {
            'sql_injection': 'CWE-89',
            'command_injection': 'CWE-78',
            'hardcoded_secrets': 'CWE-798',
            'weak_crypto': 'CWE-327',
            'path_traversal': 'CWE-22',
            'unsafe_deserialization': 'CWE-502'
        }
        return cwe_map.get(vuln_type)
    
    def _check_hardcoded_credentials(self, file_path: str, content: str, lines: List[str]) -> List[SecurityFinding]:
        """Check for hardcoded credentials and secrets."""
        findings = []
        
        # Patterns for different types of secrets
        secret_patterns = {
            'api_key': r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']([a-zA-Z0-9]{20,})["\']',
            'password': r'(?i)(password|passwd|pwd)\s*[=:]\s*["\']([^"\']{8,})["\']',
            'token': r'(?i)(token|auth[_-]?token)\s*[=:]\s*["\']([a-zA-Z0-9]{20,})["\']',
            'secret': r'(?i)(secret|secret[_-]?key)\s*[=:]\s*["\']([a-zA-Z0-9]{16,})["\']',
            'private_key': r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'
        }
        
        for secret_type, pattern in secret_patterns.items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                
                # Skip if it's clearly a placeholder or example
                if any(placeholder in match.group().lower() for placeholder in 
                       ['example', 'placeholder', 'your_', 'insert_', 'replace_', 'xxx', '***']):
                    continue
                
                finding = SecurityFinding(
                    severity='high',
                    category='hardcoded_credentials',
                    title=f"Hardcoded {secret_type.replace('_', ' ').title()}",
                    description=f"Potential hardcoded {secret_type.replace('_', ' ')} found in source code",
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=line_content.strip(),
                    recommendation="Move sensitive data to environment variables or secure configuration",
                    cwe_id='CWE-798'
                )
                findings.append(finding)
        
        return findings
    
    def _check_insecure_configurations(self, file_path: str, content: str, lines: List[str]) -> List[SecurityFinding]:
        """Check for insecure configuration patterns."""
        findings = []
        
        insecure_patterns = {
            'debug_enabled': r'(?i)debug\s*[=:]\s*true',
            'ssl_disabled': r'(?i)(ssl[_-]?verify|verify[_-]?ssl)\s*[=:]\s*false',
            'weak_cipher': r'(?i)(cipher|encryption)\s*[=:]\s*["\']?(des|rc4|md5)["\']?',
            'permissive_cors': r'(?i)cors.*\*',
            'insecure_cookie': r'(?i)(secure|httponly)\s*[=:]\s*false'
        }
        
        for config_type, pattern in insecure_patterns.items():
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                
                finding = SecurityFinding(
                    severity='medium',
                    category='insecure_configuration',
                    title=f"Insecure Configuration: {config_type.replace('_', ' ').title()}",
                    description=f"Potentially insecure configuration detected: {config_type}",
                    file_path=file_path,
                    line_number=line_num,
                    code_snippet=line_content.strip(),
                    recommendation=self._get_config_recommendation(config_type)
                )
                findings.append(finding)
        
        return findings
    
    def _get_config_recommendation(self, config_type: str) -> str:
        """Get recommendation for insecure configuration."""
        recommendations = {
            'debug_enabled': 'Disable debug mode in production environments',
            'ssl_disabled': 'Enable SSL/TLS verification for all external connections',
            'weak_cipher': 'Use strong encryption algorithms (AES-256, RSA-2048+)',
            'permissive_cors': 'Configure CORS with specific allowed origins',
            'insecure_cookie': 'Enable secure and httponly flags for cookies'
        }
        return recommendations.get(config_type, 'Review and secure the configuration')
    
    async def test_input_validation(self) -> SecurityAuditResult:
        """Test input validation and injection prevention."""
        logger.info("Testing input validation and injection prevention...")
        
        test_name = "input_validation"
        findings = []
        passed_checks = 0
        failed_checks = 0
        
        # Test payloads for various injection attacks
        test_payloads = {
            'sql_injection': [
                "'; DROP TABLE users; --",
                "' OR '1'='1",
                "1' UNION SELECT * FROM users--",
                "'; INSERT INTO users VALUES ('hacker', 'password'); --"
            ],
            'command_injection': [
                "; ls -la",
                "| cat /etc/passwd",
                "&& rm -rf /",
                "`whoami`"
            ],
            'xss': [
                "<script>alert('XSS')</script>",
                "javascript:alert('XSS')",
                "<img src=x onerror=alert('XSS')>",
                "';alert('XSS');//"
            ],
            'path_traversal': [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "....//....//....//etc/passwd",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
            ]
        }
        
        # Scan code for input validation patterns
        python_files = self._get_python_files()
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for input validation patterns
                validation_patterns = [
                    r'validate\s*\(',
                    r'sanitize\s*\(',
                    r'escape\s*\(',
                    r'clean\s*\(',
                    r're\.match\s*\(',
                    r're\.search\s*\(',
                    r'isinstance\s*\(',
                    r'len\s*\('
                ]
                
                has_validation = any(re.search(pattern, content, re.IGNORECASE) 
                                   for pattern in validation_patterns)
                
                # Check for direct user input usage
                dangerous_patterns = [
                    r'request\.args\[',
                    r'request\.form\[',
                    r'input\s*\(',
                    r'sys\.argv\[',
                    r'os\.environ\['
                ]
                
                has_direct_input = any(re.search(pattern, content, re.IGNORECASE) 
                                     for pattern in dangerous_patterns)
                
                if has_direct_input and not has_validation:
                    finding = SecurityFinding(
                        severity='high',
                        category='input_validation',
                        title='Missing Input Validation',
                        description=f'File {file_path} processes user input without validation',
                        file_path=file_path,
                        line_number=None,
                        code_snippet=None,
                        recommendation='Implement input validation and sanitization for all user inputs'
                    )
                    findings.append(finding)
                    failed_checks += 1
                else:
                    passed_checks += 1
                    
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        total_checks = passed_checks + failed_checks
        
        result = SecurityAuditResult(
            test_name=test_name,
            findings=findings,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            total_checks=total_checks,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Input validation test completed: {passed_checks}/{total_checks} checks passed")
        return result
    
    async def test_authentication_authorization(self) -> SecurityAuditResult:
        """Test authentication and authorization mechanisms."""
        logger.info("Testing authentication and authorization mechanisms...")
        
        test_name = "auth_mechanisms"
        findings = []
        passed_checks = 0
        failed_checks = 0
        
        # Check for authentication patterns in code
        python_files = self._get_python_files()
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for authentication mechanisms
                auth_patterns = [
                    r'@login_required',
                    r'@requires_auth',
                    r'authenticate\s*\(',
                    r'check_permission\s*\(',
                    r'is_admin\s*\(',
                    r'verify_token\s*\('
                ]
                
                has_auth = any(re.search(pattern, content, re.IGNORECASE) 
                             for pattern in auth_patterns)
                
                # Check for privileged operations
                privileged_patterns = [
                    r'os\.system\s*\(',
                    r'subprocess\.',
                    r'file.*write',
                    r'delete.*file',
                    r'DROP\s+TABLE',
                    r'DELETE\s+FROM'
                ]
                
                has_privileged = any(re.search(pattern, content, re.IGNORECASE) 
                                   for pattern in privileged_patterns)
                
                if has_privileged and not has_auth:
                    finding = SecurityFinding(
                        severity='high',
                        category='authorization',
                        title='Missing Authorization Check',
                        description=f'File {file_path} performs privileged operations without authorization',
                        file_path=file_path,
                        line_number=None,
                        code_snippet=None,
                        recommendation='Implement proper authorization checks for privileged operations'
                    )
                    findings.append(finding)
                    failed_checks += 1
                else:
                    passed_checks += 1
                    
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        # Check for weak session management
        session_patterns = [
            r'session\[.*\]\s*=',
            r'cookie\s*=',
            r'jwt\.',
            r'token\s*='
        ]
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                for pattern in session_patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Check if secure flags are set
                        line_start = max(0, match.start() - 200)
                        line_end = min(len(content), match.end() + 200)
                        context = content[line_start:line_end]
                        
                        if 'secure' not in context.lower() or 'httponly' not in context.lower():
                            line_num = content[:match.start()].count('\n') + 1
                            
                            finding = SecurityFinding(
                                severity='medium',
                                category='session_management',
                                title='Insecure Session Configuration',
                                description='Session/cookie configuration may be missing security flags',
                                file_path=file_path,
                                line_number=line_num,
                                code_snippet=match.group(),
                                recommendation='Set secure and httponly flags for sessions and cookies'
                            )
                            findings.append(finding)
                            failed_checks += 1
                        else:
                            passed_checks += 1
                            
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        total_checks = passed_checks + failed_checks
        
        result = SecurityAuditResult(
            test_name=test_name,
            findings=findings,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            total_checks=total_checks,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Authentication/authorization test completed: {passed_checks}/{total_checks} checks passed")
        return result
    
    async def test_rate_limiting(self) -> SecurityAuditResult:
        """Test rate limiting and abuse prevention."""
        logger.info("Testing rate limiting and abuse prevention...")
        
        test_name = "rate_limiting"
        findings = []
        passed_checks = 0
        failed_checks = 0
        
        # Check for rate limiting implementations
        python_files = self._get_python_files()
        
        rate_limit_patterns = [
            r'@rate_limit',
            r'@throttle',
            r'RateLimiter',
            r'rate.*limit',
            r'throttle',
            r'cooldown'
        ]
        
        api_endpoint_patterns = [
            r'@app\.route',
            r'@router\.',
            r'def.*command',
            r'async def.*command'
        ]
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Find API endpoints
                endpoints = re.findall(r'(def|async def)\s+(\w+)', content)
                
                has_rate_limiting = any(re.search(pattern, content, re.IGNORECASE) 
                                      for pattern in rate_limit_patterns)
                
                has_endpoints = any(re.search(pattern, content, re.IGNORECASE) 
                                  for pattern in api_endpoint_patterns)
                
                if has_endpoints and not has_rate_limiting:
                    finding = SecurityFinding(
                        severity='medium',
                        category='rate_limiting',
                        title='Missing Rate Limiting',
                        description=f'File {file_path} has API endpoints without rate limiting',
                        file_path=file_path,
                        line_number=None,
                        code_snippet=None,
                        recommendation='Implement rate limiting for API endpoints to prevent abuse'
                    )
                    findings.append(finding)
                    failed_checks += 1
                elif has_endpoints:
                    passed_checks += 1
                    
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        total_checks = passed_checks + failed_checks
        
        result = SecurityAuditResult(
            test_name=test_name,
            findings=findings,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            total_checks=total_checks,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Rate limiting test completed: {passed_checks}/{total_checks} checks passed")
        return result
    
    async def test_sensitive_data_handling(self) -> SecurityAuditResult:
        """Test secure handling of sensitive data and API keys."""
        logger.info("Testing sensitive data handling...")
        
        test_name = "sensitive_data"
        findings = []
        passed_checks = 0
        failed_checks = 0
        
        # Scan all files for sensitive data
        all_files = self._get_all_files()
        
        for file_path in all_files:
            file_findings = self.scan_file_for_vulnerabilities(file_path)
            
            # Filter for sensitive data findings
            sensitive_findings = [f for f in file_findings 
                                if f.category in ['hardcoded_secrets', 'hardcoded_credentials']]
            
            if sensitive_findings:
                findings.extend(sensitive_findings)
                failed_checks += len(sensitive_findings)
            else:
                passed_checks += 1
        
        # Check environment variable usage
        env_patterns = [
            r'os\.environ\[',
            r'os\.getenv\(',
            r'getenv\(',
            r'env\.',
            r'ENV\['
        ]
        
        python_files = self._get_python_files()
        uses_env_vars = False
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                if any(re.search(pattern, content) for pattern in env_patterns):
                    uses_env_vars = True
                    break
                    
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        if not uses_env_vars:
            finding = SecurityFinding(
                severity='medium',
                category='configuration',
                title='No Environment Variable Usage',
                description='Application does not appear to use environment variables for configuration',
                file_path=None,
                line_number=None,
                code_snippet=None,
                recommendation='Use environment variables for sensitive configuration data'
            )
            findings.append(finding)
            failed_checks += 1
        else:
            passed_checks += 1
        
        total_checks = passed_checks + failed_checks
        
        result = SecurityAuditResult(
            test_name=test_name,
            findings=findings,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            total_checks=total_checks,
            timestamp=datetime.now()
        )
        
        self.results.append(result)
        logger.info(f"Sensitive data test completed: {passed_checks}/{total_checks} checks passed")
        return result
    
    def _get_python_files(self) -> List[str]:
        """Get list of Python files to analyze."""
        python_files = []
        
        for root, dirs, files in os.walk('.'):
            # Skip virtual environments and cache directories
            dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        return python_files
    
    def _get_all_files(self) -> List[str]:
        """Get list of all files to analyze."""
        all_files = []
        
        for root, dirs, files in os.walk('.'):
            # Skip virtual environments and cache directories
            dirs[:] = [d for d in dirs if d not in ['.venv', '__pycache__', '.git', 'node_modules']]
            
            for file in files:
                # Skip binary files and common non-source files
                if not any(file.endswith(ext) for ext in ['.pyc', '.pyo', '.so', '.dll', '.exe', '.bin']):
                    all_files.append(os.path.join(root, file))
        
        return all_files
    
    def generate_security_report(self) -> Dict[str, Any]:
        """Generate comprehensive security report."""
        if not self.results:
            return {"error": "No security test results available"}
        
        # Aggregate all findings
        all_findings = []
        for result in self.results:
            all_findings.extend(result.findings)
        
        # Count findings by severity
        severity_counts = {
            'critical': len([f for f in all_findings if f.severity == 'critical']),
            'high': len([f for f in all_findings if f.severity == 'high']),
            'medium': len([f for f in all_findings if f.severity == 'medium']),
            'low': len([f for f in all_findings if f.severity == 'low']),
            'info': len([f for f in all_findings if f.severity == 'info'])
        }
        
        # Count findings by category
        category_counts = {}
        for finding in all_findings:
            category_counts[finding.category] = category_counts.get(finding.category, 0) + 1
        
        # Calculate overall security score
        total_checks = sum(result.total_checks for result in self.results)
        passed_checks = sum(result.passed_checks for result in self.results)
        security_score = (passed_checks / total_checks * 100) if total_checks > 0 else 0
        
        report = {
            "summary": {
                "security_score": round(security_score, 1),
                "total_findings": len(all_findings),
                "critical_findings": severity_counts['critical'],
                "high_findings": severity_counts['high'],
                "medium_findings": severity_counts['medium'],
                "low_findings": severity_counts['low'],
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": total_checks - passed_checks,
                "generated_at": datetime.now().isoformat()
            },
            "test_results": [],
            "findings_by_severity": severity_counts,
            "findings_by_category": category_counts,
            "detailed_findings": [],
            "recommendations": []
        }
        
        # Add test results
        for result in self.results:
            test_data = asdict(result)
            test_data['timestamp'] = result.timestamp.isoformat()
            
            # Convert findings to dict
            test_data['findings'] = [asdict(f) for f in result.findings]
            
            report["test_results"].append(test_data)
        
        # Add detailed findings
        for finding in all_findings:
            finding_data = asdict(finding)
            report["detailed_findings"].append(finding_data)
        
        # Generate recommendations
        recommendations = []
        
        if severity_counts['critical'] > 0:
            recommendations.append({
                "priority": "critical",
                "title": "Address Critical Security Issues",
                "description": f"{severity_counts['critical']} critical security issues found",
                "action": "Immediately fix all critical vulnerabilities before deployment"
            })
        
        if severity_counts['high'] > 0:
            recommendations.append({
                "priority": "high",
                "title": "Fix High-Risk Vulnerabilities",
                "description": f"{severity_counts['high']} high-risk vulnerabilities found",
                "action": "Address high-risk issues within 1 week"
            })
        
        if category_counts.get('hardcoded_credentials', 0) > 0:
            recommendations.append({
                "priority": "high",
                "title": "Remove Hardcoded Credentials",
                "description": "Hardcoded credentials found in source code",
                "action": "Move all credentials to environment variables or secure vaults"
            })
        
        if category_counts.get('input_validation', 0) > 0:
            recommendations.append({
                "priority": "high",
                "title": "Implement Input Validation",
                "description": "Missing input validation detected",
                "action": "Add comprehensive input validation and sanitization"
            })
        
        if security_score < 80:
            recommendations.append({
                "priority": "medium",
                "title": "Improve Overall Security Posture",
                "description": f"Security score is {security_score:.1f}%, below recommended 80%",
                "action": "Implement security best practices and conduct regular security reviews"
            })
        
        report["recommendations"] = recommendations
        
        return report
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all security tests and generate report."""
        logger.info("Starting comprehensive security audit...")
        
        try:
            # Run all security tests
            await self.test_input_validation()
            await self.test_authentication_authorization()
            await self.test_rate_limiting()
            await self.test_sensitive_data_handling()
            
            # Generate and return report
            report = self.generate_security_report()
            
            logger.info("Security audit completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Security audit failed: {e}")
            raise


async def main():
    """Main function to run security audit."""
    auditor = SecurityAuditor()
    
    try:
        report = await auditor.run_all_tests()
        
        # Save report to file
        report_file = f"security_audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Security audit report saved to {report_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("SECURITY AUDIT SUMMARY")
        print("="*80)
        print(f"Security Score: {report['summary']['security_score']:.1f}%")
        print(f"Total Findings: {report['summary']['total_findings']}")
        print(f"Critical: {report['summary']['critical_findings']}")
        print(f"High: {report['summary']['high_findings']}")
        print(f"Medium: {report['summary']['medium_findings']}")
        print(f"Low: {report['summary']['low_findings']}")
        print(f"Checks Passed: {report['summary']['passed_checks']}/{report['summary']['total_checks']}")
        
        if report.get('recommendations'):
            print(f"\nTop Recommendations:")
            for rec in report['recommendations'][:3]:
                print(f"  - {rec['title']} ({rec['priority']} priority)")
        
        print("="*80)
        
        # Return appropriate exit code
        if report['summary']['critical_findings'] > 0:
            return 2  # Critical issues found
        elif report['summary']['high_findings'] > 0:
            return 1  # High-risk issues found
        else:
            return 0  # No critical/high issues
        
    except Exception as e:
        logger.error(f"Security audit failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)