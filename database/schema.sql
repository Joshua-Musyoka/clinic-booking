
CREATE DATABASE IF NOT EXISTS savanaclinic_booking
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'savanaclinic_user'@'127.0.0.1'
    IDENTIFIED BY 'savannaH.2026';

GRANT ALL PRIVILEGES
    ON savanaclinic_booking.*
    TO 'savanaclinic_user'@'127.0.0.1';

FLUSH PRIVILEGES;     

USE savanaclinic_booking;


-- =========================================================
-- 1. DOCTORS
-- =========================================================

CREATE TABLE IF NOT EXISTS doctors (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_doctors_email (email),
    KEY idx_doctors_active (is_active)
) ENGINE=InnoDB;


-- =========================================================
-- 2. PATIENTS
-- =========================================================

CREATE TABLE IF NOT EXISTS patients (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(30) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_patients_email (email),
    KEY idx_patients_active (is_active)
) ENGINE=InnoDB;


-- =========================================================
-- 3. DOCTOR WORKING HOURS
--
-- weekday_iso:
--   1 = Monday
--   2 = Tuesday
--   3 = Wednesday
--   4 = Thursday
--   5 = Friday
--   6 = Saturday
--   7 = Sunday
--
-- Working hours are clinic-local times.
-- Overnight shifts are intentionally unsupported.
-- =========================================================

CREATE TABLE IF NOT EXISTS doctor_working_hours (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    doctor_id BIGINT UNSIGNED NOT NULL,
    weekday_iso TINYINT UNSIGNED NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_doctor_weekday (
        doctor_id,
        weekday_iso
    ),
    CONSTRAINT fk_working_hours_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES doctors (id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT chk_working_hours_weekday
        CHECK (weekday_iso BETWEEN 1 AND 7),
    CONSTRAINT chk_working_hours_range
        CHECK (start_time < end_time),
    KEY idx_working_hours_lookup (
        doctor_id,
        weekday_iso,
        is_active
    )
) ENGINE=InnoDB;


-- =========================================================
-- 4. APPOINTMENTS
--
-- start_at_utc and end_at_utc are UTC DATETIME values.
-- DATETIME does not retain timezone information, so the
-- application and stored procedures must use UTC consistently.
--
-- Only BOOKED appointments reserve a slot.
-- CANCELLED and COMPLETED appointments do not reserve it.
-- =========================================================

CREATE TABLE IF NOT EXISTS appointments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    patient_id BIGINT UNSIGNED NOT NULL,
    doctor_id BIGINT UNSIGNED NOT NULL,
    start_at_utc DATETIME NOT NULL,
    end_at_utc DATETIME NOT NULL,
    status ENUM(
        'BOOKED',
        'CANCELLED',
        'COMPLETED'
    ) NOT NULL DEFAULT 'BOOKED',
    cancellation_reason VARCHAR(500) NULL,
    cancelled_at_utc DATETIME NULL,
    created_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    -- Cancelled appointments no longer reserve their old slot.
    -- MySQL unique indexes permit multiple NULL values.
    active_start_at_utc DATETIME
        GENERATED ALWAYS AS (
            CASE
                WHEN status = 'BOOKED' THEN start_at_utc
                ELSE NULL
            END
        ) STORED,
    PRIMARY KEY (id),
    CONSTRAINT fk_appointments_patient
        FOREIGN KEY (patient_id)
        REFERENCES patients (id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT fk_appointments_doctor
        FOREIGN KEY (doctor_id)
        REFERENCES doctors (id)
        ON DELETE RESTRICT
        ON UPDATE RESTRICT,
    CONSTRAINT chk_appointment_duration
        CHECK (
            end_at_utc = DATE_ADD(
                start_at_utc,
                INTERVAL 30 MINUTE
            )
        ),
    UNIQUE KEY uq_doctor_active_slot (
        doctor_id,
        active_start_at_utc
    ),
    KEY idx_appointments_patient_history (
        patient_id,
        start_at_utc
    ),
    KEY idx_appointments_doctor_schedule (
        doctor_id,
        start_at_utc,
        end_at_utc,
        status
    ),
    KEY idx_appointments_status (
        status,
        start_at_utc
    )
) ENGINE=InnoDB;


DELIMITER //

DROP PROCEDURE IF EXISTS sp_create_patient//

CREATE PROCEDURE sp_create_patient(
    IN p_first_name VARCHAR(100),
    IN p_last_name VARCHAR(100),
    IN p_email VARCHAR(255),
    IN p_phone VARCHAR(30)
)
BEGIN
    DECLARE v_patient_id BIGINT UNSIGNED;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    SET p_first_name = TRIM(p_first_name);
    SET p_last_name = TRIM(p_last_name);
    SET p_email = LOWER(TRIM(p_email));
    SET p_phone = NULLIF(TRIM(p_phone), '');

    IF p_first_name IS NULL OR p_first_name = '' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_FIRST_NAME';
    END IF;

    IF p_last_name IS NULL OR p_last_name = '' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_LAST_NAME';
    END IF;

    IF p_email IS NULL OR p_email = '' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'INVALID_EMAIL';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM patients
        WHERE email = p_email
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'PATIENT_EMAIL_EXISTS';
    END IF;

    START TRANSACTION;

    INSERT INTO patients (
        first_name,
        last_name,
        email,
        phone
    )
    VALUES (
        p_first_name,
        p_last_name,
        p_email,
        p_phone
    );

    SET v_patient_id = LAST_INSERT_ID();

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
    WHERE id = v_patient_id;
END//

DELIMITER ;