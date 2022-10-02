---- admissions (new check ins to the hospital)

-- meta=init_sections=noop

-- name=noop
select 1;

-- metadata
shtab admissions

-- name=select_admission_by_id
select ${cols} from admissions where row_id = %s;

-- name=select_admission_by_hadm_id
select ${cols} from admissions where hadm_id = %s;

-- name=select_admission_by_subject_id
select ${cols} from admissions where subject_id = %s;

-- name=select_hadm_for_subject_id
select hadm_id from admissions where subject_id = %s;

-- name=admission_count
select count(*) from admissions;

-- name=select_admission_counts
select subject_id, count(subject_id) as cnt from admissions
    group by subject_id
    order by cnt desc
    limit %s;

-- name=hadm_ids
select hadm_id from admissions;

-- name=select_hadm_id_exists
select count(*) from admissions where hadm_id = %s;

-- get all noteevent IDs for heart patients
select n.row_id, a.hadm_id, a.subject_id
    from admissions as a,
	 noteevents as n
	 where n.hadm_id = a.hadm_id and
	       a.diagnosis in (
	  select distinct(diagnosis)
	      from admissions
	      where diagnosis like '%HEART%' or diagnosis like '%CARDIAC%')
    order by a.subject_id, a.hadm_id;

-- count subjects
select distinct(a.subject_id)
    from admissions as a,
	 noteevents as n
	 where n.hadm_id = a.hadm_id and
	       a.diagnosis in (
	  select distinct(diagnosis)
	      from admissions
	      where diagnosis like '%HEART%' or diagnosis like '%CARDIAC%');

-- test
select * from admissions where subject_id=13033;
