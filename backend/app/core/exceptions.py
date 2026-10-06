"""Application errors.

`AppError` is raised by API code and rendered as `{"detail", "code"}`.
`PipelineError` is raised inside the background pipeline; its message is safe
to show to the user and is stored on the job as `error_message`.
"""


class AppError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, detail: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(detail)
        self.detail = detail
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnsupportedFileError(AppError):
    status_code = 415
    code = "UNSUPPORTED_FILE"


class FileTooLargeError(AppError):
    status_code = 413
    code = "FILE_TOO_LARGE"


class InsufficientStorageError(AppError):
    status_code = 507
    code = "INSUFFICIENT_STORAGE"


class PipelineError(Exception):
    """A processing failure with a user-safe message."""

    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message
