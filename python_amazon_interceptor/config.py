import os

import attr

from python_amazon_interceptor import constants

MIDWAY = "MIDWAY"
FEDERATE = "FEDERATE"

AUTH_PATH = "AUTH_PATH"
AUTH_REDIRECT_PATH = "AUTH_REDIRECT_PATH"
CLIENT_ID = "CLIENT_ID"
IDENTITY_PROVIDER = "IDENTITY_PROVIDER"
JWKS_URL = "JWKS_URL"
REDIRECT_URI_PATH = "REDIRECT_URI_PATH"

CONFIGURATION = {
    MIDWAY: {
        IDENTITY_PROVIDER: os.environ.get("IDENTITY_PROVIDER", constants.DEFAULT_MIDWAY_PROVIDER_HOST),
        JWKS_URL: "https://{host}/jwks.json",
        AUTH_PATH: "https://{host}/SSO",
        AUTH_REDIRECT_PATH: "https://{host}/SSO/redirect",
    },
    FEDERATE: {
        IDENTITY_PROVIDER: os.environ.get("IDENTITY_PROVIDER", "idp.federate.amazon.com"),
        JWKS_URL: "https://{host}/api/oauth2/v2/certs",
        AUTH_PATH: "https://{host}/api/oauth2/v1/authorize",
        AUTH_REDIRECT_PATH: "https://{host}/api/oauth2/v1/authorize",
    },
}


@attr.s
class Config:
    auth_path = attr.ib(type=str)
    auth_redirect_path = attr.ib(type=str)
    client_id = attr.ib(type=str)
    identity_provider_host = attr.ib(type=str)
    jwks_url = attr.ib(type=str)
    redirect_uri = attr.ib(type=str)
