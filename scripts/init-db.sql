-- Initial database setup script
-- This runs when the database container starts for the first time

-- Create extensions if they don't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Create custom types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('intern', 'mentor', 'admin', 'hr');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE intern_status AS ENUM ('pending', 'active', 'completed', 'suspended');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE task_status AS ENUM ('assigned', 'in_progress', 'submitted', 'under_review', 'completed', 'revision_required');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create indexes for better performance
-- Note: These will be managed by Alembic migrations, but included here for reference

-- Text search indexes
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_search ON users USING gin(to_tsvector('english', first_name || ' ' || last_name || ' ' || email));
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_search ON tasks USING gin(to_tsvector('english', title || ' ' || description));

-- Performance indexes
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_assigned_intern ON tasks(assigned_intern_id) WHERE status IN ('assigned', 'in_progress');
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_learning_progress_intern ON learning_progress(intern_id, module_id);
