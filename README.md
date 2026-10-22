# Savannah Clinic Booking API

A clinic appointment booking REST API built with **Python 3.12, FastAPI,
MariaDB/MySQL, and stored procedures**. It supports doctor availability,
booking, cancellation, rescheduling, and patient appointment history.

The project is structured as a focused assessment implementation: HTTP
concerns live in FastAPI routes, request validation uses Pydantic,
application workflows are handled in a service layer, and transactional
database operations are implemented in stored procedures.

> **Assessment/demo deployment:** The current public deployment uses
> HTTP. Do not submit real patient information. Configure HTTPS,
> authentication, and authorization before any real-world use.

## Requirements

- Python 3.12
- MariaDB 10.6+ or a compatible MySQL server
- Git
- A database account with permission to create/use the application
  schema and install stored procedures
- `curl` (optional, for command-line API testing)

## Installation and local setup

### 1. Clone the repository

```bash
git clone https://github.com/Joshua-Musyoka/clinic-booking.git
cd clinic-booking
```

### 2. Create a virtual environment and install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Create the database and load the SQL scripts

Create the application database and user in MariaDB/MySQL, then apply
the repository SQL scripts. For example, if the scripts are named as
shown below:

```bash
mysql -u root -p -e "CREATE DATABASE savanaclinic_booking;"
mysql -u root -p savanaclinic_booking < database/schema.sql
mysql -u root -p savanaclinic_booking < database/procedures.sql
```

If the database or user already exists, do not run the `CREATE DATABASE`
statement again. Use the SQL files in `database/` as the source of truth
for the current schema and stored procedure definitions.

### 4. Configure environment variables

Create a `.env` file in the project root:

```dotenv
APP_NAME="Savannah Clinic Booking API"
APP_ENV=development
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=savanaclinic_booking
MYSQL_USER=savanaclinic_user
MYSQL_PASSWORD=replace_with_your_local_password
CLINIC_TIMEZONE=Africa/Nairobi
BOOKING_MIN_NOTICE_MINUTES=60
```

Use credentials for your local database. Do not commit `.env` or
production secrets to Git.

### 5. Start the API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Open the interactive API documentation:

- Swagger UI: <http://127.0.0.1:8001/docs>
- OpenAPI schema: <http://127.0.0.1:8001/openapi.json>
- Health check: <http://127.0.0.1:8001/health>

The health route may be configured outside the `/api/v1` prefix.

### 6. Run the tests

In a second terminal, activate the virtual environment and run:

```bash
source .venv/bin/activate
pytest -q
```

For verbose output:

```bash
pytest -v
```

Use a dedicated test database for tests that write to the database.
Never run destructive tests against production data.

## Live API

- **Base URL:** <http://174.138.14.183/api/v1/>
- **Swagger UI:** <http://174.138.14.183/docs>
- **OpenAPI schema:** <http://174.138.14.183/openapi.json>
- **Health check:** <http://174.138.14.183/health>

The deployed assessment API currently uses HTTP. Treat it as a demo
environment only and do not send real patient data.

## Features

- Retrieve a doctor's available 30-minute slots for a date.
- Book appointments with patient, doctor, working-hours,
  notice-period, and conflict checks.
- Cancel appointments with a recorded reason.
- Reschedule an appointment to an eligible, unoccupied slot.
- Retrieve a single appointment and a patient's appointment history.
- Validate request payloads with Pydantic.
- Use stored procedures for core database operations.
- Return meaningful HTTP errors for common business-rule failures.
- Publish interactive API documentation through FastAPI's OpenAPI
  integration.
- Run automated tests with Pytest and FastAPI's test client.

## Technology stack

Area Technology

---

Language Python 3.12
API framework FastAPI
Validation Pydantic
Database MariaDB / MySQL
Database access PyMySQL
Core data operations Stored procedures
ASGI server Uvicorn
Tests Pytest, HTTPX, FastAPI TestClient
Deployment DigitalOcean, Nginx, systemd
CI/CD GitHub Actions

## API endpoints

All endpoints below are relative to `/api/v1`.

---

Method Endpoint Purpose

---

`GET` `/doctors/{doctor_id}/availability?date=YYYY-MM-DD` List available
30-minute slots for a
doctor

`POST` `/appointments` Book an appointment

`GET` `/appointments/{appointment_id}` Retrieve one
appointment

`PATCH` `/appointments/{appointment_id}/cancel` Cancel an appointment

`PATCH` `/appointments/{appointment_id}/reschedule` Reschedule an
appointment

`GET` `/patients/{patient_id}/appointments` Retrieve a patient's
appointment history

---

Use `/docs` to confirm the live request schemas and response codes; the
documentation is generated from the running application.

### Datetime convention

Datetime inputs without an explicit offset are interpreted as
**Africa/Nairobi local time**. The application converts them to UTC
before calling the database procedures, which use UTC values for
appointment storage and comparisons. Appointment timestamps returned by
the API are presented in Nairobi local time.

Example input:

```json
{
    "patient_id": 1,
    "doctor_id": 1,
    "start_at": "2026-10-22 10:00:00"
}
```

This represents 10:00 in Nairobi, equivalent to 07:00 UTC. The requested
time must also meet the booking rules, including the minimum notice
period, the doctor's working hours, slot alignment, and availability.

### Check doctor availability

```bash
curl -i \
  "http://127.0.0.1:8001/api/v1/doctors/1/availability?date=2026-10-22"
```

The response contains the doctor ID, requested date, and available
slots. Each slot is 30 minutes, subject to the doctor's schedule,
existing bookings, and minimum booking notice.

### Book an appointment

```bash
curl -i -X POST \
  "http://127.0.0.1:8001/api/v1/appointments" \
  -H "Content-Type: application/json" \
  --data '{
    "patient_id": 1,
    "doctor_id": 1,
    "start_at": "2026-10-22 10:00:00"
  }'
```

Replace the sample IDs and time with valid test data. The patient and
doctor must exist and be active, and the selected slot must be valid and
available.

### Retrieve an appointment

```bash
curl -i \
  "http://127.0.0.1:8001/api/v1/appointments/1"
```

### Cancel an appointment

```bash
curl -i -X PATCH \
  "http://127.0.0.1:8001/api/v1/appointments/1/cancel" \
  -H "Content-Type: application/json" \
  --data '{"reason": "Patient requested cancellation"}'
```

A cancellation reason is required. An appointment that has already been
cancelled cannot be cancelled again.

### Reschedule an appointment

```bash
curl -i -X PATCH \
  "http://127.0.0.1:8001/api/v1/appointments/1/reschedule" \
  -H "Content-Type: application/json" \
  --data '{"start_at": "2026-10-23 11:00:00"}'
```

The new time must satisfy the same schedule, notice-period, alignment,
and conflict rules as a new booking. Check the generated API
documentation if the running schema differs.

### Retrieve patient appointment history

```bash
curl -i \
  "http://127.0.0.1:8001/api/v1/patients/1/appointments"
```

Use test patient IDs that exist in your database.

## Architecture and design

The request path is intentionally straightforward:

```text
HTTP client
    |
    v
FastAPI router
    |
    v
Pydantic request validation
    |
    v
Appointment service
    |
    v
Database connection/helper
    |
    v
Stored procedures
    |
    v
MariaDB / MySQL
```

- **Routes** handle HTTP paths, request parameters, and response
  codes.
- **Schemas** validate incoming data and define request shapes.
- **Services** coordinate workflows and translate database failures
  into application errors.
- **Database helper** manages connections and stored procedure calls.
- **Stored procedures** carry out the core data changes and
  transactional checks.

### Why stored procedures?

The booking, cancellation, rescheduling, and availability operations are
database-centric and need consistent validation around shared records.
Stored procedures keep those operations close to the data and allow
transaction boundaries and conflict checks to be handled in one place.
This also fits my existing experience with MySQL/MariaDB.

### Booking integrity and concurrency

A simple availability check in the API is not enough to prevent two
concurrent requests from booking the same slot. The database operation
must re-check conflicts within the transaction and use suitable locking.
Rescheduling should only release the original slot when the new booking
succeeds; on failure, the transaction should leave the original
appointment unchanged.

## Error handling

The service maps known stored-procedure errors to meaningful HTTP
responses, including invalid slot alignment, insufficient booking
notice, inactive patients or doctors, unavailable slots, and missing
records. Unexpected database errors are returned as a generic server
error rather than exposing SQL details or credentials.

The exact status code for a particular case is defined by the current
route and exception-handling implementation. Use Swagger UI and the
tests as the source of truth.

## Deployment and CI/CD

The assessment API is deployed on DigitalOcean, with the application
managed by `systemd` and Nginx in the deployment setup. A GitHub Actions
workflow deploys changes pushed to `main`.

Deployment credentials and production environment variables should
remain in GitHub Actions secrets or on the server, not in the
repository. The current public deployment uses HTTP; HTTPS and
appropriate access controls are necessary before real patient
information can be handled.

## AI use and engineering reflection

### 1. What did you use AI for across the four sections?

I used AI selectively as a review and troubleshooting aid rather than as
a substitute for implementation. It was useful for checking my
understanding of edge cases, reviewing error messages, and improving the
clarity of the documentation. I used it to discuss possible approaches,
then checked suggestions against the requirements, code, database
behaviour, and tests. The design choices and final implementation
decisions remained mine.

### 2. Give one example where an AI suggestion improved your work. What did you prompt it with?

One useful example was clarifying how to handle appointment datetimes. I
wanted clients to submit a straightforward Nairobi local time, while
keeping UTC storage consistent in the database. I asked for a
minimal-change approach that would interpret timezone-naive input as
`Africa/Nairobi`, convert it to UTC for database operations, and present
timestamps in local time in API responses.

That helped me make the timezone convention explicit across request
validation and the service layer instead of treating a timestamp with no
offset as inherently UTC. I then checked the conversion with a concrete
example: `10:00` in Nairobi should correspond to `07:00` UTC.

### 3. Give one example where AI output was wrong or incomplete and how you caught it.

During test troubleshooting, a suggested test change only asserted that
the response status was not `422`. That was too weak: it could pass even
if the request failed for an unrelated reason, such as a database or
booking-rule error. I recognised that the test should verify the
intended behaviour, not merely the absence of one status code. A
stronger test would isolate the service dependency and assert that a
naive Nairobi datetime is converted to the expected UTC value. This
reinforced the importance of reviewing AI-generated suggestions rather
than accepting them at face value.

### 4. Name two decisions you made without AI. Why did you trust your own judgment there?

**First, I chose stored procedures for the core booking operations
instead of introducing an ORM.** I am comfortable with MySQL/MariaDB and
wanted the critical validation and transaction logic to remain close to
the data. For this assessment's scope, that was a deliberate trade-off
in favour of directness and consistency rather than adding another
abstraction.

**Second, I kept the application separated into routers, schemas,
services, and database operations.** That structure is familiar, easy to
test, and proportionate to a small API. It gives each layer a clear
responsibility without introducing a large framework or unnecessary
abstractions. I trusted that decision because it is grounded in
maintainability and in the actual needs of the project.

## Security and production considerations

This is an assessment project, not a claim of production readiness.
Before using it with real patient data:

- Put the API behind HTTPS.
- Implement authentication and role-based authorization.
- Keep database credentials and other secrets out of source control.
- Give the runtime database user only the permissions it needs.
- Avoid logging sensitive patient information.
- Configure backups and test restoration.
- Test transaction rollback and simultaneous booking attempts against
  the target database.
- Restrict operational and administrative endpoints.
