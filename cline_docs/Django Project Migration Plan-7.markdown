# Django Project Migration Plan

## Current State Analysis

### Issues to Address
1. ~~Nested Django projects causing import path confusion~~ (Resolved in test instance)
2. ~~Multiple PostgreSQL instances (ports 5432, 5433) with inconsistent connections~~ (Test instance uses single DB)
3. No clear separation between dev and prod environments
4. Manual database management without proper backup procedures
5. Complex directory structure making maintenance difficult

### Critical Data to Preserve
1. Database contents from test instance (clean, squashed migrations)
2. Migration history (from test instance)
3. Custom application code (PDF extractor, transaction classification)
4. Configuration settings
5. Business rules and profiles
6. Static files (CSS/JS/images)

## Migration Strategy

### Option 1: New Repository (Recommended)
**Pros:**
- Clean slate without technical debt
- Proper structure from the start
- No risk of breaking existing functionality
- Clear separation of concerns
- Leverages test instance's clean migrations

**Cons:**
- Requires careful data migration
- Temporary loss of git history
- Additional setup time

### Recommended Approach: New Repository

### Phase 1: Preparation
1. **Document Current State**:
   - Map database schema from test instance
   - Document custom configurations (`settings.py`, environment variables)
   - List dependencies (`pip freeze > requirements.txt`) and compare with v8 guide's `requirements/base.txt` and `requirements/dev.txt`
   - Document business rules (PDF extraction logic, transaction classification)
   - Identify static files and their locations

2. **Create Backup Strategy**:
   - Backup test instance database:
     ```bash
     pg_dump -U <user> -d <db_name> -Fc --clean > test_db.dump
     ```
   - Validate backup integrity:
     ```bash
     pg_restore --list test_db.dump > dump_contents.txt
     grep -c "TABLE DATA" dump_contents.txt  # Verify tables exist
     grep -c "public.auth_user" dump_contents.txt  # Verify critical tables
     ```
   - Export configuration files
   - Document environment variables
   - **Note**: Backups are copied nightly to `$BACKUP_S3_BUCKET/pdf-extractor/` via `aws s3 cp` or a secure local directory with offsite syncing

3. **Create Performance Baseline**:
   - Measure current PDF processing performance:
     ```bash
     time python manage.py process_sample_pdf > baseline_performance.txt
     ```
   - Document database query times for key operations
   - Record current resource usage (memory, CPU)

4. **Create Rollback Plan**:
   - Document DNS/endpoint configuration for quick reversal
   - Create rollback script:
     ```bash
     # rollback.sh
     #!/bin/bash
     echo "Reverting to original system..."
     # 1. Restore DNS/endpoints to original system
     # 2. Ensure original system is still running
     echo "Rollback complete. Verify system functionality."
     ```
   - Test rollback procedure in isolation

5. **Start Migration Log**:
   - Create a migration log document:
     ```
     # Migration Log
     
     ## Pre-Migration
     - [Date] Initial state documented
     - [Date] Backups created and verified
     - [Date] Performance baseline established
     ```

### Phase 2: New Repository Setup
1. **Initialize New Repository**:
   ```bash
   mkdir pdf-extractor-new
   cd pdf-extractor-new
   git init
   git checkout --orphan initial
   echo "MIT License" > LICENSE
   git add LICENSE
   git commit -m "Initial commit with LICENSE"
   git switch -c develop
   ```

2. **Set Up Docker Environment**:
   - Implement basic Docker workflow with single `docker-compose.yml`
   - Use environment variables to toggle dev/prod settings (e.g., `DEBUG`, `DATABASE_URL`)
   - Set up health checks for Postgres:
     ```yaml
     healthcheck:
       test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
       interval: 5s
       retries: 5
     ```
   - Use `Makefile` shortcuts (`make up`, `make collect`, `make logs`)

3. **Migrate Code**:
   - Copy core application code from test instance
   - Update import paths to match new `app/` structure
   - Implement settings structure with `django-environ`
   - Copy static files to `app/static/`
   - For local dev, install `requirements/base.txt` and `requirements/dev.txt` separately; Docker handles dependencies via the `Dockerfile`

### Phase 3: Data Migration
1. **Database Migration**:
   - Create new PostgreSQL instance
   - Migrate data from test instance:
     ```bash
     cat test_db.dump | docker exec -i pdf-prod_postgres_1 pg_restore -U user -d db --clean --no-owner --no-privileges --exit-on-error
     ```
   - Validate data integrity (e.g., row counts, transaction records)
   - Set up basic backup procedures

2. **Configuration Migration**:
   - Migrate environment variables to `.env`
   - Update Django settings per v8 guide
   - Configure database connection
   - Set up basic logging

3. **Static Files Migration**:
   - Copy static files from test instance to `app/static/`
   - Run:
     ```bash
     docker compose -p pdf-prod exec django python manage.py collectstatic --noinput
     ```
   - Validate static file serving

4. **Update Migration Log**:
   ```
   ## Data Migration
   - [Date] Database migrated to new system
   - [Date] Table count: X tables successfully migrated
   - [Date] Configuration files migrated
   - [Date] Static files migrated
   ```

### Phase 4: Testing & Validation
1. **Functional Testing**:
   - Test core features (PDF extraction, transaction classification)
   - Verify data integrity using Adminer (`http://localhost:8081`)
   - Check import/export functionality
   - Validate business rules
   - If a cache backend env var is set (e.g., `CACHE_URL`), verify cache hits; otherwise skip
   - Create superuser:
     ```bash
     docker compose -p pdf-prod exec django python manage.py createsuperuser
     ```
   - Verify CSS/JS load in container

2. **Performance Testing**:
   - Check database performance (e.g., query response times)
   - Verify container health (`docker inspect`)
   - Test backup/restore procedures:
     ```bash
     cat prod_<timestamp>.dump | docker exec -i pdf-prod_postgres_1 pg_restore -U user -d db --clean --no-owner --no-privileges --exit-on-error
     ```
   - Compare with baseline performance:
     ```bash
     time python manage.py process_sample_pdf > new_performance.txt
     diff baseline_performance.txt new_performance.txt
     ```

3. **Automated Testing**:
   - Set up basic `pytest` for core features (e.g., PDF upload, transaction classification)
   - Write smoke tests to validate basic functionality

4. **Update Migration Log**:
   ```
   ## Testing & Validation
   - [Date] Core functionality verified
   - [Date] Data integrity confirmed
   - [Date] Performance testing: X% improvement/degradation
   - [Date] Automated tests: X passing, Y skipped
   ```

### Phase 5: Transition Plan
1. **Parallel Operation (2 days)**:
   - Run both systems in parallel
   - Perform at least one data sync:
     ```bash
     pg_dump -U <user> -d <db_name> -Fc --clean --if-exists --no-owner > sync_db.dump
     cat sync_db.dump | docker exec -i pdf-prod_postgres_1 pg_restore -U user -d db --clean --if-exists --no-owner --exit-on-error
     ```
   - Verify new system functionality
   - Compare results (e.g., transaction data, PDF outputs)
   - Document discrepancies
   - **Note**: For databases >1GB, consider `pglogical` or `pg_dump --data-only --inserts` post-migration to optimize syncs

2. **Cutover Strategy**:
   - Rehearse dump/restore in dev to estimate downtime (pad by 20%):
     ```bash
     time (cat test_db.dump | docker exec -i pdf-dev_postgres_1 pg_restore -U user -d db --clean --no-owner --no-privileges --exit-on-error)
     ```
   - Schedule maintenance window (e.g., 15-30 minutes)
   - Perform final data sync
   - Update Let's Encrypt/Cloudflare origin certificates if using a reverse proxy
   - Switch DNS/endpoints to the new system
   - Monitor with:
     ```bash
     docker compose -p pdf-prod logs -f django
     ```
   - Keep rollback script readily available during cutover

3. **Update Migration Log**:
   ```
   ## Transition
   - [Date] Parallel operation began
   - [Date] First data sync performed
   - [Date] Cutover performed (Start: XX:XX, End: XX:XX)
   - [Date] New system live
   ```

## Migration Timeline
**Note**: The four-day timeline assumes a database <1GB and no major schema issues. If unforeseen schema conflicts arise, Day 4 may extend by 1 day for fixes.

### Day 1: Preparation
- Document current state (schema, configs, dependencies, static files)
- Create backup and verify integrity
- Create performance baseline
- Prepare rollback plan
- Create migration log
- Set up new repository

### Day 2: Development
- Complete Docker setup
- Migrate core code and static files
- Begin data migration

### Day 3: Testing
- Complete data migration
- Functional and performance testing
- Set up basic `pytest`
- Bug fixes using Adminer and logs
- Compare with baseline performance

### Day 4: Transition
- Parallel operation (2 days)
- Final validation
- Cutover
- Maintain migration log

## Risk Mitigation

### Technical Risks
1. **Data Loss**:
   - Multiple backups (`test_db.dump`, sync dumps)
   - Validation checks (row counts, key records)
   - Rollback procedures (restore from dump)
   - Verified backup integrity

2. **Configuration Issues**:
   - Thorough testing in dev environment
   - Detailed documentation
   - Validation scripts for settings and dependencies
   - Migration log tracking changes

### Business Risks
1. **Downtime**:
   - Rehearsed maintenance window (15-30 minutes)
   - Clear communication plan
   - Rollback procedures
   - Documented rollback script

2. **Data Integrity**:
   - Validation procedures
   - Verification steps for transaction data
   - Performance comparison with baseline

## Success Criteria

### Technical
- All features working in new environment
- No data loss or corruption
- Proper backup/restore functionality (backup job completes ≤3 minutes per deploy)
- Clean import paths
- Correct static file serving
- PDF processing time <5 seconds per document (p95)
- Performance equal to or better than baseline

### Business
- No disruption to operations
- All reports generating correctly
- Business rules (e.g., PDF extraction, classification) functioning properly
- Performance maintained or improved
- Complete migration log documenting the process

## Next Steps

1. **Immediate Actions**:
   - Review and approve migration plan
   - Begin documentation of current state
   - Set up new repository
   - Start Docker configuration using v8 guide

2. **Required Resources**:
   - Development time (prioritize critical features like PDF extraction using `make up`, `make collect`)
   - Testing environment (dev container)
   - Backup storage (e.g., S3 bucket or local directory with offsite syncing)

3. **Dependencies**:
   - Team availability
   - Maintenance window approval
   - Stakeholder buy-in
   - Resource allocation

## Conclusion
The migration to the new Docker-based workflow provides:
- Clean, maintainable structure
- Proper database management with robust backups
- Streamlined deployment procedures
- Efficient development workflow

This simplified four-day plan leverages the test instance's clean state, ensuring a smooth transition with minimal risk. It's tailored for a solo developer, balancing speed with essential safeguards like dev/prod isolation, static file validation, and basic automated testing. If schema issues arise, a one-day buffer is included to address them.

The addition of backup validation, performance baselines, a detailed rollback plan, and a migration log provides extra layers of protection without significant overhead, ensuring both efficiency and safety throughout the migration process.