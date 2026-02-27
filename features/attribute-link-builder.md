# Attribute Pass-Through Link Feature - Design Documentation

## Overview

The Attribute Pass-Through Link feature allows administrators to create special links that automatically pass authenticated user attributes to external URLs. When a user clicks on such a link, the system reads their authentication cookie, fetches their attributes from the LSVT API, and redirects them to the target URL with those attributes appended as query parameters.

## Architecture

### Components (this project: FastAPI + Vue SPA)

1. **Link Builder UI** (`/link-builder`)
   - Vue SPA page for constructing Attribute Pass-Through Links
   - Allows selection of attributes, custom key mapping, and redirect URL configuration
   - Generates the final link in the browser with proper URL encoding (no backend call)

2. **Logic Endpoint** (`/apl`)
   - FastAPI GET handler for generated links
   - Reads `LSVT_GUSERID` cookie to identify the visitor (LSVT-authenticated user)
   - Calls LSVT API to fetch that user's attributes (via `lsvt_user` module using httpx)
   - Applies key mapping and redirects with attributes appended

3. **LSVT user fetch** (`backend/app/lsvt_user.py`)
   - Fetches user by ID from `https://cfws.lightspeedvt.com/rest/lsvtapi/users/{userId}` using httpx
   - In-memory cache with configurable TTL; no existing LightSpeedAPI class in this repo

4. **Utility Modules**
   - `redirect_validator.py`: URL validation and allowlist checking
   - `attribute_mapper.py`: Key mapping and transformation utilities

## URL Format

### Base Format
```
https://am.lightspeedvt.com/apl?params=<comma_separated_attributes>&redirect_url=<url_encoded_redirect>
```

(Use your deployment base URL; the Link Builder uses `window.location.origin`.)

### With Parameter Mapping
```
https://am.lightspeedvt.com/apl?params=<comma_separated_attributes>&redirect_url=<url_encoded_redirect>&key_map=<url_encoded_json>
```

### Example
```
https://am.lightspeedvt.com/apl?params=firstName,email,userId&redirect_url=https%3A%2F%2Fexample.com%2Flanding&key_map=%7B%22firstName%22%3A%22first_name%22%2C%22email%22%3A%22userEmail%22%7D
```

## Request Flow

1. User clicks on an Attribute Pass-Through Link
2. Endpoint (`/apl`) receives the request
3. Validates `redirect_url` (format, allowlist)
4. Reads `LSVT_GUSERID` cookie
5. Validates user ID format
6. Parses requested attributes from `params` parameter
7. Filters out blocked attributes
8. Calls LSVT API to fetch user data
9. Applies key mapping (if provided)
10. Builds final URL with attributes as query parameters
11. Performs HTTP 302 redirect

## Security Features

### Open Redirect Prevention
- URL validation (only http/https protocols)
- Configurable allowlist of permitted domains
- Rejection of dangerous protocols (javascript:, data:, etc.)

### Sensitive Data Protection
- Blocklist of sensitive attributes (password, apiKey, etc.)
- Configurable via `APL_BLOCKED_ATTRIBUTES` in backend config
- Optional warning in Link Builder UI when blocklisted attributes are selected

### Rate Limiting
- 100 requests per minute per IP address
- Configurable via `APL_RATE_LIMIT` in config

### Cookie Security
- Validates `LSVT_GUSERID` cookie format
- Falls back gracefully if cookie is missing
- No sensitive data logged

## Configuration

### Environment Variables (backend/app/config.py)

```python
# Redirect allowlist: comma-separated domains; empty = allow any valid http(s) URL
REDIRECT_ALLOWLIST: str -> list (e.g. "example.com,app.example.com")

# Blocked attributes (never pass in URL)
APL_BLOCKED_ATTRIBUTES: list = ['password', 'apiKey', 'apiSecret', 'secret', 'token']

# Rate limiting for APL endpoint (e.g. "100 per minute")
APL_RATE_LIMIT: str = "100 per minute"

# User data cache TTL (seconds)
APL_USER_CACHE_TTL: int = 300  # 5 minutes
```

### API Credentials and visitor identity

- **Visitor identity:** The redirect endpoint uses the **visitor's** `LSVT_GUSERID` cookie to know which LSVT user clicked the link. This app does not store that cookie; it is set by the LSVT platform when the user is in an LSVT-authenticated context (e.g. link placed in LSVT course or email).
- **Session credentials:** This app's Credentials panel stores API key/secret in the **session** for other features. The LSVT user-data endpoint (`https://cfws.lightspeedvt.com/rest/lsvtapi/users/{userId}`) does not require authentication, so APL works without session credentials. If that endpoint later requires auth, session credentials could be used for the fetch.

### Test Cookie Endpoint

For testing purposes, a test endpoint is available to set the `LSVT_GUSERID` cookie:

**URI:** `/test/set-cookie`

**Method:** GET

**Parameters:**
- `user_id` (optional): User ID to set in the cookie. Defaults to `5832308` if not provided.

**Example:**
```
GET /test/set-cookie
GET /test/set-cookie?user_id=5832308
```

This endpoint sets the `LSVT_GUSERID` cookie and redirects to the home page. The cookie is valid for 24 hours and is not HttpOnly (for testing purposes).

**Testing:** The cookie is scoped to the origin (host + port). For params to be appended when you click a generated APL link, set the cookie on the **same origin** as the link. For example, if the Link Builder is at `http://localhost:5173`, open `http://localhost:5173/test/set-cookie` (not port 8000), then click the generated link. Adding `apl_debug=1` to the APL URL returns JSON diagnostics (cookie present, user data keys, reason params were or weren't added) instead of redirecting.

## Available Attributes

Default available attributes include:
- `userId`, `username`, `firstName`, `lastName`, `email`
- `locationId`, `locationName`, `systemId`, `systemName`
- `phone1`, `phone2`, `address1`, `address2`, `city`, `state`, `zip`, `country`
- `companyName`, `title`, `accessLevel`
- `misc1` (other info 1), `misc2` (other info 2)

The list is defined as `DEFAULT_ATTRIBUTES` in the backend (e.g. `attribute_mapper` or APL module); the Link Builder UI uses the same list for the attribute selector.

## Error Handling

### Missing Cookie
- Redirects to target URL without attributes
- Logs warning

### Invalid User ID
- Redirects to target URL without attributes
- Logs warning

### API Errors
- Redirects to target URL without attributes
- Logs error details
- Graceful degradation

### Invalid Redirect URL
- Returns 400 Bad Request
- Logs warning

### Blocked Redirect URL
- Returns 403 Forbidden
- Logs warning

## Backward Compatibility

The endpoint supports the legacy `hook_url` parameter as an alias for `redirect_url`:
```
/apl?params=...&hook_url=...
```

This ensures existing implementations continue to work.

## Performance

- User data is cached in-process for 5 minutes (configurable via `APL_USER_CACHE_TTL`)
- Reduces API calls for repeated requests
- Cache key: `user_data_{user_id}`

## Testing Considerations

1. **Unit Tests**
   - URL validation logic
   - Key mapping transformations
   - Attribute filtering

2. **Integration Tests**
   - End-to-end link generation and execution
   - API call handling
   - Redirect URL construction

3. **Security Tests**
   - Open redirect prevention
   - Blocked attribute filtering
   - Rate limiting enforcement

4. **Edge Cases**
   - Missing cookie
   - Invalid user ID
   - API timeouts
   - Malformed URLs
   - Missing attributes

## Implementation notes (this project)

- **Stack:** FastAPI backend, Vue 3 SPA frontend. Link Builder is a client-only page; the generated link is built in the browser and points to this app's `/apl` endpoint.
- **Visitor identity:** APL uses the `LSVT_GUSERID` cookie for the clicking user; session-stored API credentials are for other app features.
- **Allowed attributes:** `DEFAULT_ATTRIBUTES` and blocklist live in the backend (config + attribute/APL modules); the frontend uses the same attribute list for the selector.

## Future Enhancements

1. POST redirect option for sensitive attributes
2. Attribute value encryption
3. Link expiration/timestamp validation
4. Analytics and usage tracking
5. Dynamic attribute list from API schema
6. Link preview/testing functionality

