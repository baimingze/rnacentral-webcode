"""
Copyright [2009-2014] EMBL-European Bioinformatics Institute
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
     http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

DATABASES = {
    'default': {
    	'ENGINE': 'django.db.backends.',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'OPTIONS'  : { 'init_command' : 'SET storage_engine=MyISAM', },
    }
}

TEMPLATE_DIRS = (
	'',
)

STATIC_ROOT = ''

EMAIL_HOST = ''
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_PORT =
EMAIL_USE_TLS = True
EMAIL_RNACENTRAL_HELPDESK = ''

SECRET_KEY = ''

ADMINS = (
    ('', ''),
)

COMPRESS_ENABLED =
DEBUG =
ALLOWED_HOSTS = []

# django-debug-toolbar
INTERNAL_IPS = ('127.0.0.1',)
