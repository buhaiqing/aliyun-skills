# Contributing to alicloud-dns-ops

Thank you for your interest in contributing to the Alibaba Cloud DNS Operations Skill! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Issue Reporting](#issue-reporting)

## Code of Conduct

Please follow our [Code of Conduct](../CODE_OF_CONDUCT.md) in all interactions with the project.

## Getting Started

### Prerequisites

- Alibaba Cloud CLI (`aliyun`) installed
- Valid API credentials configured
- Git installed
- Bash shell environment

### Setup

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/aliyun-skills.git
   cd aliyun-skills/alicloud-dns-ops
   ```
3. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### 1. Understand the Codebase

- Read `SKILL.md` for skill documentation
- Review `references/` for detailed implementation guides
- Examine `scripts/dns-skillopt-wrapper.sh` for wrapper implementation
- Check `TODO.md` for current development priorities

### 2. Make Changes

- Follow existing code patterns and style
- Keep changes focused and minimal
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run backward compatibility tests
./scripts/test-skillopt-backward-compatibility.sh alicloud-dns-ops

# Test wrapper functionality
./scripts/dns-skillopt-wrapper.sh health

# Test specific operations
./scripts/dns-skillopt-wrapper.sh alidns DescribeDomains
```

### 4. Commit Changes

- Use clear, descriptive commit messages
- Follow conventional commit format:
  ```
  feat: add support for new record type
  fix: resolve TTL validation issue
  docs: update CLI usage examples
  test: add unit tests for validation
  ```

## Code Standards

### Shell Scripting

- Use `#!/usr/bin/env bash` shebang
- Enable `set -euo pipefail` for error handling
- Quote all variables: `"$variable"`
- Use `[[ ]]` for conditionals
- Add comments for complex logic
- Follow existing code style

### Documentation

- Use Markdown format
- Include code examples
- Keep documentation up-to-date
- Follow existing documentation patterns

### Testing

- Add tests for new functionality
- Test edge cases and error conditions
- Ensure backward compatibility
- Document test procedures

## Testing

### Unit Tests

Test individual functions and components:

```bash
# Test input validation
test_validation() {
  # Test valid IPv4
  ./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
    --DomainName "example.com" \
    --RR "www" \
    --Type "A" \
    --Value "1.2.3.4" \
    --TTL 600
  
  # Test invalid IPv4 (should fail)
  ./scripts/dns-skillopt-wrapper.sh alidns AddRecord \
    --DomainName "example.com" \
    --RR "www" \
    --Type "A" \
    --Value "invalid" \
    --TTL 600
}
```

### Integration Tests

Test with external services:

```bash
# Test with GCL Runner
./scripts/test-gcl-integration.sh alicloud-dns-ops

# Test with Runtime Harness
./scripts/test-harness-integration.sh alicloud-dns-ops
```

### Performance Tests

Benchmark operation latency:

```bash
# Measure operation time
time ./scripts/dns-skillopt-wrapper.sh alidns DescribeDomains
```

## Documentation

### Updating Documentation

1. **SKILL.md** — Update for new operations or changes
2. **references/** — Update specific guides as needed
3. **README.md** — Update usage examples and features
4. **CHANGELOG.md** — Document changes for releases

### Documentation Standards

- Use clear, concise language
- Include practical examples
- Follow existing formatting patterns
- Keep documentation synchronized with code

## Pull Request Process

### 1. Prepare Your PR

- Ensure all tests pass
- Update documentation
- Add changelog entry
- Rebase on latest main branch

### 2. Submit PR

- Use descriptive PR title
- Include detailed description
- Reference related issues
- Add screenshots/examples if applicable

### 3. PR Review

- Address review feedback
- Ensure CI passes
- Get required approvals
- Squash commits if requested

### 4. Merge

- PR will be merged after approval
- Delete feature branch after merge
- Update local repository

## Issue Reporting

### Bug Reports

Include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details
- Relevant logs or screenshots

### Feature Requests

Include:
- Clear description of the feature
- Use case and benefits
- Proposed implementation (if any)
- Alternatives considered

### Security Issues

Report security issues privately to:
- Email: security@aliyun-skills.com
- Include "SECURITY" in subject line

## Development Guidelines

### Adding New Operations

1. Add CLI command to `references/cli-usage.md`
2. Add operation to `SKILL.md`
3. Add validation to wrapper script
4. Add tests for new operation
5. Update documentation

### Modifying Existing Operations

1. Ensure backward compatibility
2. Update documentation
3. Add tests for changes
4. Update changelog

### Deprecating Operations

1. Add deprecation notice
2. Provide migration path
3. Maintain backward compatibility
4. Update documentation

## Getting Help

- **Documentation**: See `references/` directory
- **Issues**: Report at [GitHub Issues](https://github.com/your-org/aliyun-skills/issues)
- **Discussions**: Use [GitHub Discussions](https://github.com/your-org/aliyun-skills/discussions)
- **Contact**: SRE Team

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](../LICENSE).