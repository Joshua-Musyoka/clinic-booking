USE savanaclinic_booking;

-- =========================================================
-- DROP EXISTING PROCEDURES
-- Safe to rerun: this replaces procedures, not table data.
-- =========================================================

DROP PROCEDURE IF EXISTS sp_get_doctor_availability;
DROP PROCEDURE IF EXISTS sp_book_appointment;
DROP PROCEDURE IF EXISTS sp_cancel_appointment;
DROP PROCEDURE IF EXISTS sp_reschedule_appointment;
DROP PROCEDURE IF EXISTS sp_get_patient_appointments;

DELIMITER $$


-- =========================================================
-- 1. GET DOCTOR AVAILABILITY
--
-- Parameters:
--   p_doctor_id
--   p_date: clinic-local calendar date
--
-- Returns available 30-minute slots as UTC DATETIME values.
-- Kenya uses UTC+03:00.
-- =========================================================

CREATE PROCEDURE sp_get_doctor_availability(
    IN p_doctor_id BIGINT UNSIGNED,
    IN p_date DATE
)
availability_proc: BEGIN
    DECLARE v_doctor_active BOOLEAN DEFAULT FALSE;
    DECLARE v_schedule_count INT DEFAULT 0;
    DECLARE v_start_time TIME;
    DECLARE v_end_time TIME;

    IF p_date IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_DATE';
    END IF;

    SELECT COUNT(*)
    INTO v_schedule_count
    FROM doctors
    WHERE id = p_doctor_id;

    IF v_schedule_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_NOT_FOUND';
    END IF;

    SELECT is_active
    INTO v_doctor_active
    FROM doctors
    WHERE id = p_doctor_id;

    IF v_doctor_active = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_INACTIVE';
    END IF;

    SELECT COUNT(*)
    INTO v_schedule_count
    FROM doctor_working_hours
    WHERE doctor_id = p_doctor_id
      AND weekday_iso = WEEKDAY(p_date) + 1
      AND is_active = TRUE;

    IF v_schedule_count = 0 THEN
        SELECT
            CAST(NULL AS DATETIME) AS start_at_utc,
            CAST(NULL AS DATETIME) AS end_at_utc
        WHERE FALSE;

        LEAVE availability_proc;
    END IF;

    SELECT start_time, end_time
    INTO v_start_time, v_end_time
    FROM doctor_working_hours
    WHERE doctor_id = p_doctor_id
      AND weekday_iso = WEEKDAY(p_date) + 1
      AND is_active = TRUE
    LIMIT 1;

    WITH RECURSIVE slot_series AS (
        SELECT
            CAST(
                CONCAT(p_date, ' ', v_start_time)
                AS DATETIME
            ) AS local_start,

            DATE_ADD(
                CAST(
                    CONCAT(p_date, ' ', v_start_time)
                    AS DATETIME
                ),
                INTERVAL 30 MINUTE
            ) AS local_end

        UNION ALL

        SELECT
            DATE_ADD(local_start, INTERVAL 30 MINUTE),
            DATE_ADD(local_end, INTERVAL 30 MINUTE)
        FROM slot_series
        WHERE DATE_ADD(local_end, INTERVAL 30 MINUTE)
              <= CAST(
                  CONCAT(p_date, ' ', v_end_time)
                  AS DATETIME
              )
    )
    SELECT
        CONVERT_TZ(
            s.local_start,
            '+03:00',
            '+00:00'
        ) AS start_at_utc,

        CONVERT_TZ(
            s.local_end,
            '+03:00',
            '+00:00'
        ) AS end_at_utc

    FROM slot_series s

    WHERE s.local_end <= CAST(
        CONCAT(p_date, ' ', v_end_time)
        AS DATETIME
    )

      AND CONVERT_TZ(
          s.local_start,
          '+03:00',
          '+00:00'
      ) >= DATE_ADD(
          UTC_TIMESTAMP(),
          INTERVAL 60 MINUTE
      )

      AND NOT EXISTS (
          SELECT 1
          FROM appointments a
          WHERE a.doctor_id = p_doctor_id
            AND a.status = 'BOOKED'
            AND a.start_at_utc <
                CONVERT_TZ(
                    s.local_end,
                    '+03:00',
                    '+00:00'
                )
            AND a.end_at_utc >
                CONVERT_TZ(
                    s.local_start,
                    '+03:00',
                    '+00:00'
                )
      )

    ORDER BY s.local_start;
END$$


-- =========================================================
-- 2. BOOK APPOINTMENT
--
-- Input start time must be UTC.
-- Appointment duration is exactly 30 minutes.
--
-- The doctor row is locked before availability is checked.
-- =========================================================

CREATE PROCEDURE sp_book_appointment(
    IN p_patient_id BIGINT UNSIGNED,
    IN p_doctor_id BIGINT UNSIGNED,
    IN p_start_at_utc DATETIME
)
booking_proc: BEGIN
    DECLARE v_doctor_count INT DEFAULT 0;
    DECLARE v_patient_count INT DEFAULT 0;
    DECLARE v_schedule_count INT DEFAULT 0;

    DECLARE v_doctor_active BOOLEAN DEFAULT FALSE;
    DECLARE v_patient_active BOOLEAN DEFAULT FALSE;

    DECLARE v_local_start DATETIME;
    DECLARE v_local_end DATETIME;
    DECLARE v_end_at_utc DATETIME;

    DECLARE v_work_start TIME;
    DECLARE v_work_end TIME;

    DECLARE v_conflict_count INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF p_start_at_utc IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_START_TIME';
    END IF;

    IF SECOND(p_start_at_utc) <> 0
       OR MINUTE(p_start_at_utc) NOT IN (0, 30) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_SLOT_ALIGNMENT';
    END IF;

    IF p_start_at_utc < DATE_ADD(
        UTC_TIMESTAMP(),
        INTERVAL 60 MINUTE
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'BOOKING_NOTICE_TOO_SHORT';
    END IF;

    SET v_end_at_utc = DATE_ADD(
        p_start_at_utc,
        INTERVAL 30 MINUTE
    );

    SET v_local_start = CONVERT_TZ(
        p_start_at_utc,
        '+00:00',
        '+03:00'
    );

    SET v_local_end = CONVERT_TZ(
        v_end_at_utc,
        '+00:00',
        '+03:00'
    );

    SELECT COUNT(*)
    INTO v_doctor_count
    FROM doctors
    WHERE id = p_doctor_id;

    IF v_doctor_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_NOT_FOUND';
    END IF;

    -- Serialize booking operations for this doctor.
    SELECT is_active
    INTO v_doctor_active
    FROM doctors
    WHERE id = p_doctor_id
    FOR UPDATE;

    IF v_doctor_active = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_INACTIVE';
    END IF;

    SELECT COUNT(*)
    INTO v_patient_count
    FROM patients
    WHERE id = p_patient_id;

    IF v_patient_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_NOT_FOUND';
    END IF;

    SELECT is_active
    INTO v_patient_active
    FROM patients
    WHERE id = p_patient_id;

    IF v_patient_active = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_INACTIVE';
    END IF;

    SELECT COUNT(*)
    INTO v_schedule_count
    FROM doctor_working_hours
    WHERE doctor_id = p_doctor_id
      AND weekday_iso = WEEKDAY(DATE(v_local_start)) + 1
      AND is_active = TRUE
      AND TIME(v_local_start) >= start_time
      AND TIME(v_local_end) <= end_time;

    IF v_schedule_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'OUTSIDE_WORKING_HOURS';
    END IF;

    SELECT COUNT(*)
    INTO v_conflict_count
    FROM appointments
    WHERE doctor_id = p_doctor_id
      AND status = 'BOOKED'
      AND start_at_utc < v_end_at_utc
      AND end_at_utc > p_start_at_utc;

    IF v_conflict_count > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'SLOT_ALREADY_BOOKED';
    END IF;

    INSERT INTO appointments (
        patient_id,
        doctor_id,
        start_at_utc,
        end_at_utc,
        status
    )
    VALUES (
        p_patient_id,
        p_doctor_id,
        p_start_at_utc,
        v_end_at_utc,
        'BOOKED'
    );

    COMMIT;

    SELECT
        LAST_INSERT_ID() AS appointment_id,
        p_patient_id AS patient_id,
        p_doctor_id AS doctor_id,
        p_start_at_utc AS start_at_utc,
        v_end_at_utc AS end_at_utc,
        'BOOKED' AS status;
END$$


-- =========================================================
-- 3. CANCEL APPOINTMENT
--
-- A cancellation releases the slot by changing the status.
-- =========================================================

CREATE PROCEDURE sp_cancel_appointment(
    IN p_appointment_id BIGINT UNSIGNED,
    IN p_reason VARCHAR(500)
)
cancellation_proc: BEGIN
    DECLARE v_appointment_count INT DEFAULT 0;
    DECLARE v_status VARCHAR(20);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    SELECT COUNT(*)
    INTO v_appointment_count
    FROM appointments
    WHERE id = p_appointment_id;

    IF v_appointment_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_NOT_FOUND';
    END IF;

    SELECT status
    INTO v_status
    FROM appointments
    WHERE id = p_appointment_id
    FOR UPDATE;

    IF v_status = 'CANCELLED' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_ALREADY_CANCELLED';
    END IF;

    IF v_status = 'COMPLETED' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_ALREADY_COMPLETED';
    END IF;

    IF p_reason IS NULL OR CHAR_LENGTH(TRIM(p_reason)) = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'CANCELLATION_REASON_REQUIRED';
    END IF;

    UPDATE appointments
    SET
        status = 'CANCELLED',
        cancellation_reason = TRIM(p_reason),
        cancelled_at_utc = UTC_TIMESTAMP()
    WHERE id = p_appointment_id;

    COMMIT;

    SELECT
        id AS appointment_id,
        status,
        cancellation_reason,
        cancelled_at_utc
    FROM appointments
    WHERE id = p_appointment_id;
END$$


-- =========================================================
-- 4. RESCHEDULE APPOINTMENT
--
-- The original booking remains intact if validation fails.
-- The appointment is excluded from its own conflict check.
-- =========================================================

CREATE PROCEDURE sp_reschedule_appointment(
    IN p_appointment_id BIGINT UNSIGNED,
    IN p_new_start_at_utc DATETIME
)
reschedule_proc: BEGIN
    DECLARE v_appointment_count INT DEFAULT 0;
    DECLARE v_doctor_count INT DEFAULT 0;
    DECLARE v_schedule_count INT DEFAULT 0;
    DECLARE v_conflict_count INT DEFAULT 0;

    DECLARE v_patient_id BIGINT UNSIGNED;
    DECLARE v_doctor_id BIGINT UNSIGNED;
    DECLARE v_status VARCHAR(20);

    DECLARE v_doctor_active BOOLEAN DEFAULT FALSE;

    DECLARE v_new_end_at_utc DATETIME;
    DECLARE v_local_start DATETIME;
    DECLARE v_local_end DATETIME;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF p_new_start_at_utc IS NULL THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_START_TIME';
    END IF;

    IF SECOND(p_new_start_at_utc) <> 0
       OR MINUTE(p_new_start_at_utc) NOT IN (0, 30) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_SLOT_ALIGNMENT';
    END IF;

    IF p_new_start_at_utc < DATE_ADD(
        UTC_TIMESTAMP(),
        INTERVAL 60 MINUTE
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'BOOKING_NOTICE_TOO_SHORT';
    END IF;

    SELECT COUNT(*)
    INTO v_appointment_count
    FROM appointments
    WHERE id = p_appointment_id;

    IF v_appointment_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_NOT_FOUND';
    END IF;

    -- Lock the appointment so concurrent changes cannot
    -- modify it while this reschedule is in progress.
    SELECT patient_id, doctor_id, status
    INTO v_patient_id, v_doctor_id, v_status
    FROM appointments
    WHERE id = p_appointment_id
    FOR UPDATE;

    IF v_status = 'CANCELLED' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_ALREADY_CANCELLED';
    END IF;

    IF v_status = 'COMPLETED' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'APPOINTMENT_ALREADY_COMPLETED';
    END IF;

    SELECT COUNT(*)
    INTO v_doctor_count
    FROM doctors
    WHERE id = v_doctor_id;

    IF v_doctor_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_NOT_FOUND';
    END IF;

    -- Same doctor-level lock used by new bookings.
    SELECT is_active
    INTO v_doctor_active
    FROM doctors
    WHERE id = v_doctor_id
    FOR UPDATE;

    IF v_doctor_active = FALSE THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'DOCTOR_INACTIVE';
    END IF;

    SET v_new_end_at_utc = DATE_ADD(
        p_new_start_at_utc,
        INTERVAL 30 MINUTE
    );

    SET v_local_start = CONVERT_TZ(
        p_new_start_at_utc,
        '+00:00',
        '+03:00'
    );

    SET v_local_end = CONVERT_TZ(
        v_new_end_at_utc,
        '+00:00',
        '+03:00'
    );

    SELECT COUNT(*)
    INTO v_schedule_count
    FROM doctor_working_hours
    WHERE doctor_id = v_doctor_id
      AND weekday_iso = WEEKDAY(DATE(v_local_start)) + 1
      AND is_active = TRUE
      AND TIME(v_local_start) >= start_time
      AND TIME(v_local_end) <= end_time;

    IF v_schedule_count = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'OUTSIDE_WORKING_HOURS';
    END IF;

    SELECT COUNT(*)
    INTO v_conflict_count
    FROM appointments
    WHERE doctor_id = v_doctor_id
      AND status = 'BOOKED'
      AND id <> p_appointment_id
      AND start_at_utc < v_new_end_at_utc
      AND end_at_utc > p_new_start_at_utc;

    IF v_conflict_count > 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'SLOT_ALREADY_BOOKED';
    END IF;

    UPDATE appointments
    SET
        start_at_utc = p_new_start_at_utc,
        end_at_utc = v_new_end_at_utc
    WHERE id = p_appointment_id;

    COMMIT;

    SELECT
        id AS appointment_id,
        patient_id,
        doctor_id,
        start_at_utc,
        end_at_utc,
        status
    FROM appointments
    WHERE id = p_appointment_id;
END$$


-- =========================================================
-- 5. PATIENT APPOINTMENT HISTORY
--
-- p_upcoming_only:
--   TRUE  = future BOOKED appointments only
--   FALSE = all appointments
--
-- Results are ordered chronologically.
-- =========================================================

CREATE PROCEDURE sp_get_patient_appointments(
    IN p_patient_id BIGINT UNSIGNED,
    IN p_upcoming_only BOOLEAN
)
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM patients
        WHERE id = p_patient_id
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_NOT_FOUND';
    END IF;

    SELECT
        a.id AS appointment_id,
        a.patient_id,
        a.doctor_id,
        d.first_name AS doctor_first_name,
        d.last_name AS doctor_last_name,
        a.start_at_utc,
        a.end_at_utc,
        a.status,
        a.cancellation_reason,
        a.cancelled_at_utc,
        a.created_at_utc
    FROM appointments a
    INNER JOIN doctors d
        ON d.id = a.doctor_id
    WHERE a.patient_id = p_patient_id
      AND (
          p_upcoming_only = FALSE
          OR (
              a.status = 'BOOKED'
              AND a.start_at_utc >= UTC_TIMESTAMP()
          )
      )
    ORDER BY a.start_at_utc ASC, a.id ASC;
END$$

DELIMITER ;



DELIMITER //

DROP PROCEDURE IF EXISTS sp_update_patient//

CREATE PROCEDURE sp_update_patient(
    IN p_patient_id BIGINT UNSIGNED,
    IN p_update_first_name BOOLEAN,
    IN p_first_name VARCHAR(100),
    IN p_update_last_name BOOLEAN,
    IN p_last_name VARCHAR(100),
    IN p_update_email BOOLEAN,
    IN p_email VARCHAR(255),
    IN p_update_phone BOOLEAN,
    IN p_phone VARCHAR(30)
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;
    DECLARE v_email VARCHAR(255);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_patient_id IS NULL OR p_patient_id = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_PATIENT_ID';
    END IF;

    SELECT COUNT(*)
    INTO v_exists
    FROM patients
    WHERE id = p_patient_id;

    IF v_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_NOT_FOUND';
    END IF;

    IF p_update_first_name = 1
       AND (p_first_name IS NULL OR TRIM(p_first_name) = '') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_FIRST_NAME';
    END IF;

    IF p_update_last_name = 1
       AND (p_last_name IS NULL OR TRIM(p_last_name) = '') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_LAST_NAME';
    END IF;

    IF p_update_email = 1
       AND (p_email IS NULL OR TRIM(p_email) = '') THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_EMAIL';
    END IF;

    SET v_email = LOWER(TRIM(p_email));

    IF p_update_email = 1 AND EXISTS (
        SELECT 1
        FROM patients
        WHERE email = v_email
          AND id <> p_patient_id
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_EMAIL_EXISTS';
    END IF;

    START TRANSACTION;

    UPDATE patients
    SET
        first_name = CASE
            WHEN p_update_first_name = 1 THEN TRIM(p_first_name)
            ELSE first_name
        END,
        last_name = CASE
            WHEN p_update_last_name = 1 THEN TRIM(p_last_name)
            ELSE last_name
        END,
        email = CASE
            WHEN p_update_email = 1 THEN v_email
            ELSE email
        END,
        phone = CASE
            WHEN p_update_phone = 1 THEN NULLIF(TRIM(p_phone), '')
            ELSE phone
        END
    WHERE id = p_patient_id;

    COMMIT;

    SELECT
        id AS patient_id,
        first_name,
        last_name,
        email,
        phone,
        is_active,
        created_at,
        updated_at
    FROM patients
    WHERE id = p_patient_id;
END//

DELIMITER ;

DELIMITER //

DROP PROCEDURE IF EXISTS sp_deactivate_patient//

CREATE PROCEDURE sp_deactivate_patient(
    IN p_patient_id BIGINT UNSIGNED
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_patient_id IS NULL OR p_patient_id = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_PATIENT_ID';
    END IF;

    START TRANSACTION;

    SELECT COUNT(*)
    INTO v_exists
    FROM patients
    WHERE id = p_patient_id
    FOR UPDATE;

    IF v_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_NOT_FOUND';
    END IF;

    UPDATE patients
    SET is_active = 0
    WHERE id = p_patient_id;

    COMMIT;

    SELECT
        id AS patient_id,
        first_name,
        last_name,
        email,
        phone,
        is_active,
        created_at,
        updated_at
    FROM patients
    WHERE id = p_patient_id;
END//

DELIMITER ;


DELIMITER //

DROP PROCEDURE IF EXISTS sp_activate_patient//

CREATE PROCEDURE sp_activate_patient(
    IN p_patient_id BIGINT UNSIGNED
)
BEGIN
    DECLARE v_exists INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    IF p_patient_id IS NULL OR p_patient_id = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_PATIENT_ID';
    END IF;

    START TRANSACTION;

    SELECT COUNT(*)
    INTO v_exists
    FROM patients
    WHERE id = p_patient_id
    FOR UPDATE;

    IF v_exists = 0 THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_NOT_FOUND';
    END IF;

    UPDATE patients
    SET is_active = 1
    WHERE id = p_patient_id;

    COMMIT;

    SELECT
        id AS patient_id,
        first_name,
        last_name,
        email,
        phone,
        is_active,
        created_at,
        updated_at
    FROM patients
    WHERE id = p_patient_id;
END//

DELIMITER ;