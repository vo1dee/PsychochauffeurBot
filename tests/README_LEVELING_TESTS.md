# User Leveling System - Comprehensive Test Suite

This directory contains a comprehensive test suite for the User Leveling System, implementing task 13 from the leveling system specification.

## 📋 Test Coverage

### Unit Tests (`test_comprehensive_leveling_unit_tests.py`)
- **XPCalculator**: Complete testing of XP calculation logic including:
  - Message XP calculation (1 XP per message)
  - Link XP calculation (3 XP for messages with links)
  - Thank you XP calculation (5 XP for thanked users)
  - Edge cases and error handling
  - Performance validation

- **LevelManager**: Comprehensive level management testing including:
  - Level threshold calculations (exponential progression)
  - Level progression validation (Level 1: 0 XP, Level 2: 50 XP, etc.)
  - Level-up detection and tracking
  - Progress percentage calculations
  - Caching performance optimization

- **AchievementEngine**: Full achievement system validation including:
  - Achievement definitions and categories
  - Condition checking logic
  - Achievement unlocking mechanisms
  - Context-based achievement evaluation

### Integration Tests (`test_leveling_integration_tests.py`)
- **Message Processing Pipeline**: End-to-end message handling
- **Level Up Integration**: Level progression with notifications
- **Achievement Integration**: Achievement unlocking scenarios
- **Error Handling**: Graceful error recovery testing
- **Concurrent Processing**: Multi-user concurrent scenarios
- **Complex Scenarios**: Real-world usage simulations

### Performance Tests (`test_leveling_performance_tests.py`)
- **Single Message Performance**: Individual message processing speed (< 0.1s requirement)
- **High Volume Performance**: Bulk message processing capabilities
- **Component Performance**: Individual component benchmarks
- **Memory Performance**: Memory usage and leak detection
- **Database Performance**: Database operation optimization
- **Concurrent Load Testing**: Multiple users processing simultaneously

### Test Fixtures (`fixtures/leveling_test_fixtures.py`)
- **User Scenarios**: Various user types (new, active, veteran, inactive)
- **Message Scenarios**: Different message types and edge cases
- **Achievement Scenarios**: Achievement unlocking conditions
- **Performance Data**: Load testing data sets
- **Error Scenarios**: Error condition simulations
- **Mock Factories**: Realistic mock object creation

## 🚀 Running Tests

### Quick Start
```bash
# Run all tests
python tests/run_leveling_tests.py --all

# Run comprehensive test suite with requirements validation
python tests/run_leveling_tests.py --comprehensive

# Run quick smoke test
python tests/run_leveling_tests.py --smoke
```

### Specific Test Types
```bash
# Unit tests only
python tests/run_leveling_tests.py --unit

# Integration tests only
python tests/run_leveling_tests.py --integration

# Performance tests only
python tests/run_leveling_tests.py --performance

# Requirements validation
python tests/run_leveling_tests.py --requirements
```

### Component-Specific Tests
```bash
# XP Calculator tests
python tests/run_leveling_tests.py --component xp

# Level Manager tests
python tests/run_leveling_tests.py --component level

# Achievement Engine tests
python tests/run_leveling_tests.py --component achievement

# User Leveling Service tests
python tests/run_leveling_tests.py --component service
```

### Coverage Reports
```bash
# Generate coverage report for all tests
python tests/run_leveling_tests.py --coverage all

# Generate coverage report for specific test type
python tests/run_leveling_tests.py --coverage unit
python tests/run_leveling_tests.py --coverage integration
```

### Using pytest directly
```bash
# Run with custom pytest configuration
pytest -c tests/pytest-leveling.ini tests/test_comprehensive_leveling_unit_tests.py -v

# Run specific test class
pytest tests/test_comprehensive_leveling_unit_tests.py::TestXPCalculatorComprehensive -v

# Run with markers
pytest -m "unit and not slow" tests/ -v
```

## 📊 Test Metrics and Requirements Validation

The test suite validates all requirements from the leveling system specification:

### ✅ Requirement 1: XP Assignment System
- Message XP: 1 XP per message
- Link XP: 3 XP for messages with links
- Thanks XP: 5 XP for thanked users
- Activity counters: messages_count, links_shared, thanks_received

### ✅ Requirement 2: Level Progression System
- Automatic level increases at thresholds
- Exponential progression: Level 1 (0 XP), Level 2 (50 XP), Level 3 (100 XP), etc.
- Level-up detection and notifications
- Progress tracking and percentage calculations

### ✅ Requirement 3: Achievement System
- 50+ achievements across categories (activity, media, social, rare, level)
- Condition-based unlocking
- Achievement notifications
- Prevention of duplicate awards

### ✅ Requirement 4: Thank You Detection System
- Multi-language support (English, Ukrainian, Hebrew)
- Mention and reply-based detection
- Keyword variations (thanks, thank you, дякую, תודה, etc.)

### ✅ Requirement 5: User Profile Display
- Current stats display (level, XP, achievements)
- Achievement emoji formatting
- Progress indicators

### ✅ Requirement 6: Data Persistence
- SQLite database integration
- User statistics storage
- Achievement tracking
- Data consistency

### ✅ Requirement 7: Message Processing Integration
- Seamless bot integration
- Real-time processing
- Error handling without disruption
- New user handling

### ✅ Requirement 8: Performance and Scalability
- < 100ms message processing requirement
- Efficient database queries
- Memory usage optimization
- Concurrent user support

## 🎯 Performance Benchmarks

The test suite validates these performance requirements:

- **Message Processing**: < 0.1 seconds per message
- **XP Calculation**: < 0.001 seconds per calculation
- **Level Calculation**: < 0.0001 seconds per calculation
- **Memory Usage**: < 50MB growth under load
- **Concurrent Processing**: 50+ simultaneous users
- **Database Operations**: Optimized query patterns

## 🔧 Test Configuration

### Pytest Configuration (`pytest-leveling.ini`)
- Async test support
- Coverage reporting
- Test markers for categorization
- Performance timeout settings
- Warning filters

### Test Markers
- `unit`: Unit tests for individual components
- `integration`: Integration tests for component interaction
- `performance`: Performance and load tests
- `slow`: Slow running tests (may be skipped in CI)
- `requirements`: Tests validating specific requirements

## 📈 Coverage Goals

- **Unit Test Coverage**: > 90%
- **Integration Test Coverage**: > 80%
- **Requirements Coverage**: 100%
- **Edge Case Coverage**: Comprehensive
- **Error Scenario Coverage**: Complete

## 🐛 Debugging Tests

### Running Individual Tests
```bash
# Run specific test method
pytest tests/test_comprehensive_leveling_unit_tests.py::TestXPCalculatorComprehensive::test_calculate_message_xp_basic -v -s

# Run with debugging output
pytest tests/test_leveling_integration_tests.py::TestBasicMessageProcessing::test_process_simple_message -v -s --tb=long
```

### Test Data Inspection
```bash
# Run with fixture inspection
pytest --fixtures tests/fixtures/leveling_test_fixtures.py

# Run with verbose fixture output
pytest tests/test_comprehensive_leveling_unit_tests.py -v --setup-show
```

## 📝 Test Reports

### Generate Test Report
```bash
python tests/run_leveling_tests.py --report
```

This generates a comprehensive test report in `test_reports/leveling_test_report.md`.

### Coverage Reports
- **Terminal**: Coverage summary in terminal output
- **HTML**: Detailed HTML report in `htmlcov/`
- **XML**: Machine-readable report in `coverage.xml`

## 🚨 Continuous Integration

The test suite is designed for CI/CD integration:

```yaml
# Example GitHub Actions workflow
- name: Run Leveling System Tests
  run: |
    python tests/run_leveling_tests.py --comprehensive
    python tests/run_leveling_tests.py --coverage all
```

## 🔍 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure project root is in Python path
2. **Async Test Failures**: Check event loop configuration
3. **Performance Test Failures**: May indicate system load issues
4. **Database Test Failures**: Verify SQLite availability

### Debug Mode
```bash
# Run with maximum verbosity
python tests/run_leveling_tests.py --unit --verbose

# Run with pytest debugging
pytest tests/ -v -s --tb=long --no-header
```

## 📚 Test Documentation

Each test file contains comprehensive docstrings explaining:
- Test purpose and scope
- Requirements being validated
- Expected behaviors
- Edge cases covered
- Performance expectations

## 🎉 Success Criteria

The test suite passes when:
- All unit tests pass (100%)
- All integration tests pass (100%)
- Performance tests meet benchmarks
- All 8 requirements are validated
- Coverage goals are met
- No memory leaks detected
- Error handling works correctly

This comprehensive test suite ensures the User Leveling System meets all specified requirements and performs reliably under various conditions.