# Copyright (C) 2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Host Reservation DHCPv6"""

import pytest

from src import srv_control
from src import srv_msg
from src import misc
from src.forge_cfg import world
from src.protosupport.multi_protocol_functions import log_contains


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_all_values_mac():
    misc.test_setup()
    srv_control.config_srv_subnet('3000::/64', '3000::1-3000::ff')
    srv_control.host_reservation_in_subnet('hostname',
                                           'reserved-hostname',
                                           0,
                                           'hw-address',
                                           'f6:f5:f4:f3:f2:01')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'ip-address', '3000::100')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'prefixes', '3001::/40')
    srv_control.add_ddns_server('127.0.0.1', '53001')
    srv_control.add_ddns_server_options('enable-updates', True)
    srv_control.add_ddns_server_options('qualifying-suffix', 'my.domain.com')
    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'IA-PD')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')

    misc.test_procedure()
    srv_msg.client_copy_option('server-id')
    srv_msg.client_copy_option('IA_NA')
    srv_msg.client_copy_option('IA_PD')
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_sets_value('Client', 'FQDN_domain_name', 'some-different-name')
    srv_msg.client_sets_value('Client', 'FQDN_flags', 'S')
    srv_msg.client_does_include('Client', 'fqdn')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_send_msg('REQUEST')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'REPLY')
    srv_msg.response_check_include_option(3)
    srv_msg.response_check_option_content(3, 'sub-option', 5)
    srv_msg.response_check_suboption_content(5, 3, 'addr', '3000::100')
    srv_msg.response_check_include_option(25)
    srv_msg.response_check_option_content(25, 'sub-option', 26)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '3001::')
    srv_msg.response_check_include_option(39)
    srv_msg.response_check_option_content(39, 'fqdn', 'reserved-hostname.my.domain.com.')


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_all_values_duid():
    misc.test_setup()
    srv_control.config_srv_subnet('3000::/64', '3000::1-3000::ff')
    srv_control.host_reservation_in_subnet('hostname',
                                           'reserved-hostname',
                                           0,
                                           'duid',
                                           '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'ip-address', '3000::100')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'prefixes', '3001::/40')
    srv_control.add_ddns_server('127.0.0.1', '53001')
    srv_control.add_ddns_server_options('enable-updates', True)
    srv_control.add_ddns_server_options('qualifying-suffix', 'my.domain.com')
    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'IA-PD')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')

    misc.test_procedure()
    srv_msg.client_copy_option('server-id')
    srv_msg.client_copy_option('IA_NA')
    srv_msg.client_copy_option('IA_PD')
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_sets_value('Client', 'FQDN_domain_name', 'some-different-name')
    srv_msg.client_sets_value('Client', 'FQDN_flags', 'S')
    srv_msg.client_does_include('Client', 'fqdn')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_send_msg('REQUEST')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'REPLY')
    srv_msg.response_check_include_option(3)
    srv_msg.response_check_option_content(3, 'sub-option', 5)
    srv_msg.response_check_suboption_content(5, 3, 'addr', '3000::100')
    srv_msg.response_check_include_option(25)
    srv_msg.response_check_option_content(25, 'sub-option', 26)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '3001::')
    srv_msg.response_check_include_option(39)
    srv_msg.response_check_option_content(39, 'fqdn', 'reserved-hostname.my.domain.com.')


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_all_values_duid_2():

    misc.test_setup()
    srv_control.config_srv_subnet('3000::/64', '3000::1-3000::ff')
    srv_control.config_srv_prefix('2001:db8:1::', 0, 48, 49)
    srv_control.host_reservation_in_subnet('hostname',
                                           'reserved-hostname',
                                           0,
                                           'duid',
                                           '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'ip-address', '3000::100')
    srv_control.host_reservation_in_subnet_add_value(0, 0, 'prefixes', '2001:db8:1::/60')
    srv_control.add_ddns_server('127.0.0.1', '53001')
    srv_control.add_ddns_server_options('enable-updates', True)
    srv_control.add_ddns_server_options('qualifying-suffix', 'my.domain.com')
    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:01:00:01:52:7b:a8:f0:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'IA-PD')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')

    misc.test_procedure()
    srv_msg.client_copy_option('server-id')
    srv_msg.client_copy_option('IA_NA')
    srv_msg.client_copy_option('IA_PD')
    srv_msg.client_sets_value('Client', 'DUID', '00:01:00:01:52:7b:a8:f0:f6:f5:f4:f3:f2:01')
    srv_msg.client_sets_value('Client', 'FQDN_domain_name', 'some-different-name')
    srv_msg.client_sets_value('Client', 'FQDN_flags', 'S')
    srv_msg.client_does_include('Client', 'fqdn')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_send_msg('REQUEST')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'REPLY')
    srv_msg.response_check_include_option(1)
    srv_msg.response_check_include_option(2)
    srv_msg.response_check_include_option(3)
    srv_msg.response_check_option_content(3, 'sub-option', 5)
    srv_msg.response_check_suboption_content(5, 3, 'addr', '3000::100', expect_include=False)
    srv_msg.response_check_include_option(25)
    srv_msg.response_check_option_content(25, 'sub-option', 26)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '2001:db8:1::', expect_include=False)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '2001:db8:1:8000::')
    srv_msg.response_check_suboption_content(26, 25, 'plen', 49)
    srv_msg.response_check_include_option(39)
    srv_msg.response_check_option_content(39, 'fqdn', 'reserved-hostname.my.domain.com.', expect_include=False)

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'IA-PD')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(1)
    srv_msg.response_check_include_option(2)
    srv_msg.response_check_include_option(3)
    srv_msg.response_check_include_option(25)
    srv_msg.response_check_option_content(25, 'sub-option', 26)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '2001:db8:1::')
    srv_msg.response_check_suboption_content(26, 25, 'plen', 60)

    misc.test_procedure()
    srv_msg.client_copy_option('server-id')
    srv_msg.client_copy_option('IA_NA')
    srv_msg.client_copy_option('IA_PD')
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_sets_value('Client', 'FQDN_domain_name', 'some-different-name')
    srv_msg.client_sets_value('Client', 'FQDN_flags', 'S')
    srv_msg.client_does_include('Client', 'fqdn')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_send_msg('REQUEST')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'REPLY')
    srv_msg.response_check_include_option(1)
    srv_msg.response_check_include_option(2)
    srv_msg.response_check_include_option(3)
    srv_msg.response_check_include_option(25)
    srv_msg.response_check_option_content(25, 'sub-option', 26)
    srv_msg.response_check_suboption_content(26, 25, 'prefix', '2001:db8:1::')
    srv_msg.response_check_suboption_content(26, 25, 'plen', 60)


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_classes_1():

    misc.test_setup()
    srv_control.config_srv_subnet('3000::/64', '3000::1-3000::1')
    srv_control.add_line_to_subnet(0, {"reservations": [{"duid": "00:03:00:01:f6:f5:f4:f3:f2:22",
                                                         "client-classes": ["reserved-class1"]}]})

    srv_control.create_new_class('reserved-class1')
    srv_control.add_option_to_defined_class(1, 'sip-server-addr', '2001:db8::1,2001:db8::2')
    srv_control.add_option_to_defined_class(1, 'preference', '123')

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(22)
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(22, expect_include=False)
    srv_msg.response_check_include_option(7, expect_include=False)

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:22')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(22)
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(22)
    srv_msg.response_check_option_content(22, 'addresses', '2001:db8::1,2001:db8::2')
    srv_msg.response_check_include_option(7)
    srv_msg.response_check_option_content(7, 'prefval', 123)


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_classes_2():

    misc.test_setup()
    srv_control.config_srv_subnet('3000::/64', '3000::1-3000::1')
    srv_control.add_line_to_subnet(0, {"reservations": [{"duid": "00:03:00:01:f6:f5:f4:f3:f2:22",
                                                         "client-classes": ["reserved-class1", "reserved-class2"]}]})

    srv_control.create_new_class('reserved-class1')
    srv_control.add_option_to_defined_class(1, 'sip-server-addr', '2001:db8::1,2001:db8::2')

    srv_control.create_new_class('reserved-class2')
    srv_control.add_option_to_defined_class(2, 'preference', '123')

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:01')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(22)
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(22, expect_include=False)
    srv_msg.response_check_include_option(7, expect_include=False)

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:22')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(22)
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(22)
    srv_msg.response_check_option_content(22, 'addresses', '2001:db8::1,2001:db8::2')
    srv_msg.response_check_include_option(7)
    srv_msg.response_check_option_content(7, 'prefval', 123)


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_empty():
    """
    Test if empty (only MAC address) reservation can be made.
    """
    misc.test_setup()
    srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::1')

    world.dhcp_cfg.update({
        "reservations": [
            {
                "duid": "00:03:00:01:f6:f5:f4:f3:f2:22"
            }
        ], "reservation-mode": "global"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:22')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')

    log_contains('client packet has been assigned to the following class(es): KNOWN')


@pytest.mark.v6
@pytest.mark.host_reservation
def test_v6_host_reservation_example_access_control():
    """
    Test check example from ARM 9.3.12 "Host Reservations as Basic Access Control"
    with added Dropping of Unknown class
    """
    misc.test_setup()
    srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::1')
    srv_control.config_srv("dns-servers", 0, "2001:db8::1")
    # TODO require-client-classes is not working correctly - Kea #2863
    world.dhcp_cfg["subnet6"][0]["require-client-classes"] = ["blocked"]

    world.dhcp_cfg.update({
        "client-classes": [
            {
                "name": "blocked",
                "option-data": [
                    {
                        "name": "dns-servers",
                        "data": "2001:db8::2"
                    }
                ]
            },
            {
                "name": "DROP",
                "test": "member('UNKNOWN')"
            }
        ]})

    world.dhcp_cfg.update({
        "reservations": [
            {"duid": "00:03:00:01:f6:f5:f4:f3:f2:11",
             "client-classes": ["blocked"]},
            {"duid": "00:03:00:01:f6:f5:f4:f3:f2:22"}
        ], "reservation-mode": "global"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # Check blocked MAC
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:11')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(23)
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(23)
    srv_msg.response_check_option_content(23, 'value', '2001:db8::2')

    # Check other known MAC
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:22')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(23)
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE')
    srv_msg.response_check_include_option(23)
    srv_msg.response_check_option_content(23, 'value', '2001:db8::1')

    # Check unknown MAC
    misc.test_procedure()
    srv_msg.client_sets_value('Client', 'DUID', '00:03:00:01:f6:f5:f4:f3:f2:33')
    srv_msg.client_does_include('Client', 'client-id')
    srv_msg.client_does_include('Client', 'IA-NA')
    srv_msg.client_requests_option(7)
    srv_msg.client_requests_option(23)
    srv_msg.client_send_msg('SOLICIT')

    misc.pass_criteria()
    srv_msg.send_wait_for_message('MUST', 'ADVERTISE', expect_response=False)
