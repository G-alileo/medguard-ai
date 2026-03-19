# Contributing to MedGuard AI

Thank you for your interest in contributing! MedGuard is an open-source drug safety assessment system.

## Code of Conduct

- Be respectful and constructive
- Focus on improving patient safety
- Maintain medical accuracy and cite sources

## How to Contribute

### Reporting Issues

- Check existing issues first
- Use clear, descriptive titles
- Include steps to reproduce bugs
- Specify your environment (OS, Python version)

### Suggesting Features

- Open an issue with `[Feature]` tag
- Explain the use case and benefits
- Consider medical safety implications

### Pull Requests

1. **Fork & Branch**
   ```bash
   git checkout -b feature/your-feature
   ```

2. **Code Standards**
   - Follow existing code style
   - Add docstrings for public methods
   - Keep functions focused and testable
   - No emojis in code/comments

3. **Testing**
   ```bash
   python run_comprehensive_tests.py --level all
   ```

4. **Commit Messages**
   ```
   feat: add drug-food interaction detection
   fix: correct severity mapping for contraindicated drugs
   docs: update API examples in README
   ```

5. **Submit PR**
   - Clear description of changes
   - Reference related issues
   - Include test results
   - Update documentation if needed

## Development Setup

```bash
git clone https://github.com/yourusername/medguard_v1.git
cd medguard_v1
uv venv && source .venv/bin/activate
uv sync
python manage.py migrate
python manage.py migrate_hardcoded_data
```

## Areas for Contribution

### High Priority
- Drug interaction data quality
- Alternative medication suggestions
- Test coverage expansion
- Performance optimization

### Welcome Additions
- Additional data sources integration
- UI/UX improvements
- Documentation enhancements
- Internationalization

### Medical Data
- Cite authoritative sources (FDA, PubMed, etc.)
- Include evidence level
- Document data collection methodology
- Verify clinical accuracy

## Code Structure

```
medguard_app/
├── orchestrator/        # Decision pipeline
├── services/           # Business logic (interaction checker, risk engine)
└── utils/              # Normalizers, helpers

apps/
├── data_access/        # Models, repositories, vector store
├── frontend/           # Templates, forms, views
└── pipeline/           # Data processing utilities
```

## Testing

- Add tests for new features
- Maintain >80% code coverage
- Test edge cases and error handling
- Use test fixtures from `test_cases_*.json`

## Questions?

Open an issue with the `question` label.

---

**Medical Disclaimer:** Contributors must ensure all changes maintain the educational nature of this software. It is not intended for clinical decision-making.
