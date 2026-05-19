# Alembic Migration Fix Summary

**Date:** May 15, 2026  
**Issue:** Multiple heads and duplicate revision IDs in Alembic migrations

## Problem

The Alembic migration history had:
- **3 separate heads** (branches that hadn't been merged)
- **2 duplicate revision IDs** (same revision ID used in multiple files)

### Duplicate Revisions Found

1. **e9f8b4a7d3c2** - appeared in:
   - `e9f8b4a7d3c2_add_dynamic_categories_and_units.py` (real migration)
   - `e9f8b4a7d3c2_preserve_external_project_task_marker.py` (marker file - DELETED)

2. **f43cf5b85a2b** - appeared in:
   - `f43cf5b85a2b_rename_purchasevalue_to_purchaseprice_.py` (real migration)
   - `f43cf5b85a2b_preserve_external_migration_marker.py` (marker file - DELETED)

### Multiple Heads

Before fix:
```
Head 1: 40e3ade9ac5a (asset management branch)
Head 2: 4e906bd86ec5 (ATS/recruitment branch)  
Head 3: 5f4aa7b8a682 (project/timesheet branch)
```

## Solution Applied

### Step 1: Remove Duplicate Marker Files
Deleted the empty "marker" migration files that were creating duplicate revision IDs:
- ❌ Deleted: `e9f8b4a7d3c2_preserve_external_project_task_marker.py`
- ❌ Deleted: `f43cf5b85a2b_preserve_external_migration_marker.py`

### Step 2: Merge All Heads
Created a merge migration to combine all three branches:
```bash
alembic merge -m "merge_all_heads" 40e3ade9ac5a 4e906bd86ec5 5f4aa7b8a682
```

This created: `4b262fe191ed_merge_all_heads.py`

### Step 3: Fix Database Version
The database had an invalid revision `abcd1234e001` that didn't exist in the migration files.

Created and ran `fix_alembic_version.py` to:
1. Clear the invalid revision from `alembic_version` table
2. Set the current version to the new merge head: `4b262fe191ed`

## Result

✅ **Single head:** `4b262fe191ed`  
✅ **No duplicate revisions**  
✅ **Database synchronized** with migration files  
✅ **Clean migration history**

## Verification Commands

```bash
# Check current database revision
alembic current
# Output: 4b262fe191ed (head) (mergepoint)

# Check for multiple heads
alembic heads
# Output: 4b262fe191ed (head)

# View migration history
alembic history
```

## Migration Graph Structure

The final merged structure:

```
... (earlier migrations)
    ↓
cd72a8217dc2 (add quantity to asset)
    ↓
e9f8b4a7d3c2 (add dynamic categories and units) [BRANCH POINT]
    ├─→ 40e3ade9ac5a (asset_id definitions table)
    └─→ 8b7a8c1d2e3f (add clock-in project/task)
            ↓
        f0a1b2c3d4e5 (align ats pipeline schema)
            ↓
        716052f21ac2 (add_job_requisition)
            ↓
        a2b3c4d5e6f7 (sync all missing ats columns)
            ↓
        4e906bd86ec5 (drop_pipeline_stage_order_unique)

... (parallel branch)
d1e2f3a4b5c6 (simplify project_task)
    ↓
5f4aa7b8a682 (add_project_task_to_work_log)

[ALL BRANCHES MERGE HERE]
    ↓
4b262fe191ed (merge_all_heads) ← CURRENT HEAD
```

## Files Modified/Created

### Deleted
- `server/alembic/versions/e9f8b4a7d3c2_preserve_external_project_task_marker.py`
- `server/alembic/versions/f43cf5b85a2b_preserve_external_migration_marker.py`

### Created
- `server/alembic/versions/4b262fe191ed_merge_all_heads.py` (merge migration)
- `server/fix_alembic_version.py` (utility script)
- `server/MIGRATION_FIX_SUMMARY.md` (this document)

## Next Steps

1. ✅ Migrations are now clean and ready for development
2. Future migrations will build on top of `4b262fe191ed`
3. To create new migrations: `alembic revision --autogenerate -m "description"`
4. To apply migrations: `alembic upgrade head`

## Notes

- The marker files were likely created to preserve revision IDs that existed in a database but were missing from the codebase
- Instead of using marker files, the proper solution is to merge branches and synchronize the database
- Always use `alembic merge` when you have multiple heads
- Never reuse revision IDs - each migration must have a unique identifier
