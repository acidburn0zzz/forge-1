# Copyright (C) 2020-2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Kea HA syncing"""

# pylint: disable=invalid-name,line-too-long,too-many-branches

import pytest

import misc
import srv_control
import srv_msg

from cb_model import setup_server_with_radius
from forge_cfg import world
from HA.steps import generate_leases, increase_mac, load_hook_libraries, wait_until_ha_state
from HA.steps import HOT_STANDBY, LOAD_BALANCING, PASSIVE_BACKUP
from softwaresupport import radius


# TODO add checking logs in all those tests


@pytest.fixture(autouse=True)
def kill_kea_on_second_system():
    # kill kea and clear data at the beginning and at the end
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)
    yield
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)


@pytest.mark.v6
@pytest.mark.ha
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_v6_hooks_HA_page_size_sync_mulitple_NA(hook_order):
    # HA SERVER 1
    misc.test_setup()
    srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::ffff')
    srv_control.config_srv_prefix('2001:db8:2::', 0, 48, 91)
    srv_control.config_srv_id('LLT', '00:01:00:02:52:7b:a8:f0:08:00:27:58:f1:e8')
    srv_control.open_control_channel()
    srv_control.agent_control_channel('$(MGMT_ADDRESS)')
    srv_control.add_hooks('libdhcp_lease_cmds.so')
    srv_control.add_ha_hook('libdhcp_ha.so')

    srv_control.update_ha_hook_parameter(HOT_STANDBY)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          'sync-page-limit': 2,
                                          "this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    misc.test_setup()
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)

    srv_control.config_srv_subnet('2001:db8:1::/64',
                                  '2001:db8:1::1-2001:db8:1::ffff',
                                  world.f_cfg.server2_iface)
    srv_control.config_srv_prefix('2001:db8:2::', 0, 48, 91)
    srv_control.config_srv_id('LLT', '00:01:00:02:52:7b:a8:f0:08:00:27:58:99:99')
    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address_2)

    load_hook_libraries('v6', hook_order)

    srv_control.update_ha_hook_parameter(HOT_STANDBY)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          'sync-page-limit': 2,
                                          "this-server-name": "server2"})
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    wait_until_ha_state('hot-standby')
    misc.test_procedure()

    set_of_leases_1 = generate_leases(leases_count=5, iaid=3, iapd=2)
    srv_msg.check_leases(set_of_leases_1)
    srv_msg.check_leases(set_of_leases_1, dest=world.f_cfg.mgmt_address_2)
    # srv_msg.forge_sleep(2, 'seconds')

    # srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                  '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log-CA',
    #                                  None,
    #                                  'Bulk apply of 4 IPv6 leases completed.')
    srv_control.start_srv('DHCP', 'stopped')
    wait_until_ha_state('partner-down', dest=world.f_cfg.mgmt_address_2)

    set_of_leases_2 = generate_leases(leases_count=5, iaid=3, iapd=2, mac="02:02:0c:03:0a:00")

    srv_control.start_srv('DHCP', 'started')
    wait_until_ha_state('hot-standby')

    srv_msg.check_leases(set_of_leases_1)
    srv_msg.check_leases(set_of_leases_2)


@pytest.mark.v4_bootp
@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.ha
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_HA_hot_standby_different_page_size_sync(dhcp_version, backend, hook_order):
    misc.test_setup()

    srv_control.define_temporary_lease_db_backend(backend)

    # we have to clear data on second system, before test forge does not know that we have multiple systems
    if dhcp_version == 'v6':
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::ffff')
    elif dhcp_version in ['v4', 'v4_bootp']:
        srv_control.config_srv_subnet('192.168.50.0/24', '192.168.50.1-192.168.50.200')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()
    srv_control.configure_loggers('kea-dhcp6.dhcpsrv', 'DEBUG', 99)
    srv_control.configure_loggers('kea-dhcp6.ha-hooks', 'DEBUG', 99)
    srv_control.configure_loggers('kea-ctrl-agent', 'DEBUG', 99, 'kea.log-CTRL')

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(HOT_STANDBY)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "sync-page-limit": 10,
                                          "this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    misc.test_setup()

    srv_control.define_temporary_lease_db_backend(backend)
    # we have to clear data on second system, before test forge does not know that we have multiple systems
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)

    if dhcp_version == 'v6':
        srv_control.config_srv_subnet('2001:db8:1::/64',
                                      '2001:db8:1::1-2001:db8:1::ffff',
                                      world.f_cfg.server2_iface)
    elif dhcp_version in ['v4', 'v4_bootp']:
        srv_control.config_srv_subnet('192.168.50.0/24',
                                      '192.168.50.1-192.168.50.200',
                                      world.f_cfg.server2_iface)

    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address_2)
    srv_control.configure_loggers(f'kea-dhcp{world.proto[1]}.dhcpsrv', 'DEBUG', 99)
    srv_control.configure_loggers(f'kea-dhcp{world.proto[1]}.ha-hooks', 'DEBUG', 99)
    srv_control.configure_loggers('kea-ctrl-agent', 'DEBUG', 99, 'kea.log-CTRL2')

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(HOT_STANDBY)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "sync-page-limit": 15,
                                          "this-server-name": "server2"})
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    wait_until_ha_state('hot-standby', dhcp_version=dhcp_version)
    set_of_leases_1 = generate_leases(leases_count=50, iaid=1, iapd=1, dhcp_version=dhcp_version)

    # turn off server2
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)
    # dump leases and logs of server2
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)
    # start clean server2
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)
    # let's wait for full synchronization of server2
    wait_until_ha_state('hot-standby', dhcp_version=dhcp_version)

    # misc.pass_criteria()
    # if dhcp_version == 'v6':
    #     srv_msg.log_contains('DHCPSRV_MEMFILE_GET_PAGE6 obtaining at most 15 IPv6 leases starting')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      None,
    #                                      'HA_LEASES_SYNC_LEASE_PAGE_RECEIVED received 15 leases from server1')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      'NOT ',
    #                                      'DHCPSRV_MEMFILE_GET_PAGE6 obtaining at most 10 IPv6 leases starting from address 2001:')
    #     srv_msg.log_doesnt_contain('HA_LEASES_SYNC_LEASE_PAGE_RECEIVED received 10 leases from')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      None,
    #                                      'HA_SYNC_SUCCESSFUL lease database synchronization with server1 completed successfully')
    # else:
    #     srv_msg.log_contains('DHCPSRV_MEMFILE_GET_PAGE4 obtaining at most 15 IPv4 leases starting')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      None,
    #                                      'HA_LEASES_SYNC_LEASE_PAGE_RECEIVED received 15 leases from server1')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      'NOT ',
    #                                      'DHCPSRV_MEMFILE_GET_PAGE6 obtaining at most 10 IPv4 leases starting from address =')
    #     srv_msg.log_doesnt_contain('HA_LEASES_SYNC_LEASE_PAGE_RECEIVED received 10 leases from')
    #     srv_msg.remote_log_includes_line(world.f_cfg.mgmt_address_2,
    #                                      '$(SOFTWARE_INSTALL_DIR)/var/log/kea.log',
    #                                      None,
    #                                      'HA_SYNC_SUCCESSFUL lease database synchronization with server1 completed successfully')

    # check if all leases are synced
    srv_msg.check_leases(set_of_leases_1, dest=world.f_cfg.mgmt_address_2, backend=backend)
    # stop server1
    srv_control.start_srv('DHCP', 'stopped')
    # dump leases and logs from server1
    srv_control.clear_some_data('all')
    # let's wait until secondary system switch status, we don't need elapsed time increased
    # due to server settings
    wait_until_ha_state('partner-down', dest=world.f_cfg.mgmt_address_2, dhcp_version=dhcp_version)

    # create leases in HA 2
    set_of_leases_2 = generate_leases(leases_count=50, iaid=1, iapd=1, dhcp_version=dhcp_version,
                                      mac="02:02:0c:03:0a:00")

    # start server1
    srv_control.start_srv('DHCP', 'started')
    # let's wait for full synchronization of server2
    wait_until_ha_state('hot-standby', dhcp_version=dhcp_version)

    # Check synced leases.
    srv_msg.check_leases(set_of_leases_1, backend=backend)
    srv_msg.check_leases(set_of_leases_2, backend=backend)


@pytest.mark.v4_bootp
@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.ha
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_HA_passive_backup_sync(dhcp_version, backend, hook_order):
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == 'v6':
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::ffff')
    elif dhcp_version in ['v4', 'v4_bootp']:
        srv_control.config_srv_subnet('192.168.50.0/24', '192.168.50.1-192.168.50.200')
    srv_control.open_control_channel()
    srv_control.agent_control_channel()

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(PASSIVE_BACKUP)
    srv_control.update_ha_hook_parameter({"this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    # we have to clear data on second system, before test forge does not know that we have multiple systems
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)

    if dhcp_version == 'v6':
        srv_control.config_srv_subnet('2001:db8:1::/64',
                                      '2001:db8:1::1-2001:db8:1::ffff',
                                      world.f_cfg.server2_iface)
    elif dhcp_version in ['v4', 'v4_bootp']:
        srv_control.config_srv_subnet('192.168.50.0/24',
                                      '192.168.50.1-192.168.50.200',
                                      world.f_cfg.server2_iface)

    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address_2)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(PASSIVE_BACKUP)
    srv_control.update_ha_hook_parameter({"this-server-name": "server2"})
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    wait_until_ha_state('passive-backup', dhcp_version=dhcp_version)
    set_of_leases_1 = generate_leases(leases_count=5, iaid=3, iapd=2, dhcp_version=dhcp_version)
    # we have no confirmation in syncing so just let's wait a bit
    srv_msg.forge_sleep(2, 'seconds')
    # check synced leases
    srv_msg.check_leases(set_of_leases_1, backend=backend)
    srv_msg.check_leases(set_of_leases_1, backend=backend, dest=world.f_cfg.mgmt_address_2)


# disabled, we know it fails due to design of HA load-balancing nothing will change here
@pytest.mark.v4_bootp
@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.disabled
@pytest.mark.ha
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_HA_load_balancing_sync(dhcp_version, backend, hook_order):
    # HA SERVER 1
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == "v6":
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::5')
        world.dhcp_cfg["subnet6"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet6"][0]["pools"].append({"pool": "2001:db8:1::100-2001:db8:1::110",
                                                      "client-class": "HA_server2"})
    else:
        srv_control.config_srv_subnet('192.168.50.0/24', '192.168.50.1-192.168.50.5')
        world.dhcp_cfg["subnet4"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet4"][0]["pools"].append({"pool": "192.168.50.20-192.168.50.30",
                                                      "client-class": "HA_server2"})
    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    # we have to clear data on second system, before test forge does not know that we have multiple systems
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)

    if dhcp_version == "v6":
        srv_control.config_srv_subnet('2001:db8:1::/64',
                                      '2001:db8:1::1-2001:db8:1::5',
                                      world.f_cfg.server2_iface)
        world.dhcp_cfg["subnet6"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet6"][0]["pools"].append({"pool": "2001:db8:1::100-2001:db8:1::110",
                                                      "client-class": "HA_server2"})
    else:
        srv_control.config_srv_subnet('192.168.50.0/24',
                                      '192.168.50.1-192.168.50.5',
                                      world.f_cfg.server2_iface)
        world.dhcp_cfg["subnet4"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet4"][0]["pools"].append({"pool": "192.168.50.20-192.168.50.30",
                                                      "client-class": "HA_server2"})

    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address_2)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "this-server-name": "server2"})
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version)
    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)

    misc.test_procedure()
    # get 10 leases
    set_of_leases_1 = generate_leases(leases_count=10, iaid=1, iapd=0, dhcp_version=dhcp_version)

    # check if there are indeed saved
    srv_msg.check_leases(set_of_leases_1, backend=backend)
    # check if those were propagated to other system
    srv_msg.check_leases(set_of_leases_1, dest=world.f_cfg.mgmt_address_2, backend=backend)
    # turn off server2
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)
    # dump leases and logs of server2
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)
    # start clean server2
    wait_until_ha_state('partner-down', dhcp_version=dhcp_version)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)
    # let's wait for full synchronization of server2
    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version)
    # check leases on server2
    srv_msg.check_leases(set_of_leases_1, dest=world.f_cfg.mgmt_address_2, backend=backend)

    # turn off server1
    srv_control.start_srv('DHCP', 'stopped')
    # dump leases and logs of server2
    srv_control.clear_some_data('all')
    # start clean server1
    wait_until_ha_state('partner-down', dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started')
    # let's wait for full synchronization of server1
    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version)
    # check leases on server1
    srv_msg.check_leases(set_of_leases_1, backend=backend)


@pytest.mark.v4_bootp
@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.disabled
@pytest.mark.ha
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_HA_load_balancing_both_scopes_for_primary(dhcp_version, backend, hook_order):
    # HA SERVER 1
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == "v6":
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::20')
        world.dhcp_cfg["subnet6"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet6"][0]["pools"].append({"pool": "2001:db8:1::100-2001:db8:1::120",
                                                      "client-class": "HA_server2"})
    else:
        srv_control.config_srv_subnet('192.168.50.0/24', '192.168.50.1-192.168.50.20')
        world.dhcp_cfg["subnet4"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet4"][0]["pools"].append({"pool": "192.168.50.100-192.168.50.120",
                                                      "client-class": "HA_server2"})
    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 100,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 2,
                                          "this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    # we don't need it, server1 wont detect server2 and will go straight to partner-down

    resp = wait_until_ha_state('partner-down', dhcp_version=dhcp_version)
    # wait_until_ha_state('load-balancing', dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)
    assert "server2" in resp["arguments"]["scopes"]
    assert "server1" in resp["arguments"]["scopes"]
    misc.test_procedure()
    # get 10 leases some form server1 and some from server2
    l_count = 40
    set_of_leases_1 = generate_leases(leases_count=l_count, iaid=1, iapd=0, dhcp_version=dhcp_version)
    assert l_count == len(set_of_leases_1), "Server didn't give us all leases it had configured"
    srv_msg.check_leases(set_of_leases_1)


@pytest.mark.v4_bootp
@pytest.mark.v4
@pytest.mark.v6
@pytest.mark.disabled
@pytest.mark.ha
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('hook_order', ['alphabetical'])  # possible params:  'reverse'
def test_HA_load_balancing_both_scopes_for_secondary(dhcp_version, backend, hook_order):
    # HA SERVER 1
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    if dhcp_version == "v6":
        srv_control.config_srv_subnet('2001:db8:1::/64', '2001:db8:1::1-2001:db8:1::20')
        world.dhcp_cfg["subnet6"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet6"][0]["pools"].append({"pool": "2001:db8:1::100-2001:db8:1::120",
                                                      "client-class": "HA_server2"})
    else:
        srv_control.config_srv_subnet('192.168.50.0/24', '192.168.50.1-192.168.50.20')
        world.dhcp_cfg["subnet4"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet4"][0]["pools"].append({"pool": "192.168.50.100-192.168.50.120",
                                                      "client-class": "HA_server2"})
    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "this-server-name": "server1"})

    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # HA SERVER 2
    misc.test_setup()
    srv_control.define_temporary_lease_db_backend(backend)
    # we have to clear data on second system, before test forge does not know that we have multiple systems
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)

    if dhcp_version == "v6":
        srv_control.config_srv_subnet('2001:db8:1::/64',
                                      '2001:db8:1::1-2001:db8:1::20',
                                      world.f_cfg.server2_iface)
        world.dhcp_cfg["subnet6"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet6"][0]["pools"].append({"pool": "2001:db8:1::100-2001:db8:1::120",
                                                      "client-class": "HA_server2"})
    else:
        srv_control.config_srv_subnet('192.168.50.0/24',
                                      '192.168.50.1-192.168.50.20',
                                      world.f_cfg.server2_iface)
        world.dhcp_cfg["subnet4"][0]["pools"][0].update({"client-class": "HA_server1"})
        world.dhcp_cfg["subnet4"][0]["pools"].append({"pool": "192.168.50.100-192.168.50.120",
                                                      "client-class": "HA_server2"})

    srv_control.open_control_channel()
    srv_control.agent_control_channel(world.f_cfg.mgmt_address_2)

    load_hook_libraries(dhcp_version, hook_order)

    srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    srv_control.update_ha_hook_parameter({"heartbeat-delay": 1000,
                                          "max-ack-delay": 0,
                                          "max-response-delay": 1500,
                                          "max-unacked-clients": 0,
                                          "this-server-name": "server2"})  # this is now secondary!
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version)
    wait_until_ha_state('load-balancing', dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)

    # kill server1 and wait for secondary to go partner-down
    srv_control.start_srv('DHCP', 'stopped')
    resp = wait_until_ha_state('partner-down', dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)
    assert "server2" in resp["arguments"]["scopes"]
    assert "server1" in resp["arguments"]["scopes"]
    misc.test_procedure()
    # get 10 leases some form server1 and some from server2
    l_count = 40
    set_of_leases_1 = generate_leases(leases_count=l_count, iaid=1, iapd=0, dhcp_version=dhcp_version)
    assert l_count == len(set_of_leases_1), "Server gave us %d leases, we wanted %d" % (len(set_of_leases_1), l_count)
    srv_msg.check_leases(set_of_leases_1, dest=world.f_cfg.mgmt_address_2)


def _add_ha_pools():
    """
    Add pools for the usual HA traffic coming from generate_leases().
    NOTE: Relying on leases being assigned to pools according to the order they
    are declared in the configuration is discouraged and is considered undefined
    behavior in Kea. Empirically, the pool order does influence the lease
    process and we rely on it in this test such that HA traffic gets the traffic
    from the first pool and the rest is left for RADIUS traffic. So these pools
    are added to the beginning, starting with 50.11 or 50::11 because lower
    values are used in RADIUS testing.
    """
    v = world.proto[1]
    if world.proto == 'v4':
        if f'subnet{v}' in world.dhcp_cfg:
            world.dhcp_cfg[f'subnet{v}'][0]['pools'].insert(0, {
                'pool': '192.168.50.11 - 192.168.50.110'
            })
        elif 'shared-networks' in world.dhcp_cfg:
            world.dhcp_cfg['shared-networks'][0][f'subnet{v}'][0]['pools'].insert(0, {
                'pool': '192.168.50.11 - 192.168.50.110'
            })
    elif world.proto == 'v6':
        if f'subnet{v}' in world.dhcp_cfg:
            world.dhcp_cfg[f'subnet{v}'][0]['pools'].insert(0, {
                'pool': '2001:db8:50::11 - 2001:db8:50::110'
            })
        elif 'shared-networks' in world.dhcp_cfg:
            world.dhcp_cfg['shared-networks'][0][f'subnet{v}'][0]['pools'].insert(0, {
                'pool': '2001:db8:50::11 - 2001:db8:50::110'
            })


# Disable until the RADIUS subnet selection is solved. See test_radius_giaddr().
@pytest.mark.disabled
@pytest.mark.v4
@pytest.mark.v4_bootp
@pytest.mark.v6
@pytest.mark.ha
@pytest.mark.radius
@pytest.mark.parametrize('backend', ['memfile', 'mysql', 'postgresql'])
@pytest.mark.parametrize('ha_mode', ['hot-standby', 'load-balancing', 'passive-backup'])
@pytest.mark.parametrize('hook_order', ['alphabetical', 'reverse'])
@pytest.mark.parametrize('config_type', ['network', 'multiple-subnets'])
@pytest.mark.parametrize('has_reservation', ['client-has-reservation-in-radius', 'client-has-no-reservation-in-radius'])
def test_HA_and_RADIUS(dhcp_version: str,
                       backend: str,
                       ha_mode: str,
                       hook_order: str,
                       config_type: str,
                       has_reservation: str):
    """
    Check that HA and RADIUS can work together.

    :param dhcp_version: the DHCP version being tested
    :param backend: the lease database backend type
    :param ha_mode: the HA mode: HS, LB or PB
    :param hook_order: the order in which hooks are loaded: either aplhabetical
        or reverse alphabetical. This is to test all order combinations for each
        set of two hook libraries after problems were found in one case where HA
        and leasequery were loaded in a certain order.
    :param config_type: different configurations used in testing
    :param has_reservation: whether the first client coming in with a request has its lease or pool reserved in RADIUS
    """

    # Constants
    leases_count = 50
    starting_mac = '01:02:0c:03:0a:00'
    starting_mac_2 = '02:02:0c:03:0a:00'

    # Start with 10 to avoid RADIUS pools which are below 10.
    last_octet = 10
    authorize_content = ''
    for mac in [starting_mac, starting_mac_2]:
        for _ in range(leases_count):
            last_octet = last_octet + 1
            mac = increase_mac(mac)
            # Leave {p} unchanged. It is formatted in radius.init_and_start_radius().
            authorize_content += '''
{p}:{mac}    Cleartext-password := "{mac}"
    \tFramed-IP-Address = "192.168.50.{last_octet}",
    \tFramed-IPv6-Address = "2001:db8:50::{last_octet}"
'''.format(p='{p}', mac=mac, last_octet=last_octet)

    # ---- HA server1 ----
    misc.test_setup()

    # Clear data.
    srv_control.clear_some_data('all')

    # Setup the RADIUS server.
    radius.init_and_start_radius(authorize_content=authorize_content)

    # Some useful variables
    addresses, configs = radius.get_test_case_variables()

    # Configure RADIUS in Kea. Server also starts here which is an
    # unfortunate side effect, but we'll restart after finishing
    # configuration below.
    setup_server_with_radius(**configs[config_type])

    # Configure the backend.
    srv_control.define_temporary_lease_db_backend(backend)

    # Start kea-ctrl-agent and configure the control socket in Kea.
    srv_control.agent_control_channel()
    srv_control.open_control_channel()

    # Load necessary hook libraries.
    load_hook_libraries(dhcp_version, hook_order)

    # Configure HA.
    if ha_mode == 'hot-standby':
        srv_control.update_ha_hook_parameter(HOT_STANDBY)
    elif ha_mode == 'load-balancing':
        srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    elif ha_mode == 'passive-backup':
        srv_control.update_ha_hook_parameter(PASSIVE_BACKUP)
    srv_control.update_ha_hook_parameter({'heartbeat-delay': 1000,
                                          'max-ack-delay': 0,
                                          'max-response-delay': 1500,
                                          'max-unacked-clients': 0,
                                          'sync-page-limit': 10,
                                          'this-server-name': 'server1'})

    # Add a leading subnet to test subnet reselection in RADIUS.
    radius.add_leading_subnet()

    # Add pools for the usual HA traffic coming from generate_leases().
    _add_ha_pools()

    # Start Kea.
    srv_control.build_and_send_config_files()
    srv_control.start_srv('DHCP', 'started')

    # ---- HA server2 ----
    misc.test_setup()

    # Clear data.
    srv_control.clear_some_data('all', dest=world.f_cfg.mgmt_address_2)

    # Setup the RADIUS server.
    radius.init_and_start_radius(authorize_content=authorize_content,
                                 destination=world.f_cfg.mgmt_address_2)

    # Get the server2-specific variables again.
    _, configs = radius.get_test_case_variables(interface=world.f_cfg.server2_iface)

    # Configure RADIUS in Kea. Server also starts here which is an
    # unfortunate side effect, but we'll restart after finishing
    # configuration below.
    setup_server_with_radius(destination=world.f_cfg.mgmt_address_2,
                             interface=world.f_cfg.server2_iface,
                             **configs[config_type])

    # radius.setup_server_with_radius() was used for server2 to generate a
    # configuration that is identical to server1's config, but the one thing we
    # don't necessarily need in server2 is RADIUS functionality.
    srv_control.delete_hooks(['libdhcp_radius.so'])

    # Configure the backend.
    srv_control.define_temporary_lease_db_backend(backend)

    # Start kea-ctrl-agent and configure the control socket in Kea.
    srv_control.agent_control_channel(host_address=world.f_cfg.mgmt_address_2)
    srv_control.open_control_channel()

    # Load necessary hook libraries.
    load_hook_libraries(dhcp_version, hook_order)

    # Configure HA.
    if ha_mode == 'hot-standby':
        srv_control.update_ha_hook_parameter(HOT_STANDBY)
    elif ha_mode == 'load-balancing':
        srv_control.update_ha_hook_parameter(LOAD_BALANCING)
    elif ha_mode == 'passive-backup':
        srv_control.update_ha_hook_parameter(PASSIVE_BACKUP)
    srv_control.update_ha_hook_parameter({'heartbeat-delay': 1000,
                                          'max-ack-delay': 0,
                                          'max-response-delay': 1500,
                                          'max-unacked-clients': 0,
                                          'sync-page-limit': 15,
                                          'this-server-name': 'server2'})
    world.dhcp_cfg['interfaces-config']['interfaces'] = [world.f_cfg.server2_iface]

    # Add a leading subnet to test subnet reselection in RADIUS.
    radius.add_leading_subnet()

    # Add pools for the usual HA traffic coming from generate_leases().
    _add_ha_pools()

    # Start Kea.
    srv_control.build_and_send_config_files(dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    # Settle was the HA state should be for server2 in normal functioning mode.
    ha_mode_2 = ha_mode
    if ha_mode == 'passive-backup':
        ha_mode_2 = 'backup'

    # ---- Start testing. ----

    # Wait for both servers to reach functioning states.
    wait_until_ha_state(ha_mode, dhcp_version=dhcp_version)
    wait_until_ha_state(ha_mode_2, dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)

    # Exchange some messages and make sure leases are given.
    set_of_leases = generate_leases(dhcp_version=dhcp_version,
                                    iaid=1,
                                    iapd=1,
                                    leases_count=leases_count,
                                    mac=starting_mac)

    # Check that both servers have all the leases in the backends.
    srv_msg.check_leases(set_of_leases, backend=backend, dest=world.f_cfg.mgmt_address)
    srv_msg.check_leases(set_of_leases, backend=backend, dest=world.f_cfg.mgmt_address_2)

    # Restart server2.
    srv_control.start_srv('DHCP', 'stopped', dest=world.f_cfg.mgmt_address_2)
    srv_control.start_srv('DHCP', 'started', dest=world.f_cfg.mgmt_address_2)

    # Wait for both servers to reach functioning states.
    wait_until_ha_state(ha_mode, dhcp_version=dhcp_version)
    wait_until_ha_state(ha_mode_2, dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)

    # Check that both servers have all the leases in the backends.
    srv_msg.check_leases(set_of_leases, backend=backend, dest=world.f_cfg.mgmt_address)
    srv_msg.check_leases(set_of_leases, backend=backend, dest=world.f_cfg.mgmt_address_2)

    if ha_mode in ['hot-standby', 'load-balancing']:
        # Stop server1.
        srv_control.start_srv('DHCP', 'stopped')

        # Wait until server2 switches status.
        wait_until_ha_state('partner-down',
                            dest=world.f_cfg.mgmt_address_2,
                            dhcp_version=dhcp_version)

    # Exchange some more messages and make sure leases are given.
    set_of_leases_2 = generate_leases(dhcp_version=dhcp_version,
                                      iaid=1,
                                      iapd=1,
                                      leases_count=leases_count,
                                      mac=starting_mac_2)

    if ha_mode in ['hot-standby', 'load-balancing']:
        # Start server1.
        srv_control.start_srv('DHCP', 'started')

        # Wait for both servers to reach functioning states.
        wait_until_ha_state(ha_mode, dhcp_version=dhcp_version)
        wait_until_ha_state(ha_mode_2, dhcp_version=dhcp_version, dest=world.f_cfg.mgmt_address_2)

    # Exchange some messages and make sure leases are given with clients that
    # are configured in RADIUS.
    radius_leases = radius.send_and_receive(config_type, has_reservation, addresses)

    # Check that both servers have all the leases in the backends.
    for leases in [set_of_leases, set_of_leases_2, radius_leases]:
        for dest in [world.f_cfg.mgmt_address, world.f_cfg.mgmt_address_2]:
            srv_msg.check_leases(leases, backend=backend, dest=dest)
