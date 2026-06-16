## ADDED Requirements

### Requirement: Application provides Passenger-compatible entrypoint
The project SHALL include a `passenger_wsgi.py` file at the repository root that Phusion Passenger can load to serve the FastAPI application. The file SHALL re-execute itself under the project's virtual environment Python and SHALL export the FastAPI `app` instance as `application`.

#### Scenario: Passenger loads the application
- **WHEN** cPanel's Phusion Passenger starts a Python application pointing to `shorty/passenger_wsgi.py`
- **THEN** the script re-executes under `shorty/.venv/bin/python3`
- **AND** imports `src.api.main.app` and exposes it as `application`
- **AND** Passenger serves incoming HTTP requests through the FastAPI app

### Requirement: Dependency manifest available for cPanel
The project SHALL include a `requirements.txt` file generated from `pyproject.toml` so that cPanel's Application Manager "Ensure Dependencies" button can install all required packages via `pip install -r requirements.txt`.

#### Scenario: cPanel installs dependencies
- **WHEN** an operator clicks "Ensure Dependencies" in cPanel's Application Manager
- **THEN** cPanel runs `pip install -r requirements.txt` inside the application's virtual environment
- **AND** all required packages (FastAPI, SQLAlchemy, aiomysql, redis, uvicorn, pydantic, pydantic-settings, alembic, python-dotenv) are installed

### Requirement: Passenger restart mechanism available
The project SHALL provide a `tmp/restart.txt` placeholder file. Touching this file (updating its modification timestamp) SHALL cause Phusion Passenger to restart the application on the next HTTP request.

#### Scenario: Application restarts after touching restart.txt
- **WHEN** an operator runs `touch ~/shorty/tmp/restart.txt` after deploying new code
- **THEN** Phusion Passenger detects the timestamp change
- **AND** restarts the application process on the next incoming request
- **AND** the new code is loaded

### Requirement: Deploy documentation
The project SHALL include a `DEPLOY.md` file documenting the step-by-step process to deploy the application on cPanel shared hosting, covering: prerequisites, cPanel Application Manager registration, environment variable configuration, MySQL database setup, Alembic migration execution, and verification.

#### Scenario: Operator follows the deploy guide
- **WHEN** a new operator reads `DEPLOY.md` and follows the documented steps
- **THEN** the application is accessible at the configured domain/subdomain
- **AND** all API endpoints respond correctly
