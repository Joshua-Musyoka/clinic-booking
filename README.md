cat > README.md <<'EOF'

# Savannah Clinic Booking API

A REST API for managing patient appointments at a small clinic. The system
allows patients to check doctor availability, book appointments, cancel
appointments, reschedule existing bookings, and retrieve appointment history.

The project is being developed as part of a software engineering assessment,
with an emphasis on correctness, data integrity, concurrency safety, automated
testing, and straightforward deployment.

## 1. Technology Stack

| Component                       | Technology              |
| ------------------------------- | ----------------------- |
| Programming language            | Python 3.12             |
| API framework                   | FastAPI                 |
| Request and response validation | Pydantic                |
| Database                        | MySQL 8.0+              |
| Python database driver          | PyMySQL                 |
| Database business operations    | MySQL stored procedures |
| Automated testing               | Pytest and HTTPX        |
| CI/CD                           | GitHub Actions          |
| Version control                 | Git and GitHub          |

The application will use direct database connections through PyMySQL.
SQLAlchemy, ORM models, and Alembic are not part of the intended architecture.

## 2. Requirements and Business Rules

The clinic has five doctors. Each doctor has defined working hours, and
appointments are scheduled in 30-minute slots.

The system must enforce the following rules:

1. Patients can retrieve available appointment slots for a doctor on a given
   date.
2. Appointments must fall within the doctor's configured working hours.
3. Appointments cannot be booked in the past.
4. Appointments must start at least 60 minutes after the current time.
5. An appointment slot cannot be booked by multiple patients.
6. Cancelling an appointment must make its slot available again.
7. An appointment cannot be cancelled more than once.
8. Rescheduling must validate the new slot using the same rules as booking.
9. Rescheduling must release the original slot when the operation succeeds.
10. Cancelled appointments cannot be rescheduled.
11. Patient appointment history must be ordered chronologically, with upcoming
    appointments returned first where applicable.
12. Database transactions and appropriate locking must protect against
    concurrent booking attempts.

The clinic's configured timezone is `Africa/Nairobi`. API timestamps must
include timezone information where required. The application will normalize
timestamps consistently before storing or comparing them in MySQL.

## 3. API Endpoints

The following endpoints define the intended API contract.

### Check doctor availability

`GET /doctors/{doctor_id}/availability?date=YYYY-MM-DD`

Returns the available 30-minute appointment slots for the specified doctor
on the requested date.

Expected behaviour:

- Validate the doctor and requested date.
- Respect the doctor's working hours.
- Exclude slots that have already been booked.
- Exclude slots that violate the booking notice requirement.
- Return a meaningful error when the doctor does not exist.

### Book an appointment

`POST /appointments`

Creates a new appointment after validating the patient, doctor, working
hours, booking notice, and slot availability.

Expected behaviour:

- Return `201 Created` when the appointment is successfully created.
- Reject invalid appointment requests.
- Reject attempts to book an occupied slot.
- Protect against simultaneous requests attempting to book the same slot.

### Cancel an appointment

`PATCH /appointments/{appointment_id}/cancel`

Cancels an existing appointment and records the cancellation reason.

Expected behaviour:

- Return a successful response when cancellation completes.
- Reject attempts to cancel an appointment that is already cancelled.
- Return an appropriate error when the appointment does not exist.
- Make the appointment's slot available again.

### Reschedule an appointment

`PATCH /appointments/{appointment_id}/reschedule`

Moves an existing appointment to a new valid slot.

Expected behaviour:

- Reject appointments that have already been cancelled.
- Validate the new slot against the doctor's working hours and booking rules.
- Reject occupied slots.
- Release the original slot when rescheduling succeeds.
- Perform the operation transactionally so a failed reschedule does not
  leave the appointment in an inconsistent state.

### Retrieve patient appointment history

`GET /patients/{patient_id}/appointments`

Returns the appointments associated with a patient, ordered by appointment
date and time.

This is a bonus endpoint for the assessment.

## 4. Architecture and Design Decisions

### FastAPI and Pydantic

FastAPI provides the HTTP API and automatic OpenAPI documentation.
Pydantic validates incoming requests and structures outgoing responses.

### MySQL and stored procedures

MySQL stores doctors, patients, working hours, and appointments.

Stored procedures centralize important database operations, including
availability checks, booking, cancellation, rescheduling, and patient
appointment history.

This approach is intended to keep database operations consistent while
using the database technology with which the developer is most familiar.

### Concurrency and data integrity

Application-level availability checks alone are insufficient to prevent
double booking: two requests could observe the same slot as available.

Booking and rescheduling operations will therefore use database transactions
and appropriate row-level locking. Operations will acquire locks in a
consistent order, validate the slot while holding the required locks, and
commit only after all checks succeed.

Database permissions will also be considered so application users cannot
bypass the intended booking operations through unrestricted direct writes.

### Separation of responsibilities

The intended application structure separates:

- Routes: HTTP methods, paths, and response handling.
- Schemas: Request and response validation.
- Services: Application-level orchestration and error mapping.
- Database helper: MySQL connection management and stored procedure calls.
- Stored procedures: Transactional database operations and business rules.

The implementation will remain deliberately small to avoid unnecessary
abstraction for a focused assessment project.

## 5. Local Development Setup

### Prerequisites

Install or provide:

- Python 3.12
- MySQL 8.0 or a compatible MySQL server
- Git

### Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd clinic-booking
```
