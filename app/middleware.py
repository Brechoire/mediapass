"""Middleware implementation for custom 404 error handling."""

from django.http import HttpResponseNotFound
from django.template.loader import render_to_string


class Custom404Middleware:
    """Custom middleware class for handling 404 errors."""

    def __init__(self, get_response):
        """Initialize the middleware with get_response function."""
        self.get_response = get_response

    def __call__(self, request):
        """Process the request and handle 404 responses."""
        response = self.get_response(request)
        if response.status_code == 404:
            html = render_to_string("404.html", {"request": request})
            return HttpResponseNotFound(html)
        return response

    def process_exception(self, request, exception):
        """Handle exceptions and process 404 errors."""
        if hasattr(exception, "status_code") and exception.status_code == 404:
            html = render_to_string("404.html", {"request": request})
            return HttpResponseNotFound(html)
        return None
