# Active Context

## Current Focus
Refining the transaction classification system to achieve the core goal: producing tax-ready Excel reports with transactions accurately separated into 6A, Auto, HomeOffice, and Personal worksheets, ensuring consistency through enhanced matching logic.

## Current State
- Successfully fixed agent separation issues
- Verified both Payee Lookup and Classification agents working correctly
- Created backup of current working state
- Updated system patterns with detailed agent documentation

## Recent Changes
1. Fixed Payee Lookup Agent:
   - Properly normalizing vendor names
   - Correctly using search tool
   - Returning all required fields
   - Not including store numbers/locations

2. Verified Classification Agent:
   - Using correct worksheet assignments
   - Proper category selection
   - Appropriate confidence levels
   - Detailed reasoning

3. Documented Agent Architecture:
   - Clear field separation
   - Development rules
   - Tool integration patterns

## Next Steps
1. Monitor agent performance for any regressions
2. Consider refactoring if frequent agent interaction issues occur
3. Keep documentation updated with any changes
4. Maintain strict field separation in future development

## Open Questions
None at this time - system is functioning as intended

## Current CLI Structure
1. Legacy System (scripts/grok.py):
   - Two-pass AI classification approach
   - Uses OpenAI assistants (AmeliaAI, DaveAI)
   - Batch processing with review workflow
   - Google Sheets integration

2. New Multi-Client System (dataextractai/cli/main.py):
   - Client management
   - Document processing
   - Basic categorization
   - Google Sheets setup/upload

## Next Steps
1. Test the caching system with real transaction data
2. Monitor cache effectiveness and hit rates
3. Consider adding cache statistics reporting
4. Evaluate performance improvements from caching
5. Consider adding cache cleanup/management features

6. Testing Tasks:
   - Test status tracking for each pass
   - Verify dependency enforcement
   - Test force processing functionality
   - Check status reset capabilities
   - Validate color-coded status display

7. Potential Improvements:
   - Add progress bars for batch processing
   - Add filtering options for status view
   - Add batch operations for status management
   - Enhance error reporting

### 1. Port Legacy Features
1. AI Processing:
   - Batch processing system
   - Multiple AI assistants support
   - Progress tracking per client
   - State management

2. Data Consolidation:
   - Batch merging
   - Data normalization
   - Year filtering
   - Transaction deduplication

3. Google Sheets Integration:
   - Client-specific sheet configuration
   - Category/Classification dropdowns
   - Sheet formatting
   - Data validation

### 2. CLI Consolidation
1. Phase out grok.py:
   - Document all features
   - Create migration path
   - Port unique functionality

2. Enhance main.py:
   - Add missing features
   - Improve error handling
   - Add progress tracking
   - Better logging

### 3. Testing & Documentation
1. Add comprehensive tests
2. Update documentation
3. Create migration guides
4. Add example configurations

### 4. Fix First Republic Bank parser issues
1. Parser is running but finding 0 transactions
2. Need to investigate date parsing in `first_republic_bank_parser.py`
3. Warning about date format "May 01, 2024 - May 24, 2024" not being parsed correctly
4. Verify PDF structure hasn't changed

### 5. Future Improvements
1. Add more comprehensive error handling in parsers
2. Improve logging for better debugging
3. Add unit tests for date parsing edge cases

## Current CLI Commands
```bash
# List all categories
python -m dataextractai.cli.main categories list <client_name>

# Add a new category
python -m dataextractai.cli.main categories add <client_name>

# Edit an existing category
python -m dataextractai.cli.main categories edit <client_name>

# Delete a category (by number or name)
python -m dataextractai.cli.main categories delete <client_name>

# Generate AI-suggested categories
python -m dataextractai.cli.main categories generate <client_name>
```

## Category Management Features
1. **List Categories**
   - Shows all categories with numbers
   - Displays system and custom categories
   - Shows descriptions and tax implications

2. **Add Categories**
   - Natural language input
   - AI-assisted formatting
   - System category matching
   - Tax implication suggestions

3. **Edit Categories**
   - Natural language updates
   - Side-by-side change preview
   - System category matching
   - Confidence level tracking

4. **Delete Categories**
   - Support for number or name input
   - Confirmation prompts
   - Category details preview

5. **Generate Categories**
   - Uses full business context
   - Industry-specific suggestions
   - Tax implication guidance
   - System category matching

## Current Work
- Fixed Payee Lookup agent functionality
- Restored Classification agent functionality
- Implemented proper prompt separation between agents
- Added detailed logging for debugging

## Current Status
1. Command-Line Version (Core)
   - Functional parser system
   - Working Google Sheets integration
   - Basic AI categorization
   - Recently added Wells Fargo CSV parser

2. Web Version (In Progress)
   - React frontend started
   - FastAPI backend framework
   - Database schema defined
   - File upload system working

## Known Issues
1. Parser System
   - Empty directory handling needs testing
   - Some parsers may need updates for new formats

2. AI Categorization
   - Needs testing with new parsers
   - May need optimization for large datasets

3. Google Sheets
   - Credentials setup needs documentation
   - Multi-client sheet management needed

## Current Challenges
1. Ensuring efficient file upload handling
2. Managing batch upload states
3. Implementing real-time status updates
4. Handling large files effectively

## Immediate Tasks
1. Design file upload component
2. Implement drag-and-drop interface
3. Add file validation
4. Create status tracking UI

## Legacy System (scripts/grok.py):
- Two-pass AI classification approach
- Uses OpenAI assistants (AmeliaAI, DaveAI)
- Batch processing with review workflow
- Google Sheets integration

## Current System:
- Modular parser architecture
- Transaction normalization
- Client profile management
- CLI and menu interfaces
- AI classifier system (in progress)

## Current Branch
- Working on `feature/db-transaction-tracking`
- Changes committed and pushed to GitHub
- Ready for testing 

## Future Enhancements

### Web Application
1. Transaction Management Interface
   - Real-time transaction viewing and editing
   - Status monitoring dashboard
   - Batch processing controls
   - Progress tracking visualization

2. Processing Controls
   - Ability to trigger reprocessing of transactions
   - Fine-grained control over which passes to run
   - Force processing options
   - Batch operation capabilities

### Intelligent Chatbot Assistant
1. Context-Aware Features
   - Full access to client profile and context
   - Historical transaction awareness
   - Understanding of business rules
   - Knowledge of tax implications

2. Natural Language Processing
   - Relationship understanding (e.g., identifying spouses, business partners)
   - Transaction pattern recognition
   - Rule-based modifications
   - Global change capabilities

3. Smart Adjustments
   - Target-based modifications (e.g., adjusting expense categories to meet targets)
   - Confidence-based filtering
   - Bulk updates with reasoning
   - Audit trail for changes

4. Integration Points
   - MCP interface for database updates
   - API access for transaction modifications
   - Real-time data validation
   - Change tracking and versioning

### Implementation Priorities
1. Core Web App
   - Basic CRUD operations
   - Authentication system
   - Real-time status updates
   - Basic reporting

2. Enhanced Processing
   - Web-based reprocessing
   - Progress monitoring
   - Error handling
   - Batch operations

3. Chatbot Integration
   - Basic query capabilities
   - Context understanding
   - Simple updates
   - Audit logging

4. Advanced Features
   - Complex relationship handling
   - Target-based adjustments
   - Pattern recognition
   - Bulk operations 

### Tax Workbook Management
1. Comprehensive Workbook Tracking
   - Schedule 6A (Core)
     * Transaction categorization and summaries
     * Business expense tracking
     * Tax implications calculation
   - Document Management
     * W-2 form attachments
     * 1099 form tracking (all types)
     * Supporting documentation upload
   - Manual Entry Sections
     * Additional income sources
     * Non-transaction deductions
     * Special calculations

2. Workbook Progress Dashboard
   - Section-by-section completion status
   - Required document checklist
   - Missing information alerts
   - Validation warnings
   - Cross-reference checks

3. Document Processing
   - OCR for form data extraction
   - Automatic form type detection
   - Data validation against IRS rules
   - Cross-form data consistency checks

4. Completion Tracking
   - Per-section progress tracking
   - Required vs optional fields
   - Data validation status
   - Supporting document status
   - Final review checklist

### Implementation Priorities
1. Core Schedule 6A (Current Focus)
   - Transaction processing
   - Business expense categorization
   - Tax category mapping
   - Summary calculations

2. Document Management
   - Document upload system
   - Form type detection
   - Basic data extraction
   - Storage and organization

3. Progress Tracking
   - Section completion status
   - Document checklist
   - Missing data alerts
   - Validation system

4. Advanced Features
   - OCR data extraction
   - Cross-form validation
   - Auto-calculations
   - Year-over-year comparison 

### QuickBooks Integration
1. Export Capabilities
   - IIF file generation for desktop QB
   - QBO format for QB Online
   - QBXML for direct integration
   - Batch export support

2. Data Mapping
   - Category to QB account mapping
   - Payee to vendor mapping
   - Business context to class mapping
   - Tax line mapping
   - Default mappings management

3. Validation & Verification
   - Account name validation
   - Required field checking
   - Amount format validation
   - Duplicate detection
   - Error reporting

4. Integration Features
   - Account list synchronization
   - Vendor list management
   - Class list management
   - Change tracking
   - Audit logging

### Implementation Priorities
1. Basic QB Export (Phase 1)
   - IIF file generation
   - Basic field mapping
   - Essential validation
   - Simple error handling

2. Enhanced Mapping (Phase 2)
   - Account mapping interface
   - Vendor synchronization
   - Class mapping system
   - Tax line mapping

3. Advanced Features (Phase 3)
   - Multiple format support
   - Conflict resolution
   - Batch processing
   - Error recovery

4. Direct Integration (Phase 4)
   - QB API integration
   - Real-time sync
   - Change tracking
   - Audit system 

## Current Task
Implemented stricter IRS-compliant business expense classification with:
- Default to personal (0% business) unless clear justification
- Confidence levels (high/medium/low) for review
- Documentation requirements in notes field
- Special handling for typically personal categories
- Cache management per pass type

## Technical Decisions
1. Moved business logic validation to Pass 2
2. Separated cache by pass_type
3. Enhanced prompt engineering for IRS compliance
4. Added confidence-based downgrades
5. Implemented documentation tracking

## Current Status
- Pass 2 running with stricter rules
- Default-to-personal working as intended
- Confidence levels properly assigned
- Documentation requirements captured
- Cache management improved 

# Active Development Context

## Current Task
Debugging transaction classifier caching mechanism in `dataextractai/agents/transaction_classifier.py`.

### Issue
- Cache mechanism in `_get_payee` method is not working effectively
- Initial implementation tried to use standardized payee names for cache keys
- Multiple attempts to fix have caused various issues including:
  - NoneType errors from accessing undefined variables
  - Control flow issues with cache checking
  - Inconsistent cache key generation

### Recent Changes
1. Attempted to use standardized payee names from LLM analysis for cache keys
2. Modified control flow to check cache earlier in process
3. Fixed variable scope and error handling
4. Implemented consistent cache key generation using `_get_cache_key` method

### Current State
- Code has been modified to:
  1. Check cache early with description-only key
  2. Use `_get_cache_key` consistently throughout
  3. Handle errors gracefully
  4. Cache results with appropriate payee names when available

### Next Steps
1. Verify cache effectiveness through logs
2. Ensure cache keys are consistent
3. Optimize cache hit rate for similar transactions
4. Consider additional improvements to caching strategy if needed

## Technical Details
Key methods involved:
- `_get_payee`: Main method for payee identification
- `_get_cache_key`: Generates cache keys from description/payee
- `_get_cached_result`: Retrieves cached results
- `_cache_result`: Stores results in cache

Cache key strategy:
1. First try with cleaned description
2. If standardized payee available, use that for more precise matching
3. Fall back to description-only if no standardized payee

## Dependencies
- SQLite database for caching
- OpenAI API for LLM analysis
- Brave Search API for vendor lookups

## Notes
- Cache effectiveness needs verification through logs
- Balance needed between cache hit rate and accuracy
- Consider impact of cache key strategy on performance 

## Current Focus: LLM Integration Implementation

### Active Task
Implementing new LLM integration with structured outputs and tools:
- Creating `LLMIntegration` class in `pdf_extractor_web/llm/integration.py`
- Updating transaction processing in `pdf_extractor_web/profiles/admin.py`
- Implementing response schemas for payee lookup and classification
- Adding tool execution and result integration

### Recent Changes
- Created comprehensive LLM integration architecture plan
- Defined response schemas for both payee lookup and classification
- Outlined tool integration strategy
- Planned status tracking for payee identification methods

### Next Steps
1. Create `LLMIntegration` class with core functionality
2. Implement response schemas
3. Add tool execution handling
4. Update transaction processing
5. Add comprehensive logging
6. Test with existing agents

### Key Decisions
- Maintain two-pass approach for payee lookup and classification
- Track payee identification method (AI, AI+Search, Human)
- Use JSON schema validation for responses
- Implement dynamic tool loading from database

### Dependencies
- OpenAI API
- Django models (Agent, Tool)
- JSON schema validation
- Logging system 

## Recent Changes
1. Payee Lookup Agent:
   - Split prompts into system and user messages
   - Added explicit instructions for tool usage
   - Improved normalized_description handling
   - Fixed tool call flow to ensure final response

2. Classification Agent:
   - Maintained original classification logic
   - Updated prompt structure to match new format
   - Preserved all business rules and worksheet assignments

## Next Steps
1. Test both agents thoroughly
2. Monitor logs for any issues
3. Consider adding more detailed logging for tool calls
4. Review agent response schemas for consistency

## Critical Notes
- Agents must be kept isolated - changes to one should not affect others
- Each agent has its own specific prompt and schema
- Tool calls must be properly handled to ensure final responses
- Logging is crucial for debugging and monitoring 

## Background Processing Implementation
- Uses ProcessingTask model to track jobs
- Supports both payee lookup and classification tasks
- Provides monitoring interface in admin
- Uses existing agent infrastructure
- Maintains same processing logic as web interface

## Current State
- Basic functionality implemented and tested
- Working with both payee lookup and classification agents
- Monitoring interface accessible from transaction admin
- Simple command-line execution for processing tasks

## Technical Details
- Task status tracking: pending, processing, completed, failed
- Progress monitoring: transaction_count, processed_count, error_count
- Error handling and logging
- Uses same agent processing as web interface

## Next Actions
1. Verify backup procedures
2. Test with larger transaction sets
3. Consider adding periodic execution
4. Document usage procedures 