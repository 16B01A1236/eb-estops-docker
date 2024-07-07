from typing import Dict

import requests
from cachetools import LRUCache, cached

from python_amazon_interceptor import constants

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode


def tokenless_query_string(params: Dict[str, str]) -> str:
    """Builds a query string (with leading question mark character) from a dictionary of parameters with ``id_token``
    parameter removed (if exists).

    :param params: Parameters to be included in query string
    :type params: dict
    :return: A query string without id_token parameter
    :rtype: str
    """
    tokenless_params = params.copy()
    tokenless_params.pop("id_token", None)
    query_string = urlencode(tokenless_params, doseq=True)
    return ("?" + query_string) if query_string else ""


def get_state(params: Dict[str, str]) -> str:
    """
    :param params: Parameters to be included in query string
    :type params: dict
    :return: A state parameter which holds original shape of request
    :rtype: str
    """
    return params.get("state")


@cached(cache=LRUCache(constants.KEY_LRU_CACHE_SIZE))
def get_public_key(key_id: str, jwks_url: str) -> Dict[str, str]:
    """Gets the certificate from Midway's JWKS. Certificate is pulled from the cache first if available.

    :param key_id: ID of the key in JWKS.
    :type key_id: str
    :param jwks_url: url to JWKS.
    :type jwks_url: str
    :return: A JSON Web Key (JWK) object.
    :rtype: dict
    """

    response = requests.get(jwks_url)
    try:
        keys = response.json()["keys"]
        for key in keys:
            if key["kid"] == key_id:
                return key
    except (ValueError, KeyError):
        raise RuntimeError("JSON web keys malformed response")

    raise RuntimeError(f"Error finding key for kid: {key_id}")
