# LLM Integration Architecture Plan

## Overview
This document outlines the architecture and implementation plan for integrating structured outputs and tools with our LLM system.

## Current State
- Django database stores agent configurations and tools
- Brave Search tool is already defined and attached to payee lookup agent
- Existing `call_agent` function handles basic structured outputs
- Three-pass classification system is established

## Implementation Plan

### 1. Core LLM Integration Module
```python
# pdf_extractor_web/llm/integration.py
class LLMIntegration:
    """Handles LLM integration with structured outputs and tools."""
    
    def __init__(self, agent: Agent):
        self.agent = agent
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.tools = self._prepare_tools()
        self.response_schema = self._get_response_schema()
```

### 2. Response Schemas
- Payee Lookup Schema:
  ```json
  {
    "type": "object",
    "properties": {
      "payee": {"type": "string"},
      "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
      "reasoning": {"type": "string"},
      "transaction_type": {
        "type": "string",
        "enum": ["purchase", "payment", "transfer", "fee", "subscription", "service"],
      },
      "normalized_description": {"type": "string"},
      "original_context": {"type": "string"},
      "questions": {"type": "string"},
    },
    "required": [
      "payee", "confidence", "reasoning", "transaction_type",
      "normalized_description", "original_context", "questions"
    ],
    "additionalProperties": False,
  }
  ```

- Classification Schema:
  ```json
  {
    "type": "object",
    "properties": {
      "classification_type": {"type": "string", "enum": ["business", "personal"]},
      "worksheet": {"type": "string", "enum": ["6A", "Auto", "HomeOffice", "None"]},
      "irs_category": {"type": "string"},
      "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
      "reasoning": {"type": "string"},
      "questions": {"type": "string"},
    },
    "required": [
      "classification_type", "worksheet", "irs_category",
      "confidence", "reasoning", "questions"
    ],
    "additionalProperties": False,
  }
  ```

### 3. Tool Integration
- Tool definitions prepared from Django database
- Tool execution handled through dynamic module imports
- Tool results integrated into final response

### 4. Transaction Processing Flow
1. Initialize LLMIntegration with selected agent
2. Process transaction description
3. Handle tool calls if present
4. Validate response against schema
5. Update transaction with results

### 5. Key Improvements
- Clean separation of concerns
- Proper structured output handling
- Comprehensive error handling
- Detailed logging
- Schema validation
- Tool execution and result integration

### 6. Status Tracking
- Track how payees were identified (AI, AI+Search, Human)
- Log tool usage and results
- Monitor confidence levels

## Implementation Steps
1. Create LLM integration module
2. Update transaction processing
3. Add logging and monitoring
4. Test with existing agents
5. Deploy and monitor

## Dependencies
- OpenAI API
- Django models (Agent, Tool)
- JSON schema validation
- Logging system

## Testing Plan
1. Unit tests for LLMIntegration
2. Integration tests with agents
3. Tool execution tests
4. Schema validation tests
5. Error handling tests

## Monitoring
- Log API requests and responses
- Track tool usage
- Monitor confidence levels
- Alert on validation failures

## Future Enhancements
- Add more tools as needed
- Enhance error recovery
- Improve logging and monitoring
- Add caching for tool results 