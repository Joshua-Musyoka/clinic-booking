# Savannah Clinic Booking API

A RESTful clinic appointment booking API built with **FastAPI, Python 3.12, MySQL, and stored procedures**.

The API supports doctor availability checks, appointment booking, cancellation, rescheduling, and patient appointment history.

## Table of Contents

- [Live API](#live-api)
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [API Endpoints](#api-endpoints)
- [Testing the API](#testing-the-api)
- [Example Workflows](#example-workflows)
- [Running Automated Tests](#running-automated-tests)
- [Local Development Setup](#local-development-setup)
- [Database Setup](#database-setup)
- [Deployment](#deployment)
- [Error Handling](#error-handling)
- [Design Decisions](#design-decisions)

## Live API

**Base URL**

```text
http://174.138.14.183/api/v1/
```

**Interactive API documentation**

```text
http://174.138.14.183/docs
```

**OpenAPI schema**

```text
http://174.138.14.183/openapi.json
```

**Health check**

```text
http://174.138.14.183/health
```

The health endpoint may be available outside the `/api/v1/` prefix, depending on the application configuration.

> The deployed API currently uses HTTP. Use HTTPS before transmitting real patient information over a public network. Do not submit real patient data while testing this assessment API.

## Features

- Check doctor availability for a specific date.
- Retrieve available 30-minute appointment slots.
- Book appointments with validation.
- Prevent conflicting bookings.
- Cancel appointments and record cancellation reasons.
- Reschedule existing appointments transactionally.
- Retrieve patient appointment history.
- Validate request data using Pydantic.
- Centralize database operations using stored procedures.
- Handle invalid requests and database errors consistently.
- Document endpoints through OpenAPI and Swagger UI.

## Technology Stack

| Component           | Technology                     |
| ------------------- | ------------------------------ |
| Language            | Python 3.12                    |
| API framework       | FastAPI                        |
| Request validation  | Pydantic                       |
| Database            | MySQL 8.0 or compatible server |
| Database operations | Stored procedures              |
| Database driver     | PyMySQL                        |
| ASGI server         | Uvicorn                        |
| Automated testing   | Pytest and HTTPX               |
| Deployment          | DigitalOcean, Nginx, systemd   |
| CI/CD               | GitHub Actions                 |

## Architecture

The application separates responsibilities into the following layers:

```text
HTTP Client
    |
    v
FastAPI Routes
    |
    v
Pydantic Validation
    |
    v
Service Layer
    |
    v
Database Helper
    |
    v
MySQL Stored Procedures
    |
    v
MySQL Database
```

### Responsibilities

- **Routes:** Define HTTP endpoints, accept requests, and return responses.
- **Schemas:** Validate incoming data and structure responses.
- **Services:** Coordinate application logic and translate errors.
- **Database helper:** Manage database connections and stored procedure calls.
- **Stored procedures:** Execute database operations and enforce transactional rules.

## API Endpoints

The following endpoints define the intended API contract.

| Method | Endpoint                                            | Purpose                              |
| ------ | --------------------------------------------------- | ------------------------------------ |
| GET    | `/doctors/{doctor_id}/availability?date=YYYY-MM-DD` | Retrieve available appointment slots |
| POST   | `/appointments`                                     | Book an appointment                  |
| PATCH  | `/appointments/{appointment_id}/cancel`             | Cancel an appointment                |
| PATCH  | `/appointments/{appointment_id}/reschedule`         | Reschedule an appointment            |
| GET    | `/patients/{patient_id}/appointments`               | Retrieve patient appointment history |

### 1. Check doctor availability

```http
GET /api/v1/doctors/{doctor_id}/availability?date=YYYY-MM-DD
```

Example:

```bash
curl -i \
  "http://174.138.14.183/api/v1/doctors/1/availability?date=2026-10-20"
```

The response should identify the available 30-minute appointment slots for the specified doctor and date.

Expected behaviour:

- Validate that the doctor exists.
- Validate the requested date.
- Respect the doctor's working hours.
- Exclude occupied appointment slots.
- Apply the minimum booking notice requirement.
- Return a meaningful error when the doctor does not exist.

Possible response status codes:

| Status | Meaning                             |
| ------ | ----------------------------------- |
| 200    | Availability retrieved successfully |
| 404    | Doctor does not exist               |
| 422    | Invalid doctor ID or date format    |
| 500    | Unexpected server error             |

The exact response body depends on the implemented response schema.

### 2. Book an appointment

```http
POST /api/v1/appointments
Content-Type: application/json
```

First, inspect the request schema in Swagger UI:

```text
http://174.138.14.183/docs
```

Expand `POST /api/v1/appointments` and select **Try it out** to see the required request fields.

You can also inspect the OpenAPI schema:

```bash
curl -s \
  "http://174.138.14.183/openapi.json"
```

Example request structure (illustrative; adjust the fields to match the actual Pydantic schema):

```json
{
    "patient_id": 1,
    "doctor_id": 1,
    "appointment_date": "2026-10-20",
    "appointment_time": "10:00"
}
```

Save the request body in `book-appointment.json`, then submit it:

```bash
curl -i -X POST \
  "http://174.138.14.183/api/v1/appointments" \
  -H "Content-Type: application/json" \
  --data @book-appointment.json
```

Expected behaviour:

- Validate the patient and doctor.
- Validate the appointment date and time.
- Ensure the requested time falls within the doctor's working hours.
- Enforce the booking notice requirement.
- Reject occupied slots.
- Prevent simultaneous requests from creating conflicting appointments.
- Return the created appointment when successful.

Expected status codes:

| Status | Meaning                                                            |
| ------ | ------------------------------------------------------------------ |
| 201    | Appointment created                                                |
| 404    | Patient or doctor not found                                        |
| 409    | Appointment slot is occupied or conflicts with an existing booking |
| 422    | Request validation failed                                          |
| 500    | Unexpected server error                                            |

The implementation may use a different status code for certain business-rule violations. Confirm the actual behaviour in the API documentation.

### 3. Cancel an appointment

```http
PATCH /api/v1/appointments/{appointment_id}/cancel
Content-Type: application/json
```

Inspect the cancellation request schema in Swagger UI to determine whether the reason is sent in a JSON body or through another defined request field.

Illustrative request body:

```json
{
    "reason": "Patient requested cancellation"
}
```

Save the body as `cancel-appointment.json`.

Example request:

```bash
curl -i -X PATCH \
  "http://174.138.14.183/api/v1/appointments/1/cancel" \
  -H "Content-Type: application/json" \
  --data @cancel-appointment.json
```

Expected behaviour:

- Cancel an existing appointment.
- Record the cancellation reason.
- Reject an appointment that is already cancelled.
- Return an appropriate error when the appointment does not exist.
- Release the appointment slot so it can be booked again.

Possible status codes:

| Status | Meaning                          |
| ------ | -------------------------------- |
| 200    | Cancellation successful          |
| 404    | Appointment not found            |
| 409    | Appointment is already cancelled |
| 422    | Invalid cancellation request     |

### 4. Reschedule an appointment

```http
PATCH /api/v1/appointments/{appointment_id}/reschedule
Content-Type: application/json
```

Inspect the rescheduling schema in Swagger UI before submitting a request.

Illustrative request body:

```json
{
    "appointment_date": "2026-10-21",
    "appointment_time": "11:00"
}
```

Save the body as `reschedule-appointment.json`.

Example request:

```bash
curl -i -X PATCH \
  "http://174.138.14.183/api/v1/appointments/1/reschedule" \
  -H "Content-Type: application/json" \
  --data @reschedule-appointment.json
```

Expected behaviour:

- Reject appointments that have already been cancelled.
- Validate the new appointment date and time.
- Ensure the new slot is within the doctor's working hours.
- Enforce the booking notice requirement.
- Reject occupied slots.
- Release the original slot only when rescheduling succeeds.
- Roll back the operation if any validation or database operation fails.

Possible status codes:

| Status | Meaning                                                         |
| ------ | --------------------------------------------------------------- |
| 200    | Rescheduling successful                                         |
| 404    | Appointment not found                                           |
| 409    | Requested slot is occupied or appointment cannot be rescheduled |
| 422    | Invalid rescheduling request                                    |

### 5. Retrieve patient appointment history

```http
GET /api/v1/patients/{patient_id}/appointments
```

Example:

```bash
curl -i \
  "http://174.138.14.183/api/v1/patients/1/appointments"
```

Expected behaviour:

- Validate that the patient exists.
- Return appointments associated with the patient.
- Order appointments by appointment date and time.
- Return an appropriate response when the patient does not exist.

Possible status codes:

| Status | Meaning                       |
| ------ | ----------------------------- |
| 200    | Appointment history retrieved |
| 404    | Patient not found             |
| 422    | Invalid patient ID            |

This is a bonus endpoint for the assessment.

## Testing the API

The API can be tested using Swagger UI, cURL, or automated tests.

### Option 1: Swagger UI

Open:

```text
http://174.138.14.183/docs
```

For each endpoint:

1. Expand the endpoint.
2. Click **Try it out**.
3. Enter the required path and query parameters.
4. Enter the request body if required.
5. Click **Execute**.
6. Inspect the HTTP status code and response body.

Swagger UI is the recommended starting point because it displays the request schemas generated from the actual FastAPI implementation.

### Option 2: cURL

Use the examples in the endpoint sections above.

To display response headers and the response body, use:

```bash
curl -i "http://174.138.14.183/api/v1/doctors/1/availability?date=2026-10-20"
```

To display only the response body:

```bash
curl -s \
  "http://174.138.14.183/api/v1/patients/1/appointments"
```

To format a JSON response using `jq`:

```bash
curl -s \
  "http://174.138.14.183/api/v1/patients/1/appointments" \
  | jq .
```

Install `jq` if necessary:

```bash
sudo apt install jq
```

### Option 3: Postman

1. Create a new Postman collection named `Savannah Clinic Booking API`.
2. Set the base URL to:

    ```text
    http://174.138.14.183/api/v1
    ```

3. Add the five endpoints listed above.
4. Use JSON request bodies for POST and PATCH requests where required.
5. Execute the requests and inspect status codes, response bodies, and response times.

## Example Workflows

Use test records in a development or assessment environment. Confirm the IDs exist before testing.

### Workflow A: Book an appointment

1. Check doctor availability.
2. Identify an available slot.
3. Submit a booking request using a valid patient, doctor, date, and time.
4. Verify that the API returns `201 Created`.
5. Check doctor availability again.
6. Confirm the booked slot is no longer available.

### Workflow B: Prevent double booking

1. Select an available slot.
2. Book the slot successfully.
3. Submit another booking for the same doctor, date, and time.
4. Verify that the second booking is rejected.
5. Confirm that only one appointment occupies the slot.

For stronger concurrency testing, send simultaneous requests for the same slot and verify that no more than one succeeds.

### Workflow C: Cancel an appointment

1. Create an appointment.
2. Cancel it and provide a reason.
3. Verify that the cancellation succeeds.
4. Attempt to cancel the same appointment again.
5. Verify that the duplicate cancellation is rejected.
6. Check doctor availability and confirm the slot has been released.

### Workflow D: Reschedule an appointment

1. Create an appointment.
2. Identify another valid, unoccupied slot.
3. Reschedule the appointment.
4. Verify that the appointment now uses the new slot.
5. Confirm that the original slot is available again.
6. Attempt to reschedule into an occupied slot.
7. Verify that the operation fails without changing the original appointment.

### Workflow E: Retrieve patient history

1. Create one or more appointments for a test patient.
2. Request the patient's appointment history.
3. Verify that the appointments belong to the requested patient.
4. Confirm that results are ordered by appointment date and time.

## Validation and Error Testing

The following cases should be tested in addition to successful requests.

| Test case                                   | Expected behaviour                                   |
| ------------------------------------------- | ---------------------------------------------------- |
| Nonexistent doctor ID                       | Meaningful not-found error                           |
| Invalid date format                         | Validation error                                     |
| Invalid or nonexistent patient ID           | Validation or not-found error                        |
| Appointment outside working hours           | Booking rejected                                     |
| Appointment in the past                     | Booking rejected where required by the booking rules |
| Appointment violates booking notice         | Booking rejected                                     |
| Slot already occupied                       | Booking rejected                                     |
| Two simultaneous bookings for the same slot | At most one booking succeeds                         |
| Cancel nonexistent appointment              | Not-found error                                      |
| Cancel an already cancelled appointment     | Request rejected                                     |
| Reschedule a cancelled appointment          | Request rejected                                     |
| Reschedule into an occupied slot            | Request rejected                                     |
| Failed rescheduling operation               | Original appointment remains unchanged               |
| Unknown endpoint                            | Not-found response                                   |

Business-rule errors should be distinguishable from unexpected server errors. The API should not expose database credentials, SQL statements, or internal stack traces in public responses.

## Running Automated Tests

The repository includes Pytest tests.

### Install dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Run the complete test suite

```bash
pytest -v
```

### Run tests with a shorter summary

```bash
pytest -q
```

### Run a specific test module

For example:

```bash
pytest -v tests/test_appointments.py
```

Other available test modules may include:

```bash
pytest -v tests/test_availability.py
pytest -v tests/test_patients.py
pytest -v tests/test_rescheduling.py
```

Run only the modules that exist in the repository.

### Important testing considerations

- Configure test database credentials separately from production credentials.
- Do not run destructive tests against the production database.
- Use isolated test data so tests can be repeated reliably.
- Test concurrent booking attempts against a database configured with the same locking and transaction behaviour as the deployed environment.
- Confirm that tests clean up any records they create.

## Local Development Setup

### Prerequisites

Install or provide:

- Python 3.12
- MySQL 8.0 or a compatible MySQL server
- Git

### Clone the repository

```bash
git clone https://github.com/Joshua-Musyoka/clinic-booking.git
cd clinic-booking
```

### Create and activate a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Configure environment variables

Create a local `.env` file using the variable names expected by the application's configuration module.

For example, a configuration may contain:

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=savanaclinic_booking
DB_USER=savanaclinic_user
DB_PASSWORD=replace_with_a_local_database_password
```

**These variable names are illustrative.** Check `app/config.py` and the database helper to determine the exact environment variable names required by the application.

Do not commit `.env` to Git.

### Prepare the database

Use the database schema and stored procedure scripts provided in the repository. See [Database Setup](#database-setup).

### Start the API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

Open:

```text
http://127.0.0.1:8001/docs
```

Check the health endpoint:

```bash
curl -i http://127.0.0.1:8001/health
```

The API may require a different port or health route depending on the application configuration.

## Database Setup

The database stores:

- Patients
- Doctors
- Doctor working hours
- Appointments

Database schema and stored procedure definitions are maintained in the repository's `database/` directory.

Before running the application:

1. Create the application database.
2. Apply the schema.
3. Install the required stored procedures.
4. Configure the application's database connection.
5. Create an application database user with the minimum required permissions.
6. Verify that the application can connect to the database.

The exact SQL commands depend on the database scripts and the database user's privileges.

Do not grant unrestricted database administration privileges to the application's runtime account.

## Deployment

The API is deployed to DigitalOcean and managed by systemd.

The GitHub Actions deployment workflow runs when changes are pushed to `main`.

The deployment process:

1. Checks out the repository.
2. Transfers application changes to the server.
3. Installs or updates Python dependencies.
4. Restarts the `clinic-booking` service.
5. Calls the health endpoint to verify that the API responds.

The production `.env` file and other secrets are maintained on the server and excluded from deployment transfers.

## Error Handling

The API should use appropriate HTTP status codes to communicate outcomes.

| Status | Meaning                                    |
| ------ | ------------------------------------------ |
| 200    | Request completed successfully             |
| 201    | Resource created successfully              |
| 400    | Invalid business request, where applicable |
| 404    | Requested resource does not exist          |
| 409    | Request conflicts with existing state      |
| 422    | Request validation failed                  |
| 500    | Unexpected server error                    |

The actual status code depends on the implemented route and exception handling. Refer to Swagger UI and the endpoint tests for the current behaviour.

## Design Decisions

### FastAPI and Pydantic

FastAPI provides request routing, HTTP handling, and OpenAPI documentation. Pydantic validates incoming requests and structures responses.

### MySQL and stored procedures

Stored procedures centralize important database operations, including booking, cancellation, rescheduling, and availability checks.

This approach keeps important database operations consistent and makes use of the developer's existing MySQL experience.

### Concurrency and data integrity

Application-level availability checks alone are insufficient to prevent double booking.

Booking and rescheduling operations should use transactions and appropriate row-level locking. The database must validate slot availability while holding the required locks and commit only after all required checks succeed.

Database constraints should reinforce these protections wherever possible.

### Separation of responsibilities

The application separates HTTP handling, request validation, business orchestration, database connection management, and transactional database operations.

The implementation remains deliberately small and avoids unnecessary abstraction for a focused assessment project.

## Security Considerations

This project is an assessment API and should not be assumed to be production-ready solely because it is deployed.

Before handling real patient information:

- Enforce authentication and authorization where required.
- Configure HTTPS.
- Restrict database access and use least-privilege credentials.
- Keep secrets out of source control.
- Validate inputs and handle errors safely.
- Configure backups and test restoration.
- Protect logs from exposing sensitive patient information.
- Test concurrency and transaction rollback behaviour.
- Restrict access to administrative and operational endpoints.

## License

Specify the project's license here if one has been selected.
