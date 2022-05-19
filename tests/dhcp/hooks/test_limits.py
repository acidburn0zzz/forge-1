# Copyright (C) 2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Author: Marcin Godzina

"""Kea HA syncing"""

# pylint: disable=invalid-name,line-too-long,unused-argument

import pytest
import time

from src import misc
from src import srv_control
from src import srv_msg

from src.forge_cfg import world


def _get_address_v4(address, chaddr):
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'chaddr', chaddr)
    srv_msg.client_send_msg('DISCOVER')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'OFFER')
    srv_msg.response_check_content('yiaddr', address)
    #
    # misc.test_procedure()
    # srv_msg.client_sets_value('Client', 'chaddr', chaddr)
    # srv_msg.client_copy_option('server_id')
    # srv_msg.client_does_include_with_value('requested_addr', address)
    # srv_msg.client_send_msg('REQUEST')
    #
    # misc.pass_criteria()
    # srv_msg.send_wait_for_message('MUST', 'ACK')
    # srv_msg.response_check_content('yiaddr', address)

@pytest.mark.v4
@pytest.mark.hook
@pytest.mark.parametrize('backend', ['memfile'])
def test_limits_basic(dhcp_version, backend):
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    srv_control.config_srv_subnet('192.168.0.0/16', '192.168.51.1-192.168.255.255')
    srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')
    world.cfg['wait_interval'] = 0.01
    start = time.time()
    for i in range(1, 30):
        _get_address_v4(f'192.168.51.{i}', chaddr=f'ff:01:02:03:ff:{i:0>2x}')
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {end - start}")

    world.cfg['wait_interval'] = 0.001
    start = time.time()
    for i in range(30, 59):
        _get_address_v4(f'192.168.51.{i}', chaddr=f'ff:01:02:03:ff:{i:0>2x}')
    end = time.time()

    print(f"Runtime of the program is {end - start}")

    run2 = end - start

    print(f"Run1: {run1}")
    print(f"Run2: {run2}")

