"""Exceptions the tool raises when a capture cannot be trusted."""


class CaptureIntegrityError(Exception):
    """Raised by one of the three refusal gates (design section 2).

    The tool refuses to run rather than guess when the two capture files
    disagree with each other or with themselves. The message must name
    exactly what disagreed -- not just that something did.
    """
