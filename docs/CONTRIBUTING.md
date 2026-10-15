# Contributing

Thank you for your interest in contributing to this project! This document provides guidelines for contributing to ensure consistency across the portfolio.

## Development Process

### 1. Fork and Clone
```bash
# Fork the repository on GitLab
# Clone your fork
git clone https://gitlab.com/your-username/project-name.git
cd project-name
```

### 2. Set Up Development Environment
```bash
# Install dependencies (varies by project)
# For Node.js projects:
npm install

# For Python projects:
pip install -r requirements.txt

# For Rust projects:
cargo build
```

### 3. Create a Feature Branch
```bash
git checkout -b feature/your-feature-name
```

### 4. Make Changes
- Follow the project's coding standards
- Add tests for new functionality
- Update documentation as needed
- Ensure all tests pass

### 5. Commit and Push
```bash
git add .
git commit -m "feat: add your feature description"
git push origin feature/your-feature-name
```

### 6. Create Merge Request
- Create a merge request on GitLab
- Provide clear description of changes
- Link to any related issues
- Ensure CI/CD pipeline passes

## Code Standards

### General Guidelines
- Write clear, readable code with appropriate comments
- Follow existing code style in the project
- Include tests for new features and bug fixes
- Update documentation for API changes

### Commit Message Format
Follow conventional commits:
```
type(scope): description

feat: add new feature
fix: resolve bug
docs: update documentation
style: formatting changes
refactor: code restructuring
test: add or update tests
chore: maintenance tasks
```

### Testing
- Add unit tests for new functionality
- Ensure all existing tests continue to pass
- Aim for high test coverage on new code
- Include integration tests where appropriate

## Documentation

### Required Documentation Updates
- Update README.md if adding new features
- Add docstrings/comments for new functions and classes
- Update API documentation for interface changes
- Include examples for new functionality

### Documentation Standards
- Use clear, concise language
- Provide code examples where helpful
- Keep documentation current with code changes
- Follow project-specific documentation format

## Issue Reporting

### Bug Reports
Include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, versions, etc.)
- Relevant logs or error messages

### Feature Requests
Include:
- Clear description of the proposed feature
- Use case and rationale
- Potential implementation approach
- Impact on existing functionality

## Code Review Process

### For Contributors
- Ensure your code follows project standards
- Respond promptly to review feedback
- Make requested changes in additional commits
- Squash commits before merge if requested

### For Reviewers
- Provide constructive feedback
- Check for code quality, test coverage, and documentation
- Verify CI/CD pipeline passes
- Approve when ready for merge

## Getting Help

### Resources
- Project documentation in `/docs`
- README.md for project-specific information
- GitLab issues for questions and discussions

### Contact
- Project maintainers: See CODEOWNERS file
- Project team: team@example.com
- Technical questions: Create an issue on GitLab

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

---

*This template should be customized for each specific project's requirements and workflow.*