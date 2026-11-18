from pathlib import Path

from django.contrib import admin
from django.http import FileResponse, HttpResponse
from django.urls import include, path

BASE_DIR = Path(__file__).resolve().parent.parent


def manus_routes(_request):
    manifest = BASE_DIR / "public" / "manus-routes.json"
    return FileResponse(manifest.open("rb"), content_type="application/json")


def health(_request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("manus-routes.json", manus_routes, name="manus_routes"),
    path("health/", health, name="health"),
    path("admin/", admin.site.urls),
    path("", include("katalog.urls")),
]
