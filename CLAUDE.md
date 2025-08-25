# Claude Code Project Configuration

## Project: test_PatAI

### Development Commands
- **Build**: `uv sync && python -m pytest`
- **Test**: `python -m pytest tests/`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`

### Project Structure
- `main.py`: Entry point
- `tests/`: Test files
- `pyproject.toml`: Dependencies and project config

### Dependencies Management
- Use `uv add <package>` to add dependencies
- Use `uv sync` to install dependencies
- Use `uv run <command>` to run commands in project environment

### Quality Standards
- Code formatting with Ruff
- Type hints required
- Test coverage target: 80%
- All commits must pass linting

### Development Workflow
1. Create feature branch
2. Implement changes with tests
3. Run linting and tests
4. Commit with descriptive messages