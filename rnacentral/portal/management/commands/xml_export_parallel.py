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

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
import subprocess
import time
from portal.models import Rna


class Command(BaseCommand):
    """
    Usage:
    python manage.py xml_export_parallel --destination /full/path/to/output/location

    Help:
    python manage.py xml_export_parallel -h
    """

    ########################
    # Command line options #
    ########################

    option_list = BaseCommand.option_list + (
        make_option('-d', '--destination',
            default='',
            dest='destination',
            help='[Required] Full path to the output directory'),
    )
    # shown with -h, --help
    help = ('Create LSF commands for parallelizing xml export.')

    ######################
    # Django entry point #
    ######################

    def handle(self, *args, **options):
        """
        Main function, called by django.
        """
        if not options['destination']:
            raise CommandError('Please specify --destination')

        total = Rna.objects.count()
        step = pow(10,5) * 2
        start = 0
        stop = 0

        for i in xrange(step,total,step):
            start = stop
            stop = min(total, i)
            cmd = "bsub python manage.py xml_export --min %i --max %i -d %s" % (start, stop, options['destination'])
            print cmd

        if stop < total:
            start = stop
            stop = total
            cmd = "bsub python manage.py xml_export --min %i --max %i -d %s" % (start, stop, options['destination'])
            print cmd
