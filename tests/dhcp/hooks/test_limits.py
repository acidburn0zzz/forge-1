# Copyright (C) 2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Author: Marcin Godzina

"""Kea Limits Hook"""

# pylint: disable=invalid-name,line-too-long,unused-argument
import time
import pytest

from src import misc
from src import srv_control
from src import srv_msg
from src.softwaresupport.cb_api import client_class_set

from src.forge_cfg import world


def _get_address_v4(address, chaddr):
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'chaddr', chaddr)
    srv_msg.client_does_include_with_value('vendor_class_id', 'PXE')
    srv_msg.client_send_msg('DISCOVER')

    misc.pass_criteria()
    try:
        srv_msg.send_wait_for_message('MUST', 'OFFER')
    except AssertionError as e:
        if e.args[0] == 'No response received.':
            return 0
        raise AssertionError(e) from e
    return 1
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
def test_limits_subnet(dhcp_version, backend):
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    srv_control.config_srv_subnet('192.168.0.0/16', '192.168.1.1-192.168.255.255')
    srv_control.add_line_to_subnet(0, {"user-context": {
        "limits": {
            "rate-limit": "10 packets per second"
        }}})

    srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.add_hooks('libdhcp_limits.so')

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    success = 0
    packets = 0

    world.cfg['wait_interval'] = 0.002
    start = time.time()
    for k in range(1, 10):
        for i in range(1, 30):
            success += _get_address_v4(f'192.168.{k}.{i}', chaddr=f'ff:01:02:03:{k:0>2x}:{i:0>2x}')
            packets += 1
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {run1}")
    print(f"Packets received {success}/{packets}")
    print(f"Packets per second {success / run1}")


@pytest.mark.v4
@pytest.mark.hook
@pytest.mark.parametrize('backend', ['memfile'])
def test_limits_class(dhcp_version, backend):
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    srv_control.config_srv_subnet('192.168.0.0/16', '192.168.1.1-192.168.255.255')
    srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.add_hooks('libdhcp_limits.so')
    srv_control.add_hooks('libdhcp_class_cmds.so')

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    classes = [
      {
        "name": "gold",
        "test": "option[vendor-class-identifier].text == 'PXE'",
        "user-context": {
          "limits": {
            "rate-limit": "10 packets per second"
          }
        }
      }
    ]
    cmd = {"command": "class-add",
           "arguments": {"client-classes": classes}}
    # get lease details from Kea using Control Agent
    response = srv_msg.send_ctrl_cmd(cmd, 'http')

    success = 0
    packets = 0

    world.cfg['wait_interval'] = 0.002
    start = time.time()
    for k in range(1, 10):
        for i in range(1, 30):
            success += _get_address_v4(f'192.168.{k}.{i}', chaddr=f'ff:01:02:03:{k:0>2x}:{i:0>2x}')
            packets += 1
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {run1}")
    print(f"Packets received {success}/{packets}")
    print(f"Packets per second {success / run1}")