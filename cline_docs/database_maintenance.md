# Database Maintenance and Backup Strategy

## Critical Rules
1. NEVER drop or modify production tables without:
   - Full backup
   - User confirmation
   - Rollback plan
   - Testing in staging first
2. ALWAYS maintain at least 3 backup copies:
   - Daily automated backup
   - Pre-migration backup
   - Weekly full backup
3. ALWAYS test restore procedures regularly
4. NEVER store sensitive data in git repository

## Backup Types and Schedule

### 1. Automated Daily Backups
```bash
# Create timestamped backup
pg_dump -U [user] -d [database] -F p -f backup_$(date +%Y%m%d_%H%M%S)_daily.sql

# Retain last 7 days
find . -name "backup_*_daily.sql" -mtime +7 -delete
```

### 2. Pre-Migration Backups
```bash
# Before any migration
pg_dump -U [user] -d [database] -F p -f backup_$(date +%Y%m%d_%H%M%S)_pre_migration.sql

# Include in migration PR/commit message:
- Backup filename
- Rollback steps
- Testing steps performed
```

### 3. Weekly Full Backups
```bash
# Full backup with schema and data
pg_dump -U [user] -d [database] -F p -f backup_$(date +%Y%m%d_%H%M%S)_full.sql
```

## Restore Procedure

### 1. Prerequisites
- Stop application server
- Verify database connection settings
- Check disk space (need 2x backup size)

### 2. Restore Steps
```bash
# Create fresh database if needed
createdb -U [user] [database]

# Restore from backup
psql -U [user] -d [database] -f [backup_file].sql

# Verify data integrity
python manage.py check
python manage.py showmigrations
```

### 3. Post-Restore Verification
- Check record counts match backup
- Verify application functionality
- Test critical features
- Check logs for errors

## Migration Safety

### 1. Pre-Migration
- Create backup
- Document current state
- Test migration in staging
- Prepare rollback plan

### 2. During Migration
- Execute in maintenance window
- Follow step-by-step checklist
- Log all actions
- Keep backup readily available

### 3. Post-Migration
- Verify data integrity
- Test application functionality
- Monitor for issues
- Keep backup for 30 days

## Required Files for Bare Metal Restore

1. Database Files:
   - Latest full backup SQL file
   - Migration history
   - Sequence reset scripts

2. Application Files:
   - All Django migrations
   - Environment variables template
   - Requirements.txt with versions
   - Setup scripts

3. Configuration:
   - Database connection settings
   - Server configuration
   - Environment-specific settings

## Best Practices for Development

1. Version Control:
   - Never commit sensitive data
   - Use .gitignore for backups
   - Document database changes

2. Testing:
   - Test migrations with sample data
   - Verify rollback procedures
   - Maintain test database

3. Documentation:
   - Keep README updated
   - Document restore procedures
   - Maintain change log

## Emergency Recovery

1. Immediate Actions:
   - Stop affected services
   - Create emergency backup
   - Document current state
   - Contact stakeholders

2. Recovery Steps:
   - Restore latest backup
   - Apply missing transactions
   - Verify data integrity
   - Test functionality

3. Post-Recovery:
   - Document incident
   - Update procedures
   - Implement preventive measures

## Monitoring and Maintenance

1. Regular Checks:
   - Database size
   - Backup success
   - Performance metrics
   - Error logs

2. Cleanup:
   - Remove old backups
   - Archive unused data
   - Optimize tables
   - Update statistics

3. Security:
   - Audit access logs
   - Review permissions
   - Update credentials
   - Check for vulnerabilities 