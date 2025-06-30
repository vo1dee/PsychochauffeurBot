import socket
import subprocess
import platform
import asyncio
from modules.logger import general_logger, error_logger
from urllib.parse import urlparse
from modules.const import Config

import asyncio
from datetime import datetime


# Global variables to track API health
api_health = {
    "last_check": None,
    "status": "unknown",
    "consecutive_failures": 0,
    "last_successful": None
}

async def run_diagnostics(url: str = None):
    """
    Run network diagnostics to help troubleshoot connection issues.
    
    Args:
        url: The URL to test connection to (optional)
    
    Returns:
        dict: Dictionary with diagnostic results
    """
    results = {
        "internet_connectivity": False,
        "dns_resolution": {},
        "ping_results": {},
        "target_connection": False,
        "system_info": {}
    }
    
    # System info
    results["system_info"]["platform"] = platform.system()
    results["system_info"]["release"] = platform.release()
    
    # Test basic internet connectivity
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=3)
        results["internet_connectivity"] = True
    except OSError:
        results["internet_connectivity"] = False
    
    # DNS resolution test for common domains
    dns_targets = ["google.com", "cloudflare.com", "openai.com"]
    if url:
        parsed_url = urlparse(url)
        if parsed_url.netloc:
            dns_targets.append(parsed_url.netloc)
    
    for target in dns_targets:
        try:
            ip = socket.gethostbyname(target)
            results["dns_resolution"][target] = ip
        except socket.gaierror:
            results["dns_resolution"][target] = "Failed to resolve"
    
    # Ping test
    ping_targets = ["1.1.1.1", "8.8.8.8"]
    if url:
        parsed_url = urlparse(url)
        if parsed_url.netloc and parsed_url.netloc in results["dns_resolution"]:
            if results["dns_resolution"][parsed_url.netloc] != "Failed to resolve":
                ping_targets.append(results["dns_resolution"][parsed_url.netloc])
    
    for target in ping_targets:
        ping_param = "-n" if platform.system().lower() == "windows" else "-c"
        try:
            output = subprocess.check_output(
                ["ping", ping_param, "1", target],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5
            )
            results["ping_results"][target] = "Success"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            results["ping_results"][target] = "Failed"
    
    # Test connection to target URL if provided
    if url:
        parsed_url = urlparse(url)
        port = 443 if parsed_url.scheme == "https" else 80
        try:
            sock = socket.create_connection((parsed_url.netloc, port), timeout=5)
            sock.close()
            results["target_connection"] = True
        except (socket.timeout, socket.error):
            results["target_connection"] = False
    
    return results

async def run_api_diagnostics(api_url: str):
    """
    Run diagnostics specifically for API connections and log the results
    
    Args:
        api_url: The API base URL to test
    """
    general_logger.info(f"Running network diagnostics for {api_url}")
    
    results = await run_diagnostics(api_url)
    
    # Log detailed results
    general_logger.info(f"Internet connectivity: {'✓' if results['internet_connectivity'] else '✗'}")
    
    general_logger.info("DNS resolution results:")
    for domain, result in results["dns_resolution"].items():
        general_logger.info(f"  {domain}: {result}")
    
    general_logger.info("Ping test results:")
    for target, result in results["ping_results"].items():
        general_logger.info(f"  {target}: {result}")
    
    general_logger.info(f"Target API connection: {'✓' if results['target_connection'] else '✗'}")
    
    # Generate recommendation based on results
    if not results["internet_connectivity"]:
        general_logger.error("DIAGNOSIS: No internet connectivity detected. Check network connection.")
        return "No internet connectivity"
    
    if any(result == "Failed to resolve" for result in results["dns_resolution"].values()):
        general_logger.error("DIAGNOSIS: DNS resolution issues detected. Check DNS configuration.")
        return "DNS resolution issues"
    
    if not results["target_connection"]:
        general_logger.error(f"DIAGNOSIS: Cannot connect to API endpoint {api_url}. Check if the URL is correct and the service is available.")
        return "API endpoint unreachable"
    
    general_logger.info("DIAGNOSIS: Network appears to be functioning correctly. The issue may be related to authentication or API service availability.")
    return "Network OK, potential API service issue"


async def monitor_api_health():
    """
    Periodically monitor API health and log status
    """
    while True:
        try:
            # Update the check time
            api_health["last_check"] = datetime.now()
            
            # Run a simple API check
            check_result = await test_api_connectivity()
            
            if check_result:
                api_health["status"] = "healthy"
                api_health["consecutive_failures"] = 0
                api_health["last_successful"] = datetime.now()
                general_logger.info(f"API health check passed: {Config.OPENROUTER_BASE_URL}")
            else:
                api_health["status"] = "unhealthy"
                api_health["consecutive_failures"] += 1
                general_logger.warning(f"API health check failed: {Config.OPENROUTER_BASE_URL}. Consecutive failures: {api_health['consecutive_failures']}")
                
                # If multiple consecutive failures, run diagnostics
                if api_health["consecutive_failures"] >= 3:
                    general_logger.error(f"Multiple consecutive API failures detected. Running diagnostics...")
                    diagnosis = await run_api_diagnostics(Config.OPENROUTER_BASE_URL)
                    general_logger.error(f"Diagnosis result: {diagnosis}")
        
        except Exception as e:
            general_logger.error(f"Error in API health monitoring: {e}")
            
        # Wait before next check (5 minutes)
        await asyncio.sleep(300)

async def test_api_connectivity():
    """
    Test basic API connectivity with a minimal request

    Returns:
        bool: True if connection successful, False otherwise
    """
    try:
        # Import here to avoid circular import
        from modules.gpt import client

        response = await client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Respond with a single word: OK"},
                {"role": "user", "content": "Health check"}
            ],
            max_tokens=5,
            temperature=0
        )

        if response and hasattr(response, 'choices') and len(response.choices) > 0:
            return True
        return False

    except Exception as e:
        general_logger.warning(f"API connectivity test failed: {e}")
        return False

# Function to start the monitoring in the background
def start_api_monitoring():
    """
    Start the API monitoring as a background task
    """
    asyncio.create_task(monitor_api_health())
    general_logger.info(f"API health monitoring started for {Config.OPENROUTER_BASE_URL}")

# Call this during application startup
# start_api_monitoring()