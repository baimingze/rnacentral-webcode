#!/bin/bash

# Copyright [1999-2014] Wellcome Trust Sanger Institute and the EMBL-European Bioinformatics Institute
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

##############################################################################
# Set environment variables
##############################################################################

# path to /rnacentral
export RNACENTRAL_HOME=

# path to directory with the redis-server binary
export RNACENTRAL_REDIS=

# path to directory with memcached binary
export RNACENTRAL_MEMCACHED=

# path to directory where files with search results are stored
export RNACENTRAL_EXPORT_RESULTS_DIR=

# path to Oracle Instant Client libraries
export ORACLE_HOME=
export LD_LIBRARY_PATH=$ORACLE_HOME
export DYLD_LIBRARY_PATH=$ORACLE_HOME
