---- patient data

-- meta=init_sections=noop

-- name=noop
select 1;

-- metadata
shtab patients

-- name=select_patient_by_id
select ${cols} from patients where row_id = ?;

-- name=select_patient_by_subject_id
select ${cols} from patients where subject_id = ?;

-- name=patient_count
select count(*) from patients;
