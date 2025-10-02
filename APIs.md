# API Overview

All routes are rooted at `http://localhost:8000`. Unless noted otherwise responses are JSON.

## Health
- `GET /api/ping` — simple health probe

## Reference data
- `GET /api/shifts` — list shift definitions
- `GET /api/rules/expected` — expected staffing counts for the selected month (`year`, `month` query params)

## Staff
- `GET /api/staff` — list staff records
- `POST /api/staff` — create staff (`full_name`, `role`, `can_night`, `base_quota`, `notes`)
- `DELETE /api/staff/{id}` — remove staff

## Fixed assignments
- `GET /api/fixed` — list fixed assignments for the month (`year`, `month` query params)
- `POST /api/fixed` — create fixed assignment (`staff_id`, `day`, `shift_code`, optional `position`)
- `PUT /api/fixed/{id}` — update fixed assignment
- `DELETE /api/fixed/{id}` — delete fixed assignment

## Off days
- `GET /api/off` — list off days (`year`, `month` query params)
- `POST /api/off` — create off day (`staff_id`, `day`, optional `reason`)
- `DELETE /api/off/{id}` — delete off day
- Legacy aliases also exist under `/api/offdays`

## Holidays
- `GET /api/holidays` — list holidays (`year` required, optional `month` filter)
- `POST /api/holidays` — create holiday (`day`, `name`, optional `kind`, `official`, `source`)
- `PUT /api/holidays/{id}` — update holiday metadata/day
- `DELETE /api/holidays/{id}` — delete holiday
- `POST /api/holidays/import?year=YYYY&source=nager` — import official VN holidays from Nager.Date

## Schedule and assignments
- `GET /api/assignments` — list generated assignments for the month (`year`, `month`)
- `GET /api/schedule/validate` — validate current schedule data for the month
- `GET /api/schedule/estimate` — estimator for staffing expectations
- `POST /api/schedule/generate` — run the scheduler (`year`, `month`, optional `shuffle`, `seed`, `save`, `fill_hc`)

## Admin
- `POST /api/admin/reset?mode=soft|hard` — soft delete assignments or recreate the SQLite database

## Export
- `GET /api/export_audit` — CSV stream of assignments with JSON metadata (accepts `year`, `month`)
- `GET /api/export/month.csv` — CSV stream of the monthly schedule (accepts `year`, `month`)

