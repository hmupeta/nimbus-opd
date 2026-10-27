-- Create the app role (non-owner for RLS enforcement)
CREATE ROLE opd_app LOGIN PASSWORD 'opd_app';
GRANT USAGE ON SCHEMA public TO opd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE opd_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO opd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE opd_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO opd_app;
