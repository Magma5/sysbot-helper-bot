# Sysbot Helper Bot

A multi-functional Discord and Telegram bot modernized for Python 3.14.

---

## 1. Environment Setup

Clone the repository and install all dependencies:

```bash
# Install and link all packages
uv sync
```

---

## 2. Database Setup

Ensure you have a PostgreSQL database running and configured to match your `config.yml` database settings:

```yaml
database_url: postgresql+asyncpg://username:password@localhost/dbname
```

---

## 3. Run Database Migrations

Set up all required production tables natively using uv:

```bash
uv run bot config.yml --alembic upgrade head
```

---

## 4. Run the Test Suite

The test suite is organized into fast isolated unit tests and integration tests using `pytest`:

```bash
# Run isolated fast unit tests (< 0.5s execution)
uv run pytest tests/unit/

# Run integration tests (Database & Bot Cog loading)
uv run pytest tests/integration/

# Run all tests with code coverage
uv run pytest --cov=sysbot_helper tests/
```

To run integration database tests against a live PostgreSQL instance instead of the default in-memory database, set `POSTGRES_TEST_DATABASE_URL`:

```bash
POSTGRES_TEST_DATABASE_URL="postgresql+asyncpg://username:password@localhost/dbname" uv run pytest tests/integration/
```

---

## 5. Start the Bot

Launch the bot with your active config:

```bash
uv run bot config.yml
```
