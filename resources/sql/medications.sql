---- chart events
-- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4878278/

-- name=prescriptions_by_hadm_id
select * from prescriptions
    where hadm_id = %s;
