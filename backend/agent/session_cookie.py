from flask import current_app, request


def name():
    return current_app.config.get("AUTH_COOKIE", "forest_session")


def secure():
    return bool(current_app.config.get("AUTH_COOKIE_SECURE", False))


def read():
    return request.cookies.get(name(), "").strip()


def attach(response, token):
    response.set_cookie(
        name(),
        token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="Lax",
        secure=secure(),
        path="/",
    )
    return response


def clear(response):
    response.delete_cookie(name(), path="/", httponly=True, samesite="Lax", secure=secure())
    return response
