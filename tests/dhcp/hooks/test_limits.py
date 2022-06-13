# Copyright (C) 2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Author: Marcin Godzina

"""Kea Limits Hook tests"""

# pylint: disable=invalid-name,line-too-long,unused-argument
import time
import pytest

from src import misc
from src import srv_control
from src import srv_msg

from src.forge_cfg import world


def _get_address_v4(chaddr, vendor=None):
    """
    Local function used to send Discover and check if Offer is send back.
    Can add vendor option to trigger client class in Kea.
    :param chaddr: MAC address
    :param vendor: Vendor name
    :return: 1 if Offer is received.
    """
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'chaddr', chaddr)
    if vendor is not None:
        srv_msg.client_does_include_with_value('vendor_class_id', vendor)
    srv_msg.client_send_msg('DISCOVER')

    misc.pass_criteria()
    try:
        srv_msg.send_wait_for_message('MUST', 'OFFER')
    except AssertionError as e:
        if e.args[0] == 'No response received.':
            return 0
        raise AssertionError(e) from e
    return 1


def _get_address_v6(duid, vendor=None):
    """
    Local function used to send Solicit and check if Advertise is send back.
    Can add vendor option to trigger client class in Kea.
    :param duid:  DUID address
    :param vendor: Vendor name
    :return: 1 if Advertise is received.
    """
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', duid)
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    if vendor is not None:
        srv_msg.client_sets_value('Client', 'vendor_class_data', vendor)
        srv_msg.client_does_include('Client', 'vendor-class')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    try:
        srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    except AssertionError as e:
        if e.args[0] == 'No response received.':
            return 0
        raise AssertionError(e) from e
    return 1


@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.hook
@pytest.mark.parametrize('backend', ['memfile'])
def test_limits_subnet(dhcp_version, backend):
    """
    Test of subnets limit of Rate Limiting Hook.
    The test makes DO or SA exchange in the fastest way possible and checks how many packets
    are being dropped per Kea server.
    """
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == 'v4':
        srv_control.config_srv_subnet('192.168.0.0/16', '192.168.1.1-192.168.255.255')
        srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
        # define limit for hook
        limit = 15
    else:
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::255:255')
        # define limit for hook
        limit = 3

    # hook configuration in user context for subnet with limit defined above
    srv_control.add_line_to_subnet(0, {"user-context": {
        "limits": {
            "rate-limit": f"{limit} packets per second"
        }}})

    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.add_hooks('libdhcp_limits.so')

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    success = 0
    packets = 0

    # Wait time for response for v4 and v6
    if dhcp_version == 'v4':
        world.cfg['wait_interval'] = 0.002
    else:
        world.cfg['wait_interval'] = 0.1

    start = time.time()
    if dhcp_version == 'v4':
        for _ in range(1, 90):
            success += _get_address_v4(chaddr='ff:01:02:03:04:05')
            packets += 1
    else:
        for _ in range(1, 20):
            success += _get_address_v6(duid='00:03:00:01:ff:ff:ff:ff:ff:ff')
            packets += 1
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {run1}")
    print(f"Packets received {success}/{packets}")
    print(f"Packets per second {success / run1}")

    score = success / run1
    assert abs(limit-score) < 1


@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.hook
@pytest.mark.parametrize('backend', ['memfile'])
def test_limits_class(dhcp_version, backend):
    """
    Test of client class limit of Rate Limiting Hook.
    The test makes DO or SA exchange in the fastest way possible and checks how many packets
    are being dropped per Kea server.
    """
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == 'v4':
        srv_control.config_srv_subnet('192.168.0.0/16', '192.168.1.1-192.168.255.255')
        srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
    else:
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::255:255')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.add_hooks('libdhcp_limits.so')
    srv_control.add_hooks('libdhcp_class_cmds.so')
    # hook configuration in user context for classes with limit
    if dhcp_version == 'v4':
        # define limit for hook
        limit = 15
        classes = [
            {
                "name": "gold",
                "test": "option[60].text == 'PXE'",
                "user-context": {
                    "limits": {
                        "rate-limit": f"{limit} packets per second"
                    }
                }
            }
        ]
    else:
        # define limit for hook
        limit = 3
        classes = [
            {
                "name": "VENDOR_CLASS_eRouter2.0",
                "user-context": {
                    "limits": {
                        "rate-limit": f"{limit} packets per second"
                    }
                }
            }
        ]
    world.dhcp_cfg["client-classes"] = classes

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    success = 0
    packets = 0

    # Wait time for response for v4 and v6
    if dhcp_version == 'v4':
        world.cfg['wait_interval'] = 0.002
    else:
        world.cfg['wait_interval'] = 0.1

    start = time.time()
    if dhcp_version == 'v4':
        for _ in range(90):
            success += _get_address_v4(chaddr='ff:01:02:03:04:05', vendor='PXE')
            packets += 1
    else:
        for _ in range(20):
            success += _get_address_v6(duid='00:03:00:01:ff:ff:ff:ff:ff:ff', vendor='eRouter2.0')
            packets += 1
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {run1}")
    print(f"Packets received {success}/{packets}")
    print(f"Packets per second {success / run1}")

    score = success / run1
    assert abs(limit-score) < 1


@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.hook
@pytest.mark.parametrize('backend', ['memfile'])
def test_limits_mix(dhcp_version, backend):
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == 'v4':
        srv_control.config_srv_subnet('192.168.0.0/16', '192.168.1.1-192.168.255.255')
        srv_control.config_srv_opt('subnet-mask', '255.255.0.0')
        limit = 20
    else:
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::255:255')
        limit = 50
    srv_control.add_line_to_subnet(0, {"user-context": {
        "limits": {
            "rate-limit": f"{limit} packets per minute"
        }}})
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.add_hooks('libdhcp_limits.so')
    srv_control.add_hooks('libdhcp_class_cmds.so')
    if dhcp_version == 'v4':
        classes = [
            {
                "name": "gold",
                "test": "option[60].text == 'PXE'",
                "user-context": {
                    "limits": {
                        "rate-limit": "10 packets per second"
                    }
                }
            },
            {
                "name": "silver",
                "test": "option[60].text == 'PXA'",
                "user-context": {
                    "limits": {
                        "rate-limit": "5 packets per second"
                    }
                }
            }

        ]
    else:
        classes = [
            {
                "name": "VENDOR_CLASS_eRouter1.0",
                "user-context": {
                    "limits": {
                        "rate-limit": "50 packets per minute"
                    }
                }
            },
            {
                "name": "VENDOR_CLASS_eRouter2.0",
                "user-context": {
                    "limits": {
                        "rate-limit": "50 packets per minute"
                    }
                }
            }
        ]
    world.dhcp_cfg["client-classes"] = classes

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    success_gold = 0
    packets_gold = 0
    success_silver = 0
    packets_silver = 0

    if dhcp_version == 'v4':
        world.cfg['wait_interval'] = 0.002
    else:
        world.cfg['wait_interval'] = 0.1
    start = time.time()
    if dhcp_version == 'v4':
        for _ in range(90):
            success_gold += _get_address_v4(chaddr='ff:01:02:03:04:05', vendor='PXE')
            success_silver += _get_address_v4(chaddr='ff:01:02:03:04:05', vendor='PXA')
            packets_gold += 1
            packets_silver += 1
    else:
        for _ in range(200):
            success_gold += _get_address_v6(duid='00:03:00:01:ff:ff:ff:ff:ff:ff', vendor='eRouter2.0')
            success_silver += _get_address_v6(duid='00:03:00:01:ff:ff:ff:ff:ff:ff', vendor='eRouter1.0')
            packets_gold += 1
            packets_silver += 1
    end = time.time()
    run1 = end - start

    print(f"Runtime of the program is {run1}")
    print(f"Gold Packets received {success_gold}/{packets_gold}")
    print(f"Gold Packets per minute {success_gold / run1 * 60}")
    print(f"Silver Packets received {success_silver}/{packets_silver}")
    print(f"Silver Packets per minute {success_silver / run1 * 60}")
