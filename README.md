# Audiobookshelf Fetch Service

This service fetches listening sessions from an Audiobookshelf (ABS) server and stores them in a local PostgreSQL database. It is designed to run as a systemd service with a periodic timer.

## Prerequisites

- Python 3.x
- PostgreSQL
- `pip`

## Setup

1.  **Clone the repository** (if not already done).

2.  **Install Dependencies**:
    It is recommended to use a virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Database Setup**:
    Since the database is on a remote machine, you'll need to create a dedicated user and database first. Run these SQL commands on your PostgreSQL server (e.g., via `psql` or pgAdmin):
    ```sql
    CREATE USER abs_user WITH PASSWORD 'secure_password';
    CREATE DATABASE abs_history OWNER abs_user;
    ```
    
    Then, on this machine, run the schema script:
    ```bash
    # Replace <REMOTE_IP> with the server's IP address.
    # You might need to install 'postgresql-client' or similar if 'psql' is missing locally.
    psql "postgresql://abs_user:secure_password@<REMOTE_IP>:5432/abs_history" -f schema.sql
    ```

4.  **Configuration**:
    Create a `.env` file in the project root (or `/etc/abs-fetch/env` if preferred, but update service file accordingly).
    
    Example `.env`:
    ```ini
    DB_CONNECTION_STRING=postgresql://user:password@localhost:5432/abs_history
    ABS_API_URL=http://your-abs-server:13378/audiobookshelf
    ABS_API_TOKEN=your_long_jwt_token
    ABS_USER_ID=your_user_uuid
    ```
    *Note: `ABS_API_URL` should include the base path if applicable (e.g., `/audiobookshelf`).*

## Systemd Service & Timer

The service is controlled by a systemd timer.

1.  **Edit Service Files**:
    - Update `systemd/abs-fetch.service`:
        - check `WorkingDirectory` path.
        - check `ExecStart` path (run `which python3` to confirm).
        - check `EnvironmentFile` path.
    - Update `systemd/abs-fetch.timer`:
        - Adjust `OnUnitActiveSec` to change frequency.

2.  **Install Service**:
    ```bash
    sudo cp systemd/abs-fetch.service /etc/systemd/system/
    sudo cp systemd/abs-fetch.timer /etc/systemd/system/
    sudo systemctl daemon-reload
    ```

3.  **Enable and Start Timer**:
    ```bash
    sudo systemctl enable --now abs-fetch.timer
    ```
    *Do not enable the `.service` file directly, as the timer controls it.*

4.  **Check Status**:
    ```bash
    systemctl list-timers --all
    systemctl status abs-fetch.timer
    ```

## Manual Run

To run the fetch logic manually:
```bash
export $(grep -v '^#' .env | xargs)
.venv/bin/python src/main.py
```
