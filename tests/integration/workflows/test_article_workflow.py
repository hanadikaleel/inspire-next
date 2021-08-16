# -*- coding: utf-8 -*-
#
# This file is part of INSPIRE.
# Copyright (C) 2014-2018 CERN.
#
# INSPIRE is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# INSPIRE is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with INSPIRE. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this license, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

from __future__ import absolute_import, division, print_function

import os

import mock
import pkg_resources
import requests_mock

from invenio_search import current_search
from invenio_workflows import (
    start,
    workflow_object_class,
    ObjectStatus
)

from mocks import fake_beard_api_request, fake_download_file, fake_magpie_api_request
from workflow_utils import build_workflow, check_wf_state


from inspirehep.modules.workflows.tasks.actions import mark
from inspirehep.modules.workflows.tasks.matching import set_wf_not_completed_ids_to_wf

PUBLISHING_RECORD = {
    '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
    'titles': [
        {
            'title': 'Update without conflicts title.'
        },
    ],
    'arxiv_eprints': [
        {
            'categories': [
                'hep-lat',
                'hep-th'
            ],
            'value': '1703.04802'
        }
    ],
    'document_type': ['article'],
    '_collections': ['Literature'],
    'acquisition_source': {
        'datetime': '2020-11-12T04:49:13.369515',
        'method': 'hepcrawl',
        'submission_number': '978',
        'source': 'Elsevier',
    },
}

CURATION_RECORD = {
    '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
    'titles': [
        {
            'title': 'Update without conflicts title.'
        },
    ],
    'arxiv_eprints': [
        {
            'categories': [
                'hep-lat',
                'hep-th'
            ],
            'value': '1703.04802'
        }
    ],
    'document_type': ['article'],
    '_collections': ['Literature'],
    'acquisition_source': {
        'datetime': '2020-11-12T04:49:13.369515',
        'method': 'hepcrawl',
        'submission_number': '978',
        'source': 'submitter',
    },
}


@mock.patch(
    "inspirehep.modules.workflows.tasks.actions.download_file_to_workflow",
    side_effect=fake_download_file,
)
@mock.patch(
    "inspirehep.modules.workflows.tasks.beard.json_api_request",
    side_effect=fake_beard_api_request,
)
@mock.patch(
    "inspirehep.modules.workflows.tasks.magpie.json_api_request",
    side_effect=fake_magpie_api_request,
)
def test_create_ticket_when_source_is_publishing(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_package_download,
    workflow_app,
    mocked_external_services,
):

    workflow_id = build_workflow(PUBLISHING_RECORD).id
    start("article", object_id=workflow_id)
    wf = workflow_object_class.get(workflow_id)
    ticket_publishing_content = u'content=Queue%3A+HEP_publishing'
    wf.continue_workflow()

    assert ticket_publishing_content in mocked_external_services.request_history[1].text
    assert wf.extra_data['curation_ticket_id']
    assert mocked_external_services.request_history[1].url == 'http://rt.inspire/ticket/new'


@mock.patch(
    "inspirehep.modules.workflows.tasks.actions.download_file_to_workflow",
    side_effect=fake_download_file,
)
@mock.patch(
    "inspirehep.modules.workflows.tasks.beard.json_api_request",
    side_effect=fake_beard_api_request,
)
@mock.patch(
    "inspirehep.modules.workflows.tasks.magpie.json_api_request",
    side_effect=fake_magpie_api_request,
)
def test_create_ticket_when_source_is_not_publishing(
    mocked_api_request_magpie,
    mocked_api_request_beard,
    mocked_package_download,
    workflow_app,
    mocked_external_services,
):

    workflow_id = build_workflow(CURATION_RECORD).id
    start("article", object_id=workflow_id)
    wf = workflow_object_class.get(workflow_id)
    ticket_curation_content = u'content=Queue%3A+HEP_curation'
    wf.continue_workflow()

    assert ticket_curation_content in mocked_external_services.request_history[1].text
    assert wf.extra_data['curation_ticket_id']
    assert mocked_external_services.request_history[1].url == 'http://rt.inspire/ticket/new'


@mock.patch(
    "inspirehep.modules.workflows.tasks.actions.check_if_france_in_fulltext",
    return_value=False,
)
@mock.patch('inspirehep.modules.workflows.tasks.submission.send_robotupload')
def test_set_fermilab_collection_from_report_number(mocked_robotupload, workflow_app):
    record = {
        '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
        'titles': [
            {
                'title': 'Update without conflicts title.'
            },
        ],
        'document_type': ['article'],
        '_collections': ['Literature'],
        'report_numbers': [
            {'value': "FERMILAB-SOMETHING-11"},
        ]
    }
    expected_collections = ["Literature", "Fermilab"]
    workflow = build_workflow(record)
    start("article", object_id=workflow.id)
    wf = workflow_object_class.get(workflow.id)
    mark('approved', True)(workflow, None)
    wf.continue_workflow()
    assert workflow.data["_collections"] == expected_collections


@mock.patch('inspirehep.modules.workflows.tasks.submission.send_robotupload')
def test_set_fermilab_collection_not_added_when_no_report_number_from_fermilab(mocked_robotupload, workflow_app):
    record = {
        '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
        'titles': [
            {
                'title': 'Update without conflicts title.'
            },
        ],
        'document_type': ['article'],
        '_collections': ['Literature'],
        'report_numbers': [
            {'value': "NOT-FERMILAB-SOMETHING-11"},
        ]
    }
    expected_collections = ["Literature"]
    workflow = build_workflow(record)
    start("article", object_id=workflow.id)
    wf = workflow_object_class.get(workflow.id)
    mark('approved', True)(workflow, None)
    wf.continue_workflow()
    assert workflow.data["_collections"] == expected_collections


@mock.patch('inspirehep.modules.workflows.tasks.submission.send_robotupload')
def test_set_fermilab_collection_even_when_record_is_hidden_and_affiliations_are_not_fermilab(mocked_robotupload, workflow_app):
    record = {
        '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
        'titles': [
            {
                'title': 'Update without conflicts title.'
            },
        ],
        "authors": [
            {
                "full_name": "Some author",
                "raw_affiliations": [
                    {"value": "Some longer description CErN? with proper keyword included"}
                ]
            }
        ],
        'document_type': ['article'],
        '_collections': ['Literature'],
        'report_numbers': [
            {'value': "FERMILAB-SOMETHING-11"},
        ]
    }
    expected_collections = ["CDS Hidden", "Fermilab"]
    workflow = build_workflow(record)
    start("article", object_id=workflow.id)
    wf = workflow_object_class.get(workflow.id)
    mark('approved', False)(workflow, None)
    wf.continue_workflow()
    assert workflow.data["_collections"] == expected_collections


@mock.patch('inspirehep.modules.workflows.tasks.upload.store_record')
@mock.patch('inspirehep.modules.workflows.tasks.submission.submit_rt_ticket', return_value="1234")
@mock.patch('inspirehep.modules.workflows.tasks.submission.send_robotupload')
def test_keywords_are_stored_in_record_when_record_is_core(mocked_robotupload, mocked_create_ticket, mocked_store_record, workflow_app):
    record = {
        '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
        'titles': [
            {
                'title': 'Update without conflicts title.'
            },
        ],
        "authors": [
            {
                "full_name": "Some author",
                "raw_affiliations": [
                    {"value": "Some longer description CErN? with proper keyword included"}
                ]
            }
        ],
        'document_type': ['article'],
        '_collections': ['Literature'],
        'abstracts': [
            {
                'value': 'Very interesting paper about the Higgs boson.'
            },
        ],
        'acquisition_source': {
            'datetime': '2020-11-12T04:49:13.369515',
            'method': 'hepcrawl',
            'submission_number': '978',
            'source': 'Elsevier',
        },
    }

    expected_keywords = [
        {u'value': u'Higgs particle', u'schema': u'INSPIRE', u'source': u'classifier'}
    ]

    workflow = build_workflow(record)
    start("article", object_id=workflow.id)
    wf = workflow_object_class.get(workflow.id)
    mark('approved', True)(workflow, None)
    mark('core', True)(workflow, None)
    wf.continue_workflow()
    assert wf.data['keywords'] == expected_keywords


@mock.patch("inspirehep.modules.workflows.tasks.beard.json_api_request", return_value={})
@mock.patch("inspirehep.modules.workflows.tasks.magpie.json_api_request", return_value={})
@mock.patch('inspirehep.modules.workflows.tasks.upload.store_record')
@mock.patch('inspirehep.modules.workflows.tasks.submission.submit_rt_ticket', return_value="1234")
@mock.patch('inspirehep.modules.workflows.tasks.submission.send_robotupload')
@mock.patch('inspirehep.modules.workflows.tasks.actions.check_if_france_in_fulltext', return_value=False)
def test_run_next_wf_is_not_starting_core_selection_wfs(check_if_france_in_fulltext, mocked_robotupload, mocked_create_ticket, mocked_store_record, mocked_magpie, mocked_beard, mocked_external_services, workflow_app):
    record = {
        '$schema': 'https://labs.inspirehep.net/schemas/records/hep.json',
        'titles': [
            {
                'title': 'Title.'
            },
        ],
        "authors": [
            {
                "full_name": "Some author",
            }
        ],
        'document_type': ['article'],
        '_collections': ['Literature'],
        'arxiv_eprints': [{'value': "1802.08709.pdf"}, ],
        'control_number': 1234,
        "acquisition_source": {
            "datetime": "2021-06-11T06:59:01.928752",
            "method": "hepcrawl",
            "source": "arXiv",
        },
    }

    workflow = build_workflow(record, extra_data={'delay': 10})
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.register_uri(
            "GET", 'http://export.arxiv.org/pdf/1802.08709.pdf',
            content=pkg_resources.resource_string(
                __name__, os.path.join('fixtures', '1802.08709.pdf')
            )
        )
        requests_mocker.register_uri("GET", "http://arxiv.org/pdf/1802.08709.pdf", text="")
        requests_mocker.register_uri(
            "GET", "http://export.arxiv.org/e-print/1802.08709.pdf",
            content=pkg_resources.resource_string(
                __name__, os.path.join('fixtures', '1802.08709.pdf')
            )
        )
        requests_mocker.register_uri("POST", "http://grobid_url.local/api/processHeaderDocument")
        start("article", object_id=workflow.id)

    wf = workflow_object_class.get(workflow.id)
    mark('auto-approved', True)(workflow, None)
    wf.callback_pos = [34, 1, 13]
    wf.continue_workflow()
    check_wf_state(wf.id, ObjectStatus.COMPLETED)

    workflow = build_workflow(record)
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.register_uri("GET", 'http://export.arxiv.org/pdf/1802.08709.pdf',
                                     content=pkg_resources.resource_string(
                                         __name__, os.path.join('fixtures', '1802.08709.pdf')), )
        requests_mocker.register_uri("GET", "http://arxiv.org/pdf/1802.08709.pdf", text="")
        requests_mocker.register_uri("GET", "http://export.arxiv.org/e-print/1802.08709.pdf",
                                     content=pkg_resources.resource_string(
                                         __name__, os.path.join('fixtures', '1802.08709.pdf')), )
        requests_mocker.register_uri("POST", "http://grobid_url.local/api/processHeaderDocument")
        current_search.flush_and_refresh('holdingpen-hep')
        start("article", object_id=workflow.id)
    matched = set_wf_not_completed_ids_to_wf(workflow)
    assert matched == []
