import binascii
import hashlib
import json
import logging
from base64 import b64decode, b64encode
from http.client import OK, TEMPORARY_REDIRECT
from os import urandom
from typing import Dict, Optional
from urllib.parse import urlencode

import jwt
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import InvalidTokenError
from werkzeug.utils import escape
from werkzeug.wrappers import BaseResponse, Request, UserAgentMixin

from python_amazon_interceptor import constants, helpers, same_site_cookie_utils
from python_amazon_interceptor.config import Config
from python_amazon_interceptor.exceptions import InvalidClaimError, NonceMismatchError, WeakKeyError

logger = logging.getLogger()


class AmazonAuthHandlerRequestMixin:
    def __init__(self, environ: Dict[str, str], config: Config):
        self.environ = environ
        self.config = config

    def authenticate(self) -> Optional[BaseResponse]:
        """Main handler for the whole Midway or Amazon Federation authentication flow. This method is called by WSGI middleware to ensure
        user is authenticated before continue processing the request.

        :return: a ``werkzeug.wrappers.BaseResponse`` if it chooses to intercept the request for authentication
            flow. If user is already authenticated, it returns `None` which indicates to the middleware that it could continue
            processing the request. In that case, ID of authenticated user is stored in two WSGI environment variable
            ``HTTP_X_FORWARDED_USER`` and ``REMOTE_USER``.

        :rtype: werkzeug.wrappers.BaseResponse or NoneType
        """
        # If there exists an error query parameter in the request URL, and the error is recognized,
        # the handler must fail the request to the service.
        error_code = self.args.get("error")
        if error_code in constants.AUTH_ERROR_CODE:
            error_description = self.args.get("error_description")
            logging.debug(f"IDP generated error {error_code} - {error_description}")
            # If there's no corresponding status code for the authentication error code
            # received, we fallback to 500 (Internal Server Error)
            status_code = constants.AUTH_ERROR_CODE.get(error_code)
            return BaseResponse(escape(error_description), status_code)

        # SSO Token can be retrieved from both cookie and URI query.
        cookie_token = self.cookies.get(constants.COOKIE_TOKEN)
        id_token = self.args.get(constants.PARAM_TOKEN)

        # If no token found, start the authentication flow.
        if not cookie_token and not id_token:
            return self._require_authentication()

        # If RFP cookie is not available, also kick-off the authentication.
        rfp = self.cookies.get(constants.COOKIE_RFP)
        if not rfp:
            return self._require_authentication()

        rfp = binascii.unhexlify(rfp)

        # In case token is available in both places, the one from URI query string takes precedence.
        token = id_token or cookie_token
        try:
            claims = self._verify_and_extract_claims(token, rfp)
        except InvalidTokenError as exception:
            logging.error(f"Failed to validate token while extracting claims: {exception}")
            return self._require_authentication()
        except InvalidClaimError as exception:
            logging.error(f"Failed to validate claims: {exception}")
            return self._require_authentication()

        # `sub` claim might have format of <user_id>@ANT.AMAZON.COM or just <user_id>
        user = claims["sub"].split("@")[0]
        if not user:
            return self._require_authentication()

        # At this point, user is authenticated, there are few scenarios next:
        #
        # 1. If `id_token` query parameter is given, we send a response to store it in cookie and extend the expiration
        #   time of RFP token.
        #   1.a. If current the request is for JS SSO endpoint (i.e. '/sso/login'), return a JSON data to approve the
        #        authentication
        #   1.b. Otherwise, return a redirection
        #
        # 2. If `id_token` doesn't exist, this is a normal pos-authentication request.
        #   2.a. If current the request is for JS SSO endpoint, return a JSON data to indicate user is already
        #        authenticated.
        #   2.b. Otherwise, don't return anything to indicate to the middleware that we don't interfere with the
        #        response here.

        response = BaseResponse()

        # If token is set via URI query, update cookie value and do the last redirect to the same URL after removing
        # `id_token` parameter. Also updating the expiration date of RFP cookie
        if id_token:
            query_string = helpers.tokenless_query_string(self.args.to_dict(flat=True))
            # Default redirect is the event's path + query string parameters
            redirect_uri = "{path}{query_string}".format(path=self.path, query_string=query_string)
            # If state is present, pull path from state
            state_param = helpers.get_state(self.args.to_dict(flat=True))
            if state_param is not None:
                try:
                    redirect_uri = json.loads(b64decode(state_param).decode("UTF-8"))["path"]
                except (KeyError, TypeError):
                    logging.error(f"Invalid state parameter: {state_param}")
                    return BaseResponse("Invalid state parameter", constants.AUTH_ERROR_CODE["invalid_request"])

            same_site_option = "None" if same_site_cookie_utils.should_set_same_site_to_none(str(self.user_agent)) else None
            response.set_cookie(
                constants.COOKIE_TOKEN, id_token, domain=self.host, secure=True, httponly=True, expires=claims["exp"],
                samesite=same_site_option
            )
            response.set_cookie(
                constants.COOKIE_RFP,
                binascii.hexlify(rfp),
                domain=self.host,
                secure=True,
                httponly=True,
                expires=claims["exp"],
                samesite=same_site_option
            )

            # We will not redirect if the current request is reaching /sso/login path (which is reserved to facilitate
            # JS integration).
            if not self._is_javascript_sso_request():
                response.status_code = TEMPORARY_REDIRECT
                response.headers["Location"] = redirect_uri
                return response

        if self._is_javascript_sso_request():
            response.status_code = OK
            response.headers["Content-Type"] = "application/json"
            response.data = json.dumps({"is_authenticated": True, "expires_at": claims["exp"]})
            return response

        self.environ["HTTP_X_FORWARDED_USER"] = user
        self.environ["REMOTE_USER"] = user
        self.environ["HTTP_X_CLIENT_VERIFY"] = "SUCCESS"
        self.environ["HTTP_X_CLIENT_IDTOKEN"] = cookie_token

        # Upon reaching this point, user is authenticated. Returning None here to tell the caller that we
        # are not altering the workflow.
        return None

    def _verify_and_extract_claims(self, jwt_token: bytes, rfp_token: bytes) -> Dict[str, str]:
        """Verifies the JWT token and extract claims.

        :param jwt_token: JWT Token.
        :type jwt_token: bytes
        :param rfp_token: Request Forgery Protection token.
        :type rfp_token: bytes
        :return: The claims extracted from JWT payload. Required claims are 'iss', 'sub', 'exp' and 'aud'.
        :rtype: dict
        """
        headers = jwt.get_unverified_header(jwt_token)
        jwk = helpers.get_public_key(headers["kid"], self.config.jwks_url)
        public_key = RSAAlgorithm.from_jwk(json.dumps(jwk))

        # Ensure key length is in strong territory
        if public_key.key_size < 2048:
            raise WeakKeyError()

        # Parse the claims and verify both signature and claims.
        verification_options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_iat": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_nbf": True,
            "require_exp": True,
        }
        claims = jwt.decode(
            jwt=jwt_token,
            key=public_key,
            verify=True,
            algorithms=[jwk["alg"]],
            verify_exp=True,
            audience=self._get_client_id(),
            leeway=constants.CLOCK_SKEW_THRESHOLD,
            issuer="https://" + self.config.identity_provider_host,
            options=verification_options,
        )
        if not claims:
            raise jwt.exceptions.DecodeError("Missing claims in payload")

        if hashlib.sha256(rfp_token).hexdigest() != claims["nonce"]:
            raise NonceMismatchError()

        return claims

    def _is_javascript_sso_request(self) -> bool:
        return self.path == "/sso/login"

    def _get_client_id(self) -> str:
        """Return the Client Id, from configuration or per the Midway Spec
        Reference: https://w.amazon.com/index.php/Midway/Operations#Manually_signing_ID_tokens

        :return: The Client Id (in format of "https://foobar.amazon.com:443")
        :rtype: str
        """

        if self.config.client_id is not None:
            return self.config.client_id

        url_scheme = self.environ["wsgi.url_scheme"]

        host = self.host
        # `host` doesn't contain port information if it's the default port of the URL scheme.
        if ":" not in self.host:
            host += ":" + self.environ["SERVER_PORT"]

        return "{url_scheme}://{host}".format(url_scheme=url_scheme, host=host)

    def _build_authentication_url(self, rfp_token: bytes, endpoint: str) -> str:
        """Builds a URL for Midway authentication request which will be accessed by end-user on browser. This request
        is a standard OAuth 2.0 Authorization Request.

        :param rfp_token: Request Forgery Protection token.
        :type rfp_token: bytes
        :param endpoint: URL of authentication endpoint.
        :type endpoint: str
        :return: The authentication URL.
        :rtype: str
        """
        query_string = helpers.tokenless_query_string(self.args.to_dict(flat=True))

        # For Federate: self.config.redirect_uri always exists and is a non-null value.
        # For Midway: We need to retain the path and query string parameters
        # when generating redirect url
        if self.config.redirect_uri is not None:
            redirect_uri = f"https://{self.host}{self.config.redirect_uri}"
        else: # Midway
            redirect_uri = f"https://{self.host}{self.path}{query_string}"

        state = b64encode(str.encode(json.dumps({"path": self.path + query_string})))
        nonce = hashlib.sha256(rfp_token).hexdigest()

        parameters = {
            "redirect_uri": redirect_uri,
            "client_id": self._get_client_id(),
            "scope": constants.OIDC_SCOPE,
            "response_type": constants.OIDC_RESPONSE_TYPE,
            "response_mode": "query",
            "state": state,
            "nonce": nonce,
            "sentry_handler_version": constants.SENTRY_HANDLER_VERSION,
        }

        return "{base_url}?{query_string}".format(base_url=endpoint, query_string=urlencode(parameters))

    def _require_authentication(self) -> BaseResponse:
        """Returns a `werkzeug.wrappers.BaseResponse` that redirects client to an authentication URL or
        returns a JSON data indicating an unauthenticated session (if the current request is reaching /sso/login
        endpoint)
        """
        # Werkzeug assumes the encoding is utf-8
        # Ref: https://github.com/pallets/werkzeug/blob/8f8ced0086591fa2c95a367374797c4c62375eb9/werkzeug/wrappers.py#L124-L126
        rfp_token = binascii.unhexlify(self.cookies.get(constants.COOKIE_RFP, default=""))
        set_cookie = False
        if not rfp_token:
            rfp_token = urandom(32)
            set_cookie = True

        response = BaseResponse()

        if self._is_javascript_sso_request():
            data = {
                "is_authenticated": False,
                "authn_endpoint": self._build_authentication_url(rfp_token, endpoint=self.config.auth_path),
            }
            response.status_code = OK
            response.data = json.dumps(data)
            response.headers["Content-Type"] = "application/json"
        else:
            response.status_code = TEMPORARY_REDIRECT
            response.headers["Location"] = self._build_authentication_url(
                rfp_token, endpoint=self.config.auth_redirect_path
            )

        if set_cookie:

            # Cookie is set with no expiration time since we are at the initial phase of authentication flow. Expiration
            # time will be updated once the authentication flow is completed.
            response.set_cookie(
                constants.COOKIE_RFP, binascii.hexlify(rfp_token), domain=self.host, secure=True, httponly=True,
                samesite="None" if same_site_cookie_utils.should_set_same_site_to_none(str(self.user_agent)) else None
            )
        return response


# The base class order looks strange but it's the only order that does not cause "TypeError"
# due to inability to "create a consistent method resolutionorder (MRO)"
class AmazonHandlerRequest(AmazonAuthHandlerRequestMixin, Request, UserAgentMixin):
    """Werkzeug's Request class with ability to handle Federate authentication workflow."""
