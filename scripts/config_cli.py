#!/usr/bin/env python3
"""
Configuration Management CLI Tool

A comprehensive command-line interface for managing configurations
with support for all advanced features.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.unified_config_service import UnifiedConfigService, ConfigScope, ConfigServiceError
from config.enhanced_config_manager import ConfigScope as EnhancedConfigScope

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConfigCLI:
    """Configuration management CLI."""
    
    def __init__(self):
        self.service: Optional[UnifiedConfigService] = None
    
    async def initialize(self):
        """Initialize the configuration service."""
        try:
            self.service = UnifiedConfigService()
            await self.service.initialize()
            logger.info("Configuration service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize configuration service: {e}")
            sys.exit(1)
    
    async def cleanup(self):
        """Cleanup resources."""
        if self.service:
            await self.service.shutdown()
    
    async def get_config(self, key: str, scope: str = "global", default: Any = None) -> None:
        """Get configuration value."""
        try:
            config_scope = ConfigScope(scope)
            value = await self.service.get_config(key, config_scope, default)
            
            if value is None:
                print(f"Configuration '{key}' not found in scope '{scope}'")
                return
            
            # Pretty print the value
            if isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2, default=str))
            else:
                print(value)
                
        except Exception as e:
            logger.error(f"Failed to get configuration: {e}")
            sys.exit(1)
    
    async def set_config(
        self,
        key: str,
        value: str,
        scope: str = "global",
        validate: bool = True,
        source: str = "cli"
    ) -> None:
        """Set configuration value."""
        try:
            config_scope = ConfigScope(scope)
            
            # Try to parse value as JSON, fallback to string
            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError:
                parsed_value = value
            
            success = await self.service.set_config(
                key=key,
                value=parsed_value,
                scope=config_scope,
                validate=validate,
                source=source
            )
            
            if success:
                print(f"Configuration '{key}' set successfully in scope '{scope}'")
            else:
                print(f"Failed to set configuration '{key}'")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Failed to set configuration: {e}")
            sys.exit(1)
    
    async def delete_config(self, key: str, scope: str = "global") -> None:
        """Delete configuration value."""
        try:
            config_scope = ConfigScope(scope)
            success = await self.service.delete_config(key, config_scope)
            
            if success:
                print(f"Configuration '{key}' deleted successfully from scope '{scope}'")
            else:
                print(f"Failed to delete configuration '{key}'")
                sys.exit(1)
                
        except Exception as e:
            logger.error(f"Failed to delete configuration: {e}")
            sys.exit(1)
    
    async def list_configs(self, scope: str = "global", detailed: bool = False) -> None:
        """List configurations."""
        try:
            config_scope = ConfigScope(scope)
            configs = await self.service.list_configs(config_scope, include_metadata=detailed)
            
            if not configs:
                print(f"No configurations found in scope '{scope}'")
                return
            
            print(f"Configurations in scope '{scope}':")
            print("-" * 40)
            
            if detailed:
                for config_info in configs:
                    print(f"Key: {config_info.key}")
                    print(f"  Valid: {config_info.is_valid}")
                    print(f"  Version: {config_info.version}")
                    print(f"  Updated: {config_info.updated_at}")
                    print(f"  Source: {config_info.source}")
                    print(f"  Checksum: {config_info.checksum}")
                    if config_info.validation_errors:
                        print(f"  Errors: {', '.join(config_info.validation_errors)}")
                    print()
            else:
                for config_key in configs:
                    print(f"  - {config_key}")
                    
        except Exception as e:
            logger.error(f"Failed to list configurations: {e}")
            sys.exit(1)
    
    async def validate_configs(self) -> None:
        """Validate all configurations."""
        try:
            validation_results = await self.service.validate_all_configs()
            
            if not validation_results:
                print("All configurations are valid!")
                return
            
            print("Configuration validation results:")
            print("-" * 40)
            
            for config_key, errors in validation_results.items():
                if errors:
                    print(f"❌ {config_key}:")
                    for error in errors:
                        print(f"    - {error}")
                else:
                    print(f"✅ {config_key}: Valid")
                    
        except Exception as e:
            logger.error(f"Failed to validate configurations: {e}")
            sys.exit(1)
    
    async def backup_config(self, key: str, scope: str = "global") -> None:
        """Create backup of configuration."""
        try:
            config_scope = ConfigScope(scope)
            backup_id = await self.service.backup_config(key, config_scope)
            print(f"Backup created: {backup_id}")
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            sys.exit(1)
    
    async def show_stats(self) -> None:
        """Show service statistics."""
        try:
            stats = self.service.get_stats()
            
            print("Configuration Service Statistics:")
            print("-" * 40)
            print(f"Total requests: {stats['requests_total']}")
            print(f"Cache hits: {stats['cache_hits']}")
            print(f"Cache misses: {stats['cache_misses']}")
            print(f"Cache hit rate: {stats['cache_hit_rate']:.2f}%")
            print(f"Cache size: {stats['cache_size']}")
            print(f"Validation errors: {stats['validation_errors']}")
            print(f"Events processed: {stats['events_processed']}")
            print(f"Event handlers: {stats['event_handlers']}")
            
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            sys.exit(1)
    
    async def import_config(self, file_path: str, scope: str = "global") -> None:
        """Import configuration from JSON file."""
        try:
            config_scope = ConfigScope(scope)
            
            with open(file_path, 'r') as f:
                config_data = json.load(f)
            
            if not isinstance(config_data, dict):
                print("Configuration file must contain a JSON object")
                sys.exit(1)
            
            success_count = 0
            error_count = 0
            
            for key, value in config_data.items():
                try:
                    success = await self.service.set_config(
                        key=key,
                        value=value,
                        scope=config_scope,
                        source="import"
                    )
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                        print(f"Failed to import '{key}'")
                except Exception as e:
                    error_count += 1
                    print(f"Error importing '{key}': {e}")
            
            print(f"Import completed: {success_count} successful, {error_count} failed")
            
        except FileNotFoundError:
            print(f"File not found: {file_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in file: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to import configuration: {e}")
            sys.exit(1)
    
    async def export_config(self, file_path: str, scope: str = "global") -> None:
        """Export configurations to JSON file."""
        try:
            config_scope = ConfigScope(scope)
            config_keys = await self.service.list_configs(config_scope)
            
            if not config_keys:
                print(f"No configurations found in scope '{scope}'")
                return
            
            export_data = {}
            
            for key in config_keys:
                try:
                    value = await self.service.get_config(key, config_scope)
                    if value is not None:
                        export_data[key] = value
                except Exception as e:
                    print(f"Warning: Failed to export '{key}': {e}")
            
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            print(f"Exported {len(export_data)} configurations to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to export configuration: {e}")
            sys.exit(1)


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Configuration Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s get gpt.model                    # Get global config
  %(prog)s set gpt.model "gpt-4" --scope global
  %(prog)s list --scope module --detailed
  %(prog)s validate
  %(prog)s backup gpt --scope global
  %(prog)s import config.json --scope global
  %(prog)s export backup.json --scope global
  %(prog)s stats
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get configuration value')
    get_parser.add_argument('key', help='Configuration key')
    get_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                           help='Configuration scope')
    get_parser.add_argument('--default', help='Default value if not found')
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key')
    set_parser.add_argument('value', help='Configuration value (JSON or string)')
    set_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                           help='Configuration scope')
    set_parser.add_argument('--no-validate', action='store_true', help='Skip validation')
    set_parser.add_argument('--source', default='cli', help='Source of the change')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete configuration value')
    delete_parser.add_argument('key', help='Configuration key')
    delete_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                              help='Configuration scope')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List configurations')
    list_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                            help='Configuration scope')
    list_parser.add_argument('--detailed', action='store_true', help='Show detailed information')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate all configurations')
    
    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create configuration backup')
    backup_parser.add_argument('key', help='Configuration key')
    backup_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                              help='Configuration scope')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show service statistics')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import configuration from file')
    import_parser.add_argument('file', help='JSON file to import')
    import_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                              help='Configuration scope')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration to file')
    export_parser.add_argument('file', help='JSON file to export to')
    export_parser.add_argument('--scope', default='global', choices=['global', 'module', 'chat', 'user'],
                              help='Configuration scope')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize CLI
    cli = ConfigCLI()
    await cli.initialize()
    
    try:
        # Execute command
        if args.command == 'get':
            await cli.get_config(args.key, args.scope, args.default)
        elif args.command == 'set':
            await cli.set_config(
                args.key, args.value, args.scope,
                validate=not args.no_validate, source=args.source
            )
        elif args.command == 'delete':
            await cli.delete_config(args.key, args.scope)
        elif args.command == 'list':
            await cli.list_configs(args.scope, args.detailed)
        elif args.command == 'validate':
            await cli.validate_configs()
        elif args.command == 'backup':
            await cli.backup_config(args.key, args.scope)
        elif args.command == 'stats':
            await cli.show_stats()
        elif args.command == 'import':
            await cli.import_config(args.file, args.scope)
        elif args.command == 'export':
            await cli.export_config(args.file, args.scope)
        else:
            parser.print_help()
    
    finally:
        await cli.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)