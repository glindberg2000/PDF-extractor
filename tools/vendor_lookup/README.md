# Vendor Lookup Tool

A Python package for looking up and enriching vendor information using the Brave Search API. This tool is particularly useful for identifying and categorizing vendors from financial statements or transaction records.

## Features

- Looks up vendor information using Brave Search API
- Scores and ranks results based on business relevance
- Handles rate limiting (1 request/second on free plan)
- Provides structured vendor information (name, URL, description, etc.)
- Includes comprehensive error handling

## Installation

1. Ensure you have Python 3.7+ installed
2. Install required packages:
   ```bash
   pip install requests python-dotenv
   ```
3. Set up your environment variables:
   ```bash
   # .env file
   BRAVE_API_KEY=your_api_key_here
   ```

## Usage

### Basic Usage

```python
from tools.vendor_lookup import lookup_vendor_info, format_vendor_results

# Look up a vendor
results = lookup_vendor_info("Apple Inc")

# Format results for display
print(format_vendor_results(results, "Apple Inc"))
```

### Processing Multiple Vendors

```python
import time
from tools.vendor_lookup import lookup_vendor_info

vendors = ["Vendor1", "Vendor2", "Vendor3"]
for vendor in vendors:
    results = lookup_vendor_info(vendor)
    process_results(results)  # Your processing logic
    time.sleep(1)  # Respect rate limit
```

### Return Data Structure

The `lookup_vendor_info` function returns a list of `VendorInfo` dictionaries:

```python
{
    "title": str,           # Business name/title
    "url": str,            # Website URL
    "description": str,    # Business description
    "last_updated": str,   # When info was last updated
    "relevance_score": int # How relevant the result is
}
```

## Rate Limiting

The free plan is limited to 1 request per second. The tool includes:
- Rate limit error detection (429 responses)
- Clear error messages for rate limit violations
- Example code for handling multiple requests with delays

## Testing

Run the test suite:
```bash
python -m tools.vendor_lookup.tests
```

The test suite includes:
- Basic vendor lookup
- Local business lookup
- Maximum results testing
- Ambiguous name handling
- Error handling

## Error Handling

The tool raises:
- `ValueError` for missing API key or invalid parameters
- `RuntimeError` for API errors (including rate limits)

Always wrap vendor lookups in try/except blocks to handle failures gracefully.

## Future Improvements

1. Add caching to avoid repeated lookups
2. Implement smart retry logic for rate limits
3. Add batch processing with rate limiting
4. Create a vendor database for frequently seen vendors 