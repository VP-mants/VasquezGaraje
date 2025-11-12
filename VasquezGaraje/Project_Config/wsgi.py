"""
WSGI config for VasquezGaraje MVC project.
"""
import os
from django.core.wsgi import get_wsgi_application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Project_Config.settings')
application = get_wsgi_application()
