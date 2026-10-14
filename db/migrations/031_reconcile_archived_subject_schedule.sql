-- Reconcile legacy schedule rows created before subject_id was required.
-- Archived subjects must not remain visible in Calendar.
UPDATE schedule sc
SET is_active = FALSE
FROM subjects sub
WHERE sc.is_active = TRUE
  AND sub.is_active = FALSE
  AND (
      sc.subject_id = sub.id
      OR (sc.subject_id IS NULL AND LOWER(TRIM(sc.subject_name)) = LOWER(TRIM(sub.name)))
  );

-- Restore the relation for unambiguous legacy rows that belong to active subjects.
UPDATE schedule sc
SET subject_id = sub.id
FROM subjects sub
WHERE sc.subject_id IS NULL
  AND sub.is_active = TRUE
  AND LOWER(TRIM(sc.subject_name)) = LOWER(TRIM(sub.name));
