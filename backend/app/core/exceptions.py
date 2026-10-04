class TripWiseError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(TripWiseError):
    status_code = 404


class ConflictError(TripWiseError):
    status_code = 409


class ValidationError(TripWiseError):
    status_code = 422


class ProviderError(TripWiseError):
    status_code = 503

