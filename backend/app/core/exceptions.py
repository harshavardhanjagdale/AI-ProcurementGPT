from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, entity: str, entity_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": f"{entity.upper()}_NOT_FOUND", "message": f"{entity} with id '{entity_id}' not found"},
        )


class DuplicateError(HTTPException):
    def __init__(self, entity: str, field: str, value: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": f"{entity.upper()}_DUPLICATE", "message": f"{entity} with {field} '{value}' already exists"},
        )


class UnauthorizedError(HTTPException):
    def __init__(self, message: str = "Invalid credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": message},
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": message},
        )


class ValidationError(HTTPException):
    def __init__(self, message: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "VALIDATION_ERROR", "message": message},
        )
