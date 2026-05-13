-- Add projectId and projectTaskId to attendanceWorkLog table
ALTER TABLE "attendanceWorkLog" 
ADD COLUMN "projectId" VARCHAR(36),
ADD COLUMN "projectTaskId" VARCHAR(36);

-- Add indexes for better query performance
CREATE INDEX IF NOT EXISTS "attendanceWorkLog_projectId_idx" ON "attendanceWorkLog"("projectId");
CREATE INDEX IF NOT EXISTS "attendanceWorkLog_projectTaskId_idx" ON "attendanceWorkLog"("projectTaskId");

-- Add foreign key constraints (optional, but recommended)
-- ALTER TABLE "attendanceWorkLog" 
-- ADD CONSTRAINT "attendanceWorkLog_projectId_fkey" 
-- FOREIGN KEY ("projectId") REFERENCES "project"("id") ON DELETE SET NULL;

-- ALTER TABLE "attendanceWorkLog" 
-- ADD CONSTRAINT "attendanceWorkLog_projectTaskId_fkey" 
-- FOREIGN KEY ("projectTaskId") REFERENCES "project_task"("id") ON DELETE SET NULL;
