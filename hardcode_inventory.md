# Hardcoded Values Inventory

This document provides a comprehensive inventory of all hardcoded values found in the codebase, along with recommendations for moving them to the configuration system.

## Summary

Total hardcoded values identified: **17**

## Detailed Inventory

### 1. AWS Configuration

#### 1.1 AWS Profile Name
- **File**: `src/config.py`
- **Line**: 13
- **Current Value**: `"oversea1"`
- **Description**: Default AWS profile name used for authentication
- **Suggested Approach**: Already configurable via `config.yaml` under `aws.profile`, but has a hardcoded default. Keep as fallback default.
- **Status**: ✅ Already in config system, but update default in documentation

#### 1.2 AWS Region
- **File**: `src/config.py`
- **Line**: 14
- **Current Value**: `"us-east-1"`
- **Description**: Default AWS region for Identity Center operations
- **Suggested Approach**: Already configurable via `config.yaml` under `aws.region`. Keep as sensible fallback default.
- **Status**: ✅ Already in config system

#### 1.3 Identity Center Instance ID
- **File**: `src/config.py`
- **Line**: 15
- **Current Value**: `"ssoins-722353200eb6813f"`
- **Description**: AWS IAM Identity Center instance ID - CRITICAL SECURITY CONCERN
- **Suggested Approach**: Already configurable via `config.yaml` under `aws.identity_center.instance_id`. This is a sensitive value that should NEVER have a hardcoded default in production.
- **Status**: ⚠️ Already in config system, but remove hardcoded default

---

### 2. Group Names

#### 2.1 KIRO Group Name
- **Files**: 
  - `src/config.py` (lines 21, 179)
  - `src/models.py` (lines 42, 46)
- **Current Value**: `"Group_KIRO_eu-central-1"`
- **Description**: Name of the KIRO subscription group in Identity Center
- **Suggested Approach**: Already configurable via `config.yaml` under `groups.kiro`, but hardcoded in `models.py`. Update `models.py` to use config.
- **Status**: ⚠️ Partially configurable, needs update in models.py

#### 2.2 QDEV Group Name
- **Files**: 
  - `src/config.py` (lines 22, 180)
  - `src/models.py` (lines 44, 46)
- **Current Value**: `"Group_QDEV_eu-central-1"`
- **Description**: Name of the QDEV subscription group in Identity Center
- **Suggested Approach**: Already configurable via `config.yaml` under `groups.qdev`, but hardcoded in `models.py`. Update `models.py` to use config.
- **Status**: ⚠️ Partially configurable, needs update in models.py

---

### 3. Username Format

#### 3.1 Username Template
- **Files**: 
  - `src/config.py` (lines 28, 183)
  - `src/models.py` (line 37)
  - `src/user_manager.py` (lines 217, 691, 813, 814, 1168)
  - `src/report_generator.py` (lines 366, 381)
  - `src/user_attribute_upgrader.py` (lines 109, 230)
- **Current Value**: `"{employee_id}@haier-saml.com"` or hardcoded `@haier-saml.com` suffix
- **Description**: Template for generating IAM Identity Center usernames from employee IDs
- **Suggested Approach**: Already configurable via `config.yaml` under `user_format.username_template`, but hardcoded in multiple files. Needs centralized usage through config.
- **Status**: ⚠️ Partially configurable, hardcoded in multiple locations

---

### 4. Performance and Threading Limits

#### 4.1 Max Workers Range Validation
- **File**: `main.py`
- **Line**: 96
- **Current Value**: Range `1-10`
- **Description**: Validation range for maximum concurrent worker threads
- **Suggested Approach**: Add `performance.max_workers_min` and `performance.max_workers_max` to config
- **Status**: ❌ Not configurable

#### 4.2 Max Workers Default Value
- **File**: `main.py`
- **Lines**: 69, 98, 564, 595
- **Current Value**: `5`
- **Description**: Default number of concurrent worker threads
- **Suggested Approach**: Already configurable via `config.yaml` under `performance.max_workers`
- **Status**: ✅ Already in config system

---

### 5. Timeout Values

#### 5.1 Report Generation Timeout
- **File**: `main.py`
- **Line**: 342
- **Current Value**: `120` seconds (2 minutes)
- **Description**: Maximum time allowed for report generation before timeout
- **Suggested Approach**: Add `timeouts.report_generation` to config
- **Status**: ❌ Not configurable

#### 5.2 Future Results Timeout (User Operations)
- **Files**: `src/user_manager.py`
- **Lines**: 582, 1046
- **Current Value**: `60` seconds (1 minute)
- **Description**: Maximum time to wait for concurrent user operation results
- **Suggested Approach**: Add `timeouts.user_operation` to config
- **Status**: ❌ Not configurable

---

### 6. Progress Tracking

#### 6.1 Progress Update Interval
- **File**: `src/progress_tracker.py`
- **Line**: 39
- **Current Value**: `0.5` seconds
- **Description**: Minimum time interval between progress display updates
- **Suggested Approach**: Add `performance.progress_update_interval` to config
- **Status**: ❌ Not configurable

---

### 7. Data Validation Limits

#### 7.1 Maximum Users Warning Threshold
- **File**: `src/data_validator.py`
- **Line**: 252
- **Current Value**: `1000` users
- **Description**: Threshold for warning about large batch sizes
- **Suggested Approach**: Add `validation.max_users_warning` to config
- **Status**: ❌ Not configurable

---

### 8. Retry Configuration

#### 8.1 Initial Retry Delay
- **File**: `src/config.py`
- **Line**: 45
- **Current Value**: `1.0` seconds
- **Description**: Initial delay before first retry attempt
- **Suggested Approach**: Already configurable through `RetryConfig.initial_delay` but not exposed in config.yaml
- **Status**: ⚠️ Exists in code but not in config.yaml

---

### 9. Logging Configuration

#### 9.1 Log Format
- **File**: `src/config.py`
- **Line**: 37
- **Current Value**: `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`
- **Description**: Format string for log messages
- **Suggested Approach**: Already configurable through `LoggingConfig.format` but not exposed in config.yaml
- **Status**: ⚠️ Exists in code but not in config.yaml

---

## Configuration Priorities

### High Priority (Security/Critical)
1. ✅ Identity Center Instance ID - Already configurable, remove hardcoded default
2. ⚠️ Group names in models.py - Update to use config
3. ⚠️ Username template in multiple files - Centralize through config

### Medium Priority (Performance/Behavior)
4. ❌ Report generation timeout - Add to config
5. ❌ User operation timeout - Add to config
6. ❌ Max workers range validation - Add to config
7. ❌ Progress update interval - Add to config
8. ❌ Maximum users warning threshold - Add to config

### Low Priority (Nice to Have)
9. ⚠️ Initial retry delay - Expose in config.yaml
10. ⚠️ Log format - Expose in config.yaml

---

## Implementation Plan

### Phase 1: Update config.py
- Add new configuration fields for timeouts, validation limits, and performance settings
- Add new dataclass for TimeoutConfig
- Add new dataclass for ValidationConfig
- Update PerformanceConfig with additional fields
- Update ConfigManager to load these new sections from config.yaml

### Phase 2: Update config.yaml.example
- Add timeouts section with all timeout configurations
- Add validation section with data validation limits
- Expand performance section with new fields
- Add retry.initial_delay field
- Add logging.format field

### Phase 3: Update Source Files
- Update models.py to accept config and use it for group names and username template
- Update main.py to use timeout values from config
- Update user_manager.py to use timeout values from config
- Update progress_tracker.py to use update interval from config
- Update data_validator.py to use validation limits from config
- Update all files using hardcoded username templates to use config

### Phase 4: Testing and Validation
- Test backward compatibility with existing config files
- Verify default values work correctly
- Test all configuration overrides
- Update documentation

---

## Notes

- All changes must maintain backward compatibility
- Default values should be sensible and production-ready
- Sensitive values (like instance IDs) should not have defaults in production code
- Configuration validation should be enhanced to check new fields
