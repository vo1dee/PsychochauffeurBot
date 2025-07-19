#!/usr/bin/env python3
"""
Health check script for production deployment validation.

This script performs comprehensive health checks to ensure the system
is fully operational after deployment.
"""

import asyncio
import argparse
import sys
import time
from typing import Dict, Any, List
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HealthChecker:
    """Comprehensive health checker for production deployments."""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.base_url = self._get_base_url(environment)
        self.results: List[Dict[str, Any]] = []
    
    def _get_base_url(self, environment: str) -> str:
        """Get base URL for the environment."""
        urls = {
            'staging': 'https://staging-bot.example.com',
            'production': 'https://bot.example.com',
            'local': 'http://localhost:8080'
        }
        return urls.get(environment, 'http://localhost:8080')
    
    async def run_health_checks(self) -> bool:
        """Run comprehensive health checks."""
        logger.info(f"Running health checks for {self.environment} environment")
        
        checks = [
            self.check_system_health,
            self.check_service_availability,
            self.check_database_health,
            self.check_external_services,
            self.check_performance_metrics,
            self.check_error_rates,
            self.check_resource_usage
        ]
        
        all_healthy = True
        
        for check in checks:
            try:
                result = await check()
                self.results.append(result)
                
                if result['status'] == 'critical':
                    all_healthy = False
                    logger.error(f"Critical issue: {result['name']} - {result['message']}")
                elif result['status'] == 'warning':
                    logger.warning(f"Warning: {result['name']} - {result['message']}")
                else:
                    logger.info(f"Healthy: {result['name']}")
                    
            except Exception as e:
                logger.error(f"Health check error: {check.__name__} - {str(e)}")
                self.results.append({
                    'name': check.__name__,
                    'status': 'critical',
                    'message': str(e),
                    'details': {}
                })
                all_healthy = False
        
        self._print_health_summary()
        return all_healthy
    
    async def check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/health", timeout=30.0)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and data.get('data', {}).get('status') == 'healthy':
                        return {
                            'name': 'system_health',
                            'status': 'healthy',
                            'message': 'System is healthy',
                            'details': data.get('data', {})
                        }
                    else:
                        return {
                            'name': 'system_health',
                            'status': 'critical',
                            'message': 'System reports unhealthy status',
                            'details': data
                        }
                else:
                    return {
                        'name': 'system_health',
                        'status': 'critical',
                        'message': f'Health endpoint returned HTTP {response.status_code}',
                        'details': {'status_code': response.status_code}
                    }
        
        except Exception as e:
            return {
                'name': 'system_health',
                'status': 'critical',
                'message': f'Failed to check system health: {str(e)}',
                'details': {}
            }
    
    async def check_service_availability(self) -> Dict[str, Any]:
        """Check service availability and response times."""
        try:
            endpoints = [
                '/api/v1/health',
                '/api/v1/metrics',
                '/api/v1/config/global/default'
            ]
            
            response_times = []
            failed_endpoints = []
            
            async with httpx.AsyncClient() as client:
                for endpoint in endpoints:
                    start_time = time.time()
                    try:
                        response = await client.get(f"{self.base_url}{endpoint}", timeout=10.0)
                        response_time = (time.time() - start_time) * 1000  # Convert to ms
                        response_times.append(response_time)
                        
                        if response.status_code >= 500:
                            failed_endpoints.append(f"{endpoint} (HTTP {response.status_code})")
                    
                    except Exception as e:
                        failed_endpoints.append(f"{endpoint} ({str(e)})")
            
            avg_response_time = sum(response_times) / len(response_times) if response_times else 0
            
            if failed_endpoints:
                return {
                    'name': 'service_availability',
                    'status': 'critical',
                    'message': f'Failed endpoints: {", ".join(failed_endpoints)}',
                    'details': {
                        'failed_endpoints': failed_endpoints,
                        'avg_response_time': avg_response_time
                    }
                }
            elif avg_response_time > 5000:  # 5 seconds
                return {
                    'name': 'service_availability',
                    'status': 'warning',
                    'message': f'High response times: {avg_response_time:.1f}ms average',
                    'details': {'avg_response_time': avg_response_time}
                }
            else:
                return {
                    'name': 'service_availability',
                    'status': 'healthy',
                    'message': f'All services available, avg response time: {avg_response_time:.1f}ms',
                    'details': {'avg_response_time': avg_response_time}
                }
        
        except Exception as e:
            return {
                'name': 'service_availability',
                'status': 'critical',
                'message': f'Service availability check failed: {str(e)}',
                'details': {}
            }
    
    async def check_database_health(self) -> Dict[str, Any]:
        """Check database health and performance."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/health", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get('data', {}).get('services', {})
                    db_info = services.get('database', {})
                    
                    db_status = db_info.get('status')
                    response_time = db_info.get('response_time', 0)
                    
                    if db_status == 'healthy':
                        if response_time > 100:  # 100ms threshold
                            return {
                                'name': 'database_health',
                                'status': 'warning',
                                'message': f'Database slow: {response_time}ms response time',
                                'details': db_info
                            }
                        else:
                            return {
                                'name': 'database_health',
                                'status': 'healthy',
                                'message': f'Database healthy: {response_time}ms response time',
                                'details': db_info
                            }
                    else:
                        return {
                            'name': 'database_health',
                            'status': 'critical',
                            'message': f'Database unhealthy: {db_status}',
                            'details': db_info
                        }
                else:
                    return {
                        'name': 'database_health',
                        'status': 'critical',
                        'message': 'Cannot check database health',
                        'details': {}
                    }
        
        except Exception as e:
            return {
                'name': 'database_health',
                'status': 'critical',
                'message': f'Database health check failed: {str(e)}',
                'details': {}
            }
    
    async def check_external_services(self) -> Dict[str, Any]:
        """Check external service connectivity."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/health", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    services = data.get('data', {}).get('services', {})
                    external_apis = services.get('external_apis', {})
                    
                    critical_services = []
                    degraded_services = []
                    healthy_services = []
                    
                    for service_name, service_info in external_apis.items():
                        status = service_info.get('status')
                        if status == 'healthy':
                            healthy_services.append(service_name)
                        elif status == 'degraded':
                            degraded_services.append(service_name)
                        else:
                            critical_services.append(service_name)
                    
                    if critical_services:
                        return {
                            'name': 'external_services',
                            'status': 'warning',  # Not critical as bot can work with some services down
                            'message': f'Critical services down: {", ".join(critical_services)}',
                            'details': external_apis
                        }
                    elif degraded_services:
                        return {
                            'name': 'external_services',
                            'status': 'warning',
                            'message': f'Degraded services: {", ".join(degraded_services)}',
                            'details': external_apis
                        }
                    else:
                        return {
                            'name': 'external_services',
                            'status': 'healthy',
                            'message': f'All external services healthy: {", ".join(healthy_services)}',
                            'details': external_apis
                        }
                else:
                    return {
                        'name': 'external_services',
                        'status': 'warning',
                        'message': 'Cannot check external services',
                        'details': {}
                    }
        
        except Exception as e:
            return {
                'name': 'external_services',
                'status': 'warning',
                'message': f'External services check failed: {str(e)}',
                'details': {}
            }
    
    async def check_performance_metrics(self) -> Dict[str, Any]:
        """Check performance metrics."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/metrics", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    metrics = data.get('data', {})
                    
                    system = metrics.get('system', {})
                    application = metrics.get('application', {})
                    
                    cpu_usage = system.get('cpu_usage', 0)
                    memory_usage = system.get('memory_usage', 0)
                    response_time = application.get('average_response_time', 0)
                    error_rate = application.get('error_rate', 0)
                    
                    issues = []
                    if cpu_usage > 80:
                        issues.append(f'High CPU usage: {cpu_usage}%')
                    if memory_usage > 85:
                        issues.append(f'High memory usage: {memory_usage}%')
                    if response_time > 2000:
                        issues.append(f'High response time: {response_time}ms')
                    if error_rate > 5:
                        issues.append(f'High error rate: {error_rate}%')
                    
                    if issues:
                        return {
                            'name': 'performance_metrics',
                            'status': 'warning',
                            'message': f'Performance issues: {", ".join(issues)}',
                            'details': metrics
                        }
                    else:
                        return {
                            'name': 'performance_metrics',
                            'status': 'healthy',
                            'message': 'Performance metrics within normal ranges',
                            'details': {
                                'cpu_usage': cpu_usage,
                                'memory_usage': memory_usage,
                                'response_time': response_time,
                                'error_rate': error_rate
                            }
                        }
                else:
                    return {
                        'name': 'performance_metrics',
                        'status': 'warning',
                        'message': 'Cannot retrieve performance metrics',
                        'details': {}
                    }
        
        except Exception as e:
            return {
                'name': 'performance_metrics',
                'status': 'warning',
                'message': f'Performance metrics check failed: {str(e)}',
                'details': {}
            }
    
    async def check_error_rates(self) -> Dict[str, Any]:
        """Check error rates and recent errors."""
        # This would typically check error logs or metrics
        # For now, we'll use the metrics endpoint
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/metrics", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    application = data.get('data', {}).get('application', {})
                    error_rate = application.get('error_rate', 0)
                    
                    if error_rate > 10:
                        return {
                            'name': 'error_rates',
                            'status': 'critical',
                            'message': f'Critical error rate: {error_rate}%',
                            'details': {'error_rate': error_rate}
                        }
                    elif error_rate > 5:
                        return {
                            'name': 'error_rates',
                            'status': 'warning',
                            'message': f'Elevated error rate: {error_rate}%',
                            'details': {'error_rate': error_rate}
                        }
                    else:
                        return {
                            'name': 'error_rates',
                            'status': 'healthy',
                            'message': f'Error rate normal: {error_rate}%',
                            'details': {'error_rate': error_rate}
                        }
                else:
                    return {
                        'name': 'error_rates',
                        'status': 'warning',
                        'message': 'Cannot check error rates',
                        'details': {}
                    }
        
        except Exception as e:
            return {
                'name': 'error_rates',
                'status': 'warning',
                'message': f'Error rate check failed: {str(e)}',
                'details': {}
            }
    
    async def check_resource_usage(self) -> Dict[str, Any]:
        """Check resource usage and capacity."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/metrics", timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    system = data.get('data', {}).get('system', {})
                    
                    cpu_usage = system.get('cpu_usage', 0)
                    memory_usage = system.get('memory_usage', 0)
                    disk_usage = system.get('disk_usage', 0)
                    
                    critical_issues = []
                    warnings = []
                    
                    if cpu_usage > 90:
                        critical_issues.append(f'Critical CPU usage: {cpu_usage}%')
                    elif cpu_usage > 75:
                        warnings.append(f'High CPU usage: {cpu_usage}%')
                    
                    if memory_usage > 90:
                        critical_issues.append(f'Critical memory usage: {memory_usage}%')
                    elif memory_usage > 80:
                        warnings.append(f'High memory usage: {memory_usage}%')
                    
                    if disk_usage > 90:
                        critical_issues.append(f'Critical disk usage: {disk_usage}%')
                    elif disk_usage > 80:
                        warnings.append(f'High disk usage: {disk_usage}%')
                    
                    if critical_issues:
                        return {
                            'name': 'resource_usage',
                            'status': 'critical',
                            'message': f'Critical resource usage: {", ".join(critical_issues)}',
                            'details': system
                        }
                    elif warnings:
                        return {
                            'name': 'resource_usage',
                            'status': 'warning',
                            'message': f'High resource usage: {", ".join(warnings)}',
                            'details': system
                        }
                    else:
                        return {
                            'name': 'resource_usage',
                            'status': 'healthy',
                            'message': f'Resource usage normal (CPU: {cpu_usage}%, Memory: {memory_usage}%, Disk: {disk_usage}%)',
                            'details': system
                        }
                else:
                    return {
                        'name': 'resource_usage',
                        'status': 'warning',
                        'message': 'Cannot check resource usage',
                        'details': {}
                    }
        
        except Exception as e:
            return {
                'name': 'resource_usage',
                'status': 'warning',
                'message': f'Resource usage check failed: {str(e)}',
                'details': {}
            }
    
    def _print_health_summary(self):
        """Print health check summary."""
        total_checks = len(self.results)
        healthy_checks = sum(1 for result in self.results if result['status'] == 'healthy')
        warning_checks = sum(1 for result in self.results if result['status'] == 'warning')
        critical_checks = sum(1 for result in self.results if result['status'] == 'critical')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"HEALTH CHECK SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Environment: {self.environment}")
        logger.info(f"Total checks: {total_checks}")
        logger.info(f"Healthy: {healthy_checks}")
        logger.info(f"Warnings: {warning_checks}")
        logger.info(f"Critical: {critical_checks}")
        
        if critical_checks > 0:
            logger.info(f"\nCRITICAL ISSUES:")
            for result in self.results:
                if result['status'] == 'critical':
                    logger.info(f"  ❌ {result['name']}: {result['message']}")
        
        if warning_checks > 0:
            logger.info(f"\nWARNINGS:")
            for result in self.results:
                if result['status'] == 'warning':
                    logger.info(f"  ⚠️  {result['name']}: {result['message']}")
        
        if healthy_checks > 0:
            logger.info(f"\nHEALTHY SERVICES:")
            for result in self.results:
                if result['status'] == 'healthy':
                    logger.info(f"  ✅ {result['name']}: {result['message']}")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Run comprehensive health checks')
    parser.add_argument('--environment', '-e',
                       choices=['local', 'staging', 'production'],
                       default='production',
                       help='Target environment for health checks')
    
    args = parser.parse_args()
    
    checker = HealthChecker(args.environment)
    is_healthy = await checker.run_health_checks()
    
    if not is_healthy:
        logger.error("Health checks failed! System may not be ready for production traffic.")
        sys.exit(1)
    else:
        logger.info("All health checks passed! System is ready for production traffic.")
        sys.exit(0)


if __name__ == '__main__':
    asyncio.run(main())