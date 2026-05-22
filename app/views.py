"""Views module for handling application routes and responses."""

from django.shortcuts import render


def test_404(request):
    """Render the 404 error page for testing purposes."""
    return render(request, "404.html")
