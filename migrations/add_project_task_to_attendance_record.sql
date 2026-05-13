ALTER TABLE "attendanceRecord"
ADD COLUMN IF NOT EXISTS "projectId" VARCHAR(36),
ADD COLUMN IF NOT EXISTS "projectTaskId" VARCHAR(36),
ADD COLUMN IF NOT EXISTS "description" VARCHAR(1000);

CREATE INDEX IF NOT EXISTS "attendanceRecord_projectId_idx"
ON "attendanceRecord"("projectId");

CREATE INDEX IF NOT EXISTS "attendanceRecord_projectTaskId_idx"
ON "attendanceRecord"("projectTaskId");
