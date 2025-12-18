# Configuration Guide - Updated Features

This guide documents the new configuration options added to eliminate hardcoded values from the codebase.

## Overview of New Configuration Options

The following new configuration sections and fields have been added to provide greater flexibility and eliminate hardcoded values:

### 1. Timeouts Section

Control timeout values for various operations:

```yaml
timeouts:
  report_generation: 120           # Report generation timeout (seconds)
  user_operation: 60               # User operation timeout (seconds)
```

**Use Cases:**
- **Large deployments**: Increase timeouts if processing many users
- **Slow networks**: Increase timeouts in environments with network latency
- **Fast environments**: Decrease timeouts to fail faster

**Example for large deployment:**
```yaml
timeouts:
  report_generation: 300  # 5 minutes for large reports
  user_operation: 120     # 2 minutes for slow API responses
```

### 2. Validation Section

Configure data validation thresholds:

```yaml
validation:
  max_users_warning: 1000          # User count warning threshold
```

**Use Cases:**
- **Small batches**: Lower threshold to warn about unexpectedly large batches
- **Large operations**: Raise threshold to avoid unnecessary warnings

**Example for enterprise deployment:**
```yaml
validation:
  max_users_warning: 5000  # Warn only when exceeding 5000 users
```

### 3. Enhanced Performance Section

New performance-related options:

```yaml
performance:
  max_workers: 5                   # Default concurrent threads
  max_workers_min: 1               # Minimum concurrent threads
  max_workers_max: 10              # Maximum concurrent threads
  auto_downgrade: true             # Auto-downgrade on rate limits
  show_progress: true              # Show progress information
  progress_update_interval: 0.5    # Progress update interval (seconds)
```

**Use Cases:**
- **High-performance environments**: Increase max_workers_max for faster processing
- **Rate-limited APIs**: Adjust progress_update_interval to reduce console spam
- **Silent operations**: Set progress_update_interval higher for cleaner logs

**Example for high-performance environment:**
```yaml
performance:
  max_workers: 10
  max_workers_min: 5
  max_workers_max: 20
  progress_update_interval: 1.0  # Update every second
```

### 4. Enhanced Retry Section

Added initial delay configuration:

```yaml
retry:
  max_attempts: 3                  # Maximum retry attempts
  backoff_factor: 2.0              # Backoff factor
  initial_delay: 1.0               # Initial retry delay (seconds)
```

**Use Cases:**
- **Aggressive retries**: Decrease initial_delay for faster recovery
- **Conservative retries**: Increase initial_delay to avoid overwhelming services

**Example for aggressive retry strategy:**
```yaml
retry:
  max_attempts: 5
  backoff_factor: 1.5
  initial_delay: 0.5  # Start retrying after 0.5 seconds
```

### 5. Enhanced Logging Section

Added log format configuration:

```yaml
logging:
  level: INFO                      # Log level
  file: logs/subscription_manager.log
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

**Use Cases:**
- **Custom log parsers**: Adjust format for log aggregation tools
- **Detailed debugging**: Include additional context in log messages

**Example for JSON logging:**
```yaml
logging:
  level: DEBUG
  format: '{"time":"%(asctime)s","name":"%(name)s","level":"%(levelname)s","message":"%(message)s"}'
```

### 6. User Format Template

The username template is now clearly documented:

```yaml
user_format:
  username_template: "{employee_id}@your-domain.com"
  use_new_format: true
```

**Use Cases:**
- **Different domains**: Change the domain part for different environments
- **Custom formats**: Use different username patterns

**Example for multiple domains:**
```yaml
# Development environment
user_format:
  username_template: "{employee_id}@dev.company.com"
  
# Production environment
user_format:
  username_template: "{employee_id}@company.com"
```

## Complete Configuration Example

Here's a complete example showing all new options configured for a large enterprise deployment:

```yaml
aws:
  profile: production-profile
  region: us-east-1
  identity_center:
    instance_id: ssoins-xxxxxxxxxxxxx

groups:
  kiro: Group_KIRO_Production
  qdev: Group_QDEV_Production

user_format:
  username_template: "{employee_id}@enterprise.com"
  use_new_format: true

logging:
  level: INFO
  file: logs/enterprise_subscription_manager.log
  format: "%(asctime)s - [%(process)d] - %(name)s - %(levelname)s - %(message)s"

retry:
  max_attempts: 5
  backoff_factor: 2.0
  initial_delay: 2.0

performance:
  max_workers: 10
  max_workers_min: 3
  max_workers_max: 20
  auto_downgrade: true
  show_progress: true
  progress_update_interval: 1.0

timeouts:
  report_generation: 300
  user_operation: 120

validation:
  max_users_warning: 5000
```

## Environment-Specific Configurations

### Development Environment

```yaml
# config.dev.yaml
performance:
  max_workers: 2
  max_workers_max: 5
  progress_update_interval: 0.5

timeouts:
  report_generation: 60
  user_operation: 30

validation:
  max_users_warning: 100

logging:
  level: DEBUG
```

### Production Environment

```yaml
# config.prod.yaml
performance:
  max_workers: 10
  max_workers_max: 20
  progress_update_interval: 2.0

timeouts:
  report_generation: 300
  user_operation: 120

validation:
  max_users_warning: 10000

logging:
  level: WARNING
```

## Migration from Hardcoded Values

If you're upgrading from a version with hardcoded values, here's what changed:

### Previously Hardcoded (Now Configurable)

| What was hardcoded | Where | Now configured in |
|-------------------|-------|-------------------|
| Report timeout: 120s | main.py line 342 | `timeouts.report_generation` |
| User operation timeout: 60s | user_manager.py lines 582, 1046 | `timeouts.user_operation` |
| Max workers range: 1-10 | main.py line 96 | `performance.max_workers_min/max` |
| Progress update: 0.5s | progress_tracker.py line 39 | `performance.progress_update_interval` |
| Max users warning: 1000 | data_validator.py line 252 | `validation.max_users_warning` |
| Group names | models.py lines 42, 44, 46 | `groups.kiro`, `groups.qdev` |
| Username format | models.py line 37 | `user_format.username_template` |

### No Configuration Changes Required

Existing `config.yaml` files will continue to work without any changes. The system uses sensible defaults for all new fields.

### Gradual Migration

You can add new configuration options gradually:

```yaml
# Start by just adding timeouts
timeouts:
  report_generation: 180  # Increase if needed

# Later, add performance tuning
performance:
  max_workers: 8
  progress_update_interval: 1.0

# Finally, customize validation
validation:
  max_users_warning: 2000
```

## Troubleshooting

### Issue: Operations timing out

**Solution**: Increase timeout values
```yaml
timeouts:
  report_generation: 300
  user_operation: 120
```

### Issue: Too many warnings about user count

**Solution**: Increase warning threshold
```yaml
validation:
  max_users_warning: 5000
```

### Issue: Progress updates too frequent

**Solution**: Increase update interval
```yaml
performance:
  progress_update_interval: 2.0
```

### Issue: Rate limiting errors

**Solution**: Reduce max workers and increase delays
```yaml
performance:
  max_workers: 3
  max_workers_max: 5

retry:
  initial_delay: 3.0
  backoff_factor: 3.0
```

## Best Practices

1. **Start with defaults**: Use the default configuration and adjust only what's necessary
2. **Test changes**: Test configuration changes in a development environment first
3. **Document customizations**: Comment your config.yaml to explain why values were changed
4. **Monitor performance**: Use different configurations and monitor to find optimal values
5. **Environment-specific configs**: Maintain separate configs for dev/staging/prod
6. **Version control**: Keep your config.yaml in version control (except sensitive values)

## Additional Resources

- See `config.yaml.example` for a complete configuration template
- See `hardcode_inventory.md` for detailed information about what was changed
- See `CHANGELOG.md` for version history of configuration changes
