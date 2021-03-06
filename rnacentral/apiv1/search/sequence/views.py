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

from django.core.urlresolvers import reverse
from django.views.decorators.cache import never_cache
from django.utils.datastructures import MultiValueDictKeyError
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from apiv1.search.sequence.rest_client import ENASequenceSearchClient, \
    SequenceSearchError, ResultsUnavailableError, InvalidSequenceError, \
    StatusNotFoundError


@api_view(['GET', 'POST'])
@permission_classes((AllowAny,))
def submit(request):
    """
    Submit a sequence and get a url for retrieving results.

    Status codes:

    * 200 - query submitted
    * 400 - invalid sequence/job_id/jsession_id
    * 500 - other internal error

    Return values:

    * `url` for checking query status
    * `message` with a status or an error message
    """
    job_id = jsession_id = url = message = None
    code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        sequence = request.QUERY_PARAMS['sequence']
    except:
        message = '`sequence` query parameter is required'
        code = status.HTTP_400_BAD_REQUEST
    else:
        client = ENASequenceSearchClient()
        try:
            (job_id, jsession_id) = client.submit_query(sequence)
        except InvalidSequenceError, e:
            message = e.message
            code = status.HTTP_400_BAD_REQUEST
        except SequenceSearchError, e:
            message = e.message
            code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            message = 'OK'
            code = status.HTTP_200_OK
            url = request.build_absolute_uri(
                reverse('apiv1.search.sequence.views.get_status') +
                '?jsession_id={0}&job_id={1}'.format(jsession_id, job_id)
            )
    data = {
        'message': message,
        'url': url,
    }
    return Response(data, status=code)


@api_view(['GET'])
@permission_classes((AllowAny,))
@never_cache
def get_status(request):
    """
    Check the query status using `job_id` and `jsession_id` query parameters.

    Status codes:

    * 200 - query 'Done' or 'In progress' depending on the `message` value
    * 400 - bad input parameters
    * 404 - query status not found
    * 500 - internal error

    Returns a status `message` and a `status` code, which can be:

    * `Done`
    * `In progress`
    * `Failed`
    """
    url = None
    count = 0
    code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        job_id = request.QUERY_PARAMS['job_id']
        jsession_id = request.QUERY_PARAMS['jsession_id']
    except:
        query_status = 'Failed'
        message = '`job_id` and `jsession_id` query parameters are required'
        code = status.HTTP_400_BAD_REQUEST
    else:
        client = ENASequenceSearchClient()
        try:
            (query_status, count) = client.get_status(job_id, jsession_id)
        except SequenceSearchError, e:
            query_status = 'Failed'
            message = e.message
            code = status.HTTP_500_INTERNAL_SERVER_ERROR
        except StatusNotFoundError, exc:
            query_status = 'Failed'
            message = exc.message
            code = status.HTTP_404_NOT_FOUND
        else:
            message = 'OK'
            code = status.HTTP_200_OK
            url = request.build_absolute_uri(
                reverse('apiv1.search.sequence.views.get_results') +
                '?jsession_id={0}&job_id={1}'.format(jsession_id, job_id)
            )
    data = {
        'message': message,
        'status': query_status,
        'url': url,
        'count': count,
    }
    return Response(data, status=code)


@api_view(['GET'])
@permission_classes((AllowAny,))
def get_results(request):
    """
    Get query results given a `job_id` and a `jsession_id`.

    The results set can be paginated over using
    `page_size` and `page` query parameters.

    Status codes:

    * 200 - results ready
    * 400 - bad input parameters
    * 404 - results unavailable or expired
    * 500 - internal error

    Return values:

    * results - list of dictionaries or an empty list
    * message - status or error message.
    """
    # default return values
    results = []
    message = ''
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    # optional pagination parameters
    page_number = int(request.QUERY_PARAMS.get('page', 1))
    page_size = int(request.QUERY_PARAMS.get('page_size', 10))

    try:
        job_id = request.QUERY_PARAMS['job_id']
        jsession_id = request.QUERY_PARAMS['jsession_id']
    except MultiValueDictKeyError:
        message = '`job_id` and `jsession_id` query parameters are required'
        status_code = status.HTTP_400_BAD_REQUEST
    else:
        client = ENASequenceSearchClient()
        try:
            results = client.get_results(job_id, jsession_id, page_number, page_size)
        except SequenceSearchError as exc:
            message = exc.message
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        except ResultsUnavailableError as exc:
            message = exc.message
            status_code = status.HTTP_404_NOT_FOUND
        except Exception:
            message = 'Unknown error'
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            message = 'OK'
            status_code = status.HTTP_200_OK

    data = {
        'results': results,
        'message': message
    }
    return Response(data, status=status_code)
