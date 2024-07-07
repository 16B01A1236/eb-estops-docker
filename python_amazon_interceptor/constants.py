DEFAULT_MIDWAY_PROVIDER_HOST = "midway-auth.amazon.com"

OIDC_SCOPE = "openid"
OIDC_RESPONSE_TYPE = "id_token"
SENTRY_HANDLER_VERSION = "PythonMidwayServerHandler-1.0"

COOKIE_RFP = "amzn_sso_rfp"
COOKIE_TOKEN = "amzn_sso_token"
PARAM_TOKEN = "id_token"

# 7 minute clock skew threshold
CLOCK_SKEW_THRESHOLD = 7 * 60

AUTH_ERROR_CODE = {
    "invalid_request": 401,
    "unauthorized_client": 401,
    "invalid_client": 401,
    "access_denied": 403,
    "unsupported_response_type": 401,
    "invalid_scope": 401,
    "server_error": 401,
    "temporarily_unavailable": 500,
}

KEY_LRU_CACHE_SIZE = 2
