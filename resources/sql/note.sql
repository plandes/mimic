---- free text notes

-- meta=init_sections=noop

-- name=noop
select 1;

-- name=categories
select distinct category from noteevents order by category;

-- name=select_discharge_categories
select distinct(description)
    from noteevents
    where category = 'Discharge summary';

-- name=select_note_text_by_id
select text from noteevents where row_id = %s;

-- name=select_note_by_id
select ${cols} from noteevents where row_id = %s;

-- name=select_notes_by_hadm_id
select ${cols} from noteevents where hadm_id = %s;

-- name=select_row_ids_by_hadm_id
select row_id from noteevents where hadm_id = %s;

-- name=select_categories_by_hadm_ids
select hadm_id, row_id, category from noteevents where hadm_id in %s;

-- name=select_hadm_id_by_row_id
select hadm_id from noteevents where row_id = %s;

-- name=select_keys
select row_id from noteevents;

-- name=select_hadm_row_id_category
select hadm_id, row_id, category from noteevents;

-- name=select_notes_by_category
select ${cols}
    from noteevents
    where category = %s and hadm_id is not null
    order by description
    limit %s;

-- name=select_discharge_reports
select ${cols}
    from noteevents
    where category = 'Discharge summary' and
          description = 'Report' and
          hadm_id is not null
    order by description
    limit %s;

-- name=select_note_count
select count(*) from noteevents where hadm_id = %s;

-- name=select_note_count_by_subject_id
select hadm_id, count(hadm_id) as cnt
    from noteevents
    where subject_id = %s and hadm_id is not null
    group by hadm_id
    order by cnt desc;

-- name=note_count
select count(*) from noteevents;

-- name=missing_hadm_count
select count(*) from noteevents where hadm_id is null;

-- name=total_count
select count(*) from noteevents;

-- name=random_hadm
select hadm_id from noteevents
    where hadm_id is not null
    order by random()
    limit %s;
