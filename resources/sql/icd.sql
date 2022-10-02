---- ICD-9 codes for diagnosis and procedures

-- meta=init_sections=noop

-- name=noop
select 1;

-- metadata
shtab diagnoses_icd

-- name=select_diagnosis_by_hadm_id
select d.row_id, d.icd9_code, id.short_title, id.long_title
    from diagnoses_icd as d,
         d_icd_diagnoses as id
    where d.icd9_code = id.icd9_code and d.hadm_id = %s
    order by hadm_id, seq_num;

-- name=select_procedure_by_hadm_id
select d.row_id, d.icd9_code, id.short_title, id.long_title
    from procedures_icd as d,
         d_icd_procedures as id
    where d.icd9_code = id.icd9_code and d.hadm_id = %s
    order by hadm_id, seq_num;

-- name=select_heart_failure_hadm_id
select distinct(d.hadm_id)
    from diagnoses_icd as d
    where d.icd9_code like '428%%';

-- 13,608 hospital admissions with 482,457 notes for heart failure
select count(*) from noteevents
    where hadm_id in (
	select distinct(d.hadm_id)
	    from diagnoses_icd as d
	    where d.icd9_code like '428%');

-- heart failure ICD9s
select d.row_id, d.hadm_id, d.icd9_code, id.short_title, id.long_title
    from diagnoses_icd as d,
         d_icd_diagnoses as id
    where d.icd9_code = id.icd9_code and d.icd9_code like '428%'
    order by hadm_id, seq_num;
