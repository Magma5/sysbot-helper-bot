# Sysbot Helper Bot

A multi-functional Discord and Telegram bot modernized for Python 3.14.

---

## 1. Environment Setup

Clone the repository and install all dependencies:

```bash
# Install poetry (if not already installed)
pip install poetry

# Install and link all packages
poetry install
```

---

## 2. Database Setup

Ensure you have a PostgreSQL database running and configured to match your `config.yml` database settings:

```yaml
database_url: postgresql+asyncpg://username:password@localhost/dbname
```

---

## 3. Run Database Migrations

Set up all required production tables natively using poetry:

```bash
poetry run python main.py config.yml --alembic upgrade head
```

---

## 4. Run the Test Suite

To verify that everything is configured and working offline:

```bash
poetry run python -m unittest tests/test_bot_smoke.py tests/test_templates.py
```

---

## 5. Start the Bot

Launch the bot with your active config:

```bash
poetry run python main.py config.yml
```
