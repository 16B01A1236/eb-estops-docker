class AmazonAuthHandlerError(Exception):
    """
    Base class for all exceptions
    """

    pass


class WeakKeyError(AmazonAuthHandlerError):
    pass


class InvalidClaimError(AmazonAuthHandlerError):
    pass


class NonceMismatchError(InvalidClaimError):
    pass
