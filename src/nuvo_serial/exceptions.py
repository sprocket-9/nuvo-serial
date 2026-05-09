class MessageFormatError(Exception):
    """The message read from the stream is unrecognized format."""


class MessageClassificationError(Exception):
    """The message type cannot be classified by any of the implemented message type
    handlers.
    """

class MessageResponseError(Exception):
    """No response received for sent message."""

class ModelMismatchError(Exception):
    """Model specified at connection time differs from the model reported by the unit."""
