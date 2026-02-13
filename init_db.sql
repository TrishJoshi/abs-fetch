-- Run these commands on your remote PostgreSQL server
-- (e.g. `psql -U postgres`)

CREATE USER abs_user WITH PASSWORD 'secure_password';
CREATE DATABASE abs_history OWNER abs_user;

-- Replace 'secure_password' with a strong password.
