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

import django_rq
import gzip
import json
import math
import os
import re
import requests

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.servers.basehttp import FileWrapper
from django.core.urlresolvers import reverse
from django.db.models import Min, Max, Count, Avg
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render, render_to_response, redirect
from django.template import TemplateDoesNotExist
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_page, never_cache
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView

from portal.config.expert_databases import expert_dbs
from portal.forms import ContactForm
from portal.models import Rna, Database, Release, Xref, Accession, DatabaseStats


CACHE_TIMEOUT = 60 * 60 * 24 * 1 # per-view cache timeout in seconds
XREF_PAGE_SIZE = 1000

########################
# Function-based views #
########################

def download_job_result(request):
    """
    Download job results given a job id.
    """
    job_id = request.GET.get('job', '')

    if not job_id:
        raise Http404

    q = django_rq.get_queue()
    job = q.fetch_job(job_id)

    if not job:
        return HttpResponse('Invalid job id')
    if job.result:
        wrapper = FileWrapper(open(job.result, 'r'))
        response = HttpResponse(wrapper, content_type='text/fasta')
        response['Content-Disposition'] = 'attachment; filename=%s' % job.result
        response['Content-Length'] = os.path.getsize(job.result)
        return response
    else:
        return HttpResponse('Check back later')


def export_results(query):
    """
    """
    endpoint = 'http://wwwdev.ebi.ac.uk/ebisearch/ws/rest/rnacentral'

    def get_hit_count():
        """
        Get the total number of results to be exported.
        """
        hits = 0
        url = ''.join([endpoint,
                      '?query={query}',
                      '&start=0',
                      '&size=0',
                      '&format=json']).format(query=query)
        # todo error handling
        results = json.loads(requests.get(url).text)
        hits = results['hitCount']
        return hits

    def get_results_page(start, end):
        """
        Paginate over search results and record RNAcentral ids.
        """
        ids = []
        page_size = end - start
        url =  ''.join([endpoint,
                       '?query={query}',
                       '&start={start}',
                       '&size={page_size}',
                       '&format=json']).format(query=query, start=start, page_size=page_size)
        # todo error handling
        data = json.loads(requests.get(url).text)
        for entry in data['entries']:
            ids.append(entry['id'])
        return ids

    def format_output(rnacentral_ids):
        """
        Given a list of RNAcentral ids, return the results
        in the specified format.
        """
        output = []
        for rna in Rna.objects.filter(upi__in=rnacentral_ids).all():
            output.append(rna.get_sequence_fasta())
        return ''.join(output)

    def paginate_over_results():
        """
        Loop over the results and write out the data in an archive.
        """
        filename = 'results.txt.gz'
        archive = gzip.open(filename, 'wb')
        output = []
        start = 0
        page_size = 50
        while (start < hits):
            max_end = start + page_size
            end = min(max_end, hits)
            rnacentral_ids = get_results_page(start, end)
            archive.write(format_output(rnacentral_ids))
            start = max_end
        archive.close()
        return filename

    hits = get_hit_count()
    if hits == 0:
        data = 'no results'
    else:
        data = paginate_over_results()
    return data


@never_cache
def export_search_results(request):
    """
    Internal API.
    Export search results in different formats:
    * fasta
    """
    query = request.GET.get('q', '')
    _format = request.GET.get('format', 'fasta')

    job = django_rq.enqueue(export_results, query)

    # todo: error handling
    result_url = '{url}?job={job_id}'.format(url=reverse('download-job-result'), job_id=job.id)
    return HttpResponse(result_url)


@never_cache
def ebeye_proxy(request):
    """
    Internal API.
    Get EBeye search URL from the client and send back the results.
    Bypasses EBeye same-origin policy.
    """
    url = request.GET['url']
    try:
        ebeye_response = requests.get(url)
        response = HttpResponse(ebeye_response.text)
        patch_cache_control(response, no_cache=True, no_store=True,
                            must_revalidate=True)
        return response
    except:
        raise Http404



@never_cache
def get_xrefs_data(request, upi, taxid=None):
    """
    Internal API.
    Get the xrefs table in batches.
    """
    xref_list = Rna.objects.get(upi=upi).get_xrefs(taxid=taxid).all()
    paginator = Paginator(xref_list, XREF_PAGE_SIZE)

    page = request.GET.get('page')
    try:
        xrefs = paginator.page(page)
    except PageNotAnInteger:
        xrefs = paginator.page(1)
    except EmptyPage:
        xrefs = paginator.page(paginator.num_pages)

    return render_to_response('portal/xref-table.html', {"xrefs": xrefs})


@cache_page(CACHE_TIMEOUT)
def get_sequence_lineage(request, upi):
    """
    Internal API.
    Get the lineage for an RNA sequence based on the
    classifications from all database cross-references.
    """
    try:
        xrefs = Xref.objects.filter(upi=upi).select_related('accession').iterator()
        json_lineage_tree = _get_json_lineage_tree(xrefs)
    except Rna.DoesNotExist:
        raise Http404
    return HttpResponse(json_lineage_tree, content_type="application/json")


@cache_page(CACHE_TIMEOUT)
def homepage(request):
    """
    RNAcentral homepage.
    """
    context = {
        'seq_count': Rna.objects.count(),
        'last_update': Release.objects.order_by('-release_date').all()[0],
        'databases': list(Database.objects.order_by('-num_sequences').all()),
    }
    return render(request, 'portal/homepage.html', {'context': context})


@cache_page(CACHE_TIMEOUT)
def expert_databases_view(request):
    """
    List of RNAcentral expert databases.
    """
    context = {
        'expert_dbs': sorted(expert_dbs, key=lambda x: x['name'].lower()),
        'num_imported': len([x for x in expert_dbs if x['imported']]),
    }
    return render(request, 'portal/expert-databases.html', {'context': context})


@cache_page(CACHE_TIMEOUT)
def rna_view_redirect(request, upi, taxid):
    """
    Redirect from urs_taxid to urs/taxid.
    """
    return redirect('unique-rna-sequence', upi=upi, taxid=taxid)


@cache_page(CACHE_TIMEOUT)
def rna_view(request, upi, taxid=None):
    """
    Unique RNAcentral Sequence view.
    Display all annotations or customize the page using the taxid (optional).
    """
    def get_xref_page_num():
        """
        For pages with many xrefs, get the xref page number.
        Return it as a number because it is used in numerical comparisons
        in the template.
        """
        xref_page_num = request.GET.get('xref-page')
        if xref_page_num:
            xref_page_num = int(xref_page_num)
        else:
            xref_page_num = 1
        return xref_page_num

    def get_xrefs_pages():
        """
        When the number of xrefs is large, calculate the number of xref batches.
        Example:
        count_xrefs = 3095
        Return [1, 2, 3, 4] for 4 pages.
        """
        return xrange(1, int(math.ceil(rna.count_xrefs()/float(XREF_PAGE_SIZE))) + 1)

    def is_taxid_filtering_possible():
        """
        Determine if the page should be customized using the taxid.
        """
        if taxid:
            if rna.xref_with_taxid_exists(taxid):
                return True
            else:
                return False
        else:
            return False

    def get_single_species():
        """
        Determine if the sequence has only one species or get the taxid species.
        """

        def get_species_name_from_taxid(taxid):
            """
            Get a species name given an NCBI taxid.
            """
            species_name = ''
            if taxid:
                xref = Xref.objects.filter(taxid=taxid).select_related('accession')[:1].get()
                if xref:
                    species_name = xref.accession.species
            return species_name

        if taxid_filtering:
            return get_species_name_from_taxid(taxid)
        else:
            if rna.count_distinct_organisms == 1:
                return rna.xrefs.first().accession.species
            else:
                return None

    try:
        rna = Rna.objects.get(upi=upi)
    except Rna.DoesNotExist:
        raise Http404

    taxid_filtering = is_taxid_filtering_possible()

    context = {
        'counts': rna.count_symbols(),
        'taxid': taxid,
        'taxid_filtering': taxid_filtering,
        'single_species': get_single_species(),
        'description': rna.get_description(taxid) if taxid_filtering else rna.get_description(),
        'distinct_databases': rna.get_distinct_database_names(taxid),
        'publications': rna.get_publications(taxid) if taxid_filtering else rna.get_publications(),
        'tab': request.GET.get('tab', ''),
        'xref_pages': get_xrefs_pages(),
        'xref_page_size': XREF_PAGE_SIZE,
        'xref_page_num': get_xref_page_num(),
    }

    return render(request, 'portal/unique-rna-sequence.html', {'rna': rna, 'context': context})


@cache_page(CACHE_TIMEOUT)
def expert_database_view(request, expert_db_name):
    """
    Expert database view.
    """
    def _normalize_expert_db_name(expert_db_name):
        """
        Expert_db_name should match RNACEN.RNC_DATABASE.DESCR
        """
        dbs = Database.objects.values_list('descr', flat=True)
        dbs_coming_soon = ()
        if re.match('tmrna-website', expert_db_name, flags=re.IGNORECASE):
            expert_db_name = 'TMRNA_WEB'
        else:
            expert_db_name = expert_db_name.upper()
        if expert_db_name in dbs:
            return expert_db_name
        elif expert_db_name in dbs_coming_soon:
            return 'coming_soon'
        else:
            return False

    expert_db_name = _normalize_expert_db_name(expert_db_name)
    if expert_db_name and expert_db_name != 'coming_soon':
        expert_db = Database.objects.get(descr=expert_db_name)
        expert_db_stats = DatabaseStats.objects.get(database=expert_db_name)
        if expert_db_name == 'LNCRNADB':
            lncrnadb = Rna.objects.filter(xrefs__accession__database=expert_db_name).\
                                   order_by('-length').\
                                   all()
        else:
            lncrnadb = []
        return render_to_response('portal/expert-database.html', {
            'expert_db': expert_db,
            'expert_db_stats': expert_db_stats,
            'lncrnadb': lncrnadb,
        })
    elif expert_db_name == 'coming_soon':
        return render_to_response('portal/coming-soon.html')
    else:
        raise Http404()


@never_cache
def website_status_view(request):
    """
    This view will be monitored by Nagios for the presence
    of string "All systems operational".
    """
    def _is_database_up():
        try:
            rna = Rna.objects.all()[0]
            return True
        except:
            return False

    def _is_api_up():
        return True

    def _is_search_up():
        return True

    context = dict()
    context['is_database_up'] = _is_database_up()
    context['is_api_up'] = _is_api_up()
    context['is_search_up'] = _is_search_up()
    context['overall_status'] = context['is_database_up'] and context['is_api_up'] and context['is_search_up']
    return render_to_response('portal/website-status.html', {'context': context})

#####################
# Class-based views #
#####################

class StaticView(TemplateView):
    """
    Render flat pages.
    """
    def get(self, request, page, *args, **kwargs):
        self.template_name = 'portal/' + page + '.html'
        response = super(StaticView, self).get(request, *args, **kwargs)
        try:
            return response.render()
        except TemplateDoesNotExist:
            raise Http404()


class ContactView(FormView):
    """
    Contact form view.
    """
    template_name = 'portal/contact.html'
    form_class = ContactForm

    def form_valid(self, form):
        # This method is called when valid form data has been POSTed.
        # It should return an HttpResponse.
        if form.send_email():
            return redirect('contact-us-success')
        else:
            return redirect('error')

####################
# Helper functions #
####################

def _get_json_lineage_tree(xrefs):
    """
    Combine lineages from multiple xrefs to produce a single species tree.
    The data are used by the d3 library.
    """

    def get_lineages_and_taxids():
        """
        Combine the lineages from all accessions in a single list.
        """
        for xref in xrefs:
            lineages.append(xref.accession.classification)
            taxids[xref.accession.classification.split('; ')[-1]] = xref.taxid

    def build_nested_dict_helper(path, text, container):
        """
        Recursive function that builds the nested dictionary.
        """
        segs = path.split('; ')
        head = segs[0]
        tail = segs[1:]
        if not tail:
            # store how many time the species is seen
            try:
                if head in container:
                    container[head] += 1
                else:
                    container[head] = 1
            except:
                container = {}
                container[head] = 1
        else:
            try:
                if head not in container:
                    container[head] = {}
            except:
                container = {}
                container[head] = 1
            build_nested_dict_helper('; '.join(tail), text, container[head])

    def get_nested_dict(lineages):
        """
        Transform a list like this:
            items = [
                'A; C; X; human',
                'A; C; X; human',
                'B; D; Y; mouse',
                'B; D; Z; rat',
                'B; D; Z; rat',
            ]
        into a nested dictionary like this:
            {'root': {'A': {'C': {'X': {'human': 2}}}, 'B': {'D': {'Y': {'mouse': 1}, 'Z': {'rat': 2}}}}}
        """
        container = {}
        for lineage in lineages:
            build_nested_dict_helper(lineage, lineage, container)
        return container

    def get_nested_tree(data, container):
        """
        Transform a nested dictionary like this:
            {'root': {'A': {'C': {'X': {'human': 2}}}, 'B': {'D': {'Y': {'mouse': 1}, 'Z': {'rat': 2}}}}}
        into a json file like this (fragment shown):
            {"name":"A","children":[{"name":"C","children":[{"name":"X","children":[{"name":"human","size":2}]}]}]}
        """
        if not container:
            container = {
                "name": 'All',
                "children": []
            }
        for name, children in data.iteritems():
            if isinstance(children, int):
                container['children'].append({
                    "name": name,
                    "size": children,
                    "taxid": taxids[name],
                })
            else:
                container['children'].append({
                    "name": name,
                    "children": []
                })
                get_nested_tree(children, container['children'][-1])
        return container

    lineages = []
    taxids = dict()
    get_lineages_and_taxids()
    nodes = get_nested_dict(lineages)
    json_lineage_tree = get_nested_tree(nodes, {})
    return json.dumps(json_lineage_tree)
