# Copyright (C) 2013-2023 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# pylint: disable=consider-iterating-dictionary
# pylint: disable=consider-using-f-string
# pylint: disable=consider-using-in
# pylint: disable=invalid-name
# pylint: disable=line-too-long
# pylint: disable=no-else-return
# pylint: disable=possibly-unused-variable
# pylint: disable=superfluous-parens
# pylint: disable=unspecified-encoding
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-nested-blocks

import datetime
import re
import os
import glob
import json
import logging

from src import srv_msg

from src.forge_cfg import world
from src.misc import merge_containers
from src.protosupport.multi_protocol_functions import add_variable, substitute_vars
from src.protosupport.multi_protocol_functions import remove_file_from_server, copy_file_from_server
from src.protosupport.multi_protocol_functions import wait_for_message_in_log
from src.softwaresupport.multi_server_functions import fabric_run_command, fabric_send_file, remove_local_file
from src.softwaresupport.multi_server_functions import copy_configuration_file, fabric_sudo_command
from src.softwaresupport.multi_server_functions import fabric_remove_file_command, fabric_download_file
from src.softwaresupport.multi_server_functions import check_local_path_for_downloaded_files

log = logging.getLogger('forge')


# kea_otheroptions was originally designed for vendor options
# because codes sometime overlap with basic options
kea_otheroptions = {
    "tftp-servers": 32,
    "config-file": 33,
    "syslog-servers": 34,
    "device-id": 36,
    "time-servers": 37,
    "time-offset": 38
}

world.kea_options6 = {
    "client-id": 1,
    "server-id": 2,
    "IA_NA": 3,
    "IN_TA": 4,
    "IA_address": 5,
    "preference": 7,
    "elapsedtime": 8,
    "relay-msg": 9,
    "unicast": 12,
    "status-code": 13,
    "rapid_commit": 14,
    "interface-id": 18,
    "sip-server-dns": 21,
    "sip-server-addr": 22,
    "dns-servers": 23,
    "domain-search": 24,
    "IA_PD": 25,
    "IA-Prefix": 26,
    "nis-servers": 27,
    "nisp-servers": 28,
    "nis-domain-name": 29,
    "nisp-domain-name": 30,
    "sntp-servers": 31,
    "information-refresh-time": 32,
    "bcmcs-server-dns": 33,
    "bcmcs-server-addr": 34,
    "pana-agent": 40,
    "new-posix-timezone": 41,
    "new-tzdb-timezone": 42,
    "lq-client-link": 48,
    "bootfile-url": 59,
    "bootfile-param": 60,
    "erp-local-domain-name": 65
}

world.kea_options4 = {
    "subnet-mask": 1,  # ipv4-address (array)
    "time-offset": 2,
    "routers": 3,  # ipv4-address (single)
    "time-servers": 4,  # ipv4-address (single)
    "name-servers": 5,  # ipv4-address (array)
    "domain-name-servers": 6,  # ipv4-address (array)
    "log-servers": 7,  # ipv4-address (single)
    "cookie-servers": 8,  # ipv4-address (single)
    "lpr-servers": 9,  # ipv4-address (single)
    "impress-servers": 10,  # ipv4-address (single)
    "resource-location-servers": 11,  # ipv4-address (single)
    "host-name": 12,  # string
    "boot-size": 13,
    "merit-dump": 14,  # string
    "domain-name": 15,  # fqdn (single)
    "swap-server": 16,  # ipv4-address (single)
    "root-path": 17,  # string
    "extensions-path": 18,  # string
    "ip-forwarding": 19,  # boolean
    "non-local-source-routing": 20,  # boolean
    "policy-filter": 21,  # ipv4-address (single)
    "max-dgram-reassembly": 22,
    "default-ip-ttl": 23,
    "path-mtu-aging-timeout": 24,
    "path-mtu-plateau-table": 25,
    "interface-mtu": 26,
    "all-subnets-local": 27,  # boolean
    "broadcast-address": 28,  # ipv4-address (single)
    "perform-mask-discovery": 29,  # boolean
    "mask-supplier": 30,  # boolean
    "router-discovery": 31,  # boolean
    "router-solicitation-address": 32,  # ipv4-address (single)
    "static-routes": 33,  # ipv4-address (array)
    "trailer-encapsulation": 34,  # boolean
    "arp-cache-timeout": 35,
    "ieee802-3-encapsulation": 36,
    "default-tcp-ttl": 37,
    "tcp-keepalive-interval": 38,
    "tcp-keepalive-garbage": 39,  # boolean
    "nis-domain": 40,  # string (single)
    "nis-servers": 41,  # ipv4-address (array)
    "ntp-servers": 42,  # ipv4-address (array)
    "vendor-encapsulated-options": 43,  # empty
    "netbios-name-servers": 44,  # ipv4-address
    "netbios-dd-server": 45,  # ipv4-address
    "netbios-node-type": 46,  # uint8
    "netbios-scope": 47,  # string
    "font-servers": 48,  # ipv4-address
    "x-display-manager": 49,  # ipv4-address
    "dhcp-requested-address": 50,  # ipv4-address
    "dhcp-option-overload": 52,  # uint8
    "server_id": 54,
    "dhcp-server-identifier": 54,
    "dhcp-message": 56,  # string
    "dhcp-max-message-size": 57,  # uint16
    "vendor-class-identifier": 60,  # binary
    "client_id": 61,
    "nwip-domain-name": 62,  # string
    "nwip-suboptions": 63,  # binary
    "nisplus-domain-name": 64,  # string
    "nisplus-servers": 65,  # ipv4-address (array)
    "boot-file-name": 67,  # string
    "mobile-ip-home-agent": 68,  # ipv4-address (array)
    "smtp-server": 69,  # ipv4-address (array)
    "pop-server": 70,  # ipv4-address (array)
    "nntp-server": 71,  # ipv4-address (array)
    "www-server": 72,  # ipv4-address (array)
    "finger-server": 73,  # ipv4-address (array)
    "irc-server": 74,  # ipv4-address (array)
    "streettalk-server": 75,  # ipv4-address (array)
    "streettalk-directory-assistance-server": 76,  # ipv4-address (array)
    "user_class": 77,  # binary
    "fqdn": 81,  # record
    "dhcp-agent-options": 82,  # empty
    "authenticate": 90,  # binary
    "client-last-transaction-time": 91,  # uint32
    "associated-ip": 92,  # ipv4-address
    "subnet-selection": 118,  # ipv4-address
    "domain-search": 119,  # binary
    "vivco-suboptions": 124,  # binary
    "vivso-suboptions": 125,  # binary
    "end": 255
}


class CreateCert:
    """
    This class creates TLS certificates for CA, server and client,
    mostly for testing Control Agent with TLS.
    class attributes return certificate files paths on server.
    eg. CreateCert.ca_key returns "/home/user/kea/ca_key.pem"

    download() function downloads selected certificate to test result directory on forge machine
    and returns full path of the file.
    """
    def __init__(self):
        # Assign certificate files paths to attributes.
        self.ca_key = world.f_cfg.data_join('ca_key.pem')
        self.ca_cert = world.f_cfg.data_join('ca_cert.pem')
        self.server_cert = world.f_cfg.data_join('server_cert.pem')
        self.server_csr = world.f_cfg.data_join('server_csr.csr')
        self.server_key = world.f_cfg.data_join('server_key.pem')
        self.client_cert = world.f_cfg.data_join('client_cert.pem')
        self.client_csr = world.f_cfg.data_join('client_csr.csr')
        self.client_key = world.f_cfg.data_join('client_key.pem')
        if world.f_cfg.mgmt_address_2 != '':
            self.server2_cert = world.f_cfg.data_join('server2_cert.pem')
            self.server2_csr = world.f_cfg.data_join('server2_csr.csr')
            self.server2_key = world.f_cfg.data_join('server2_key.pem')

        # Delete leftover certificates.
        self.clear()
        # Generate certificates.
        self.generate()

    @staticmethod
    def change_access(p):
        if isinstance(p, list):
            p = " ".join(p)
        fabric_sudo_command(f'chmod 644 {p}')

    def clear(self, name: str = None):
        """
        Remove all default keys and certs or just one singled out by name
        :param name: name of a cert/key to be removed
        """
        if name is not None:
            remove_file_from_server(name)
            return
        # Delete leftover certificates.
        remove_file_from_server(self.ca_key)
        remove_file_from_server(self.ca_cert)
        remove_file_from_server(self.server_cert)
        remove_file_from_server(self.server_csr)
        remove_file_from_server(self.server_key)
        remove_file_from_server(self.client_cert)
        remove_file_from_server(self.client_csr)
        remove_file_from_server(self.client_key)
        if world.f_cfg.mgmt_address_2 != '':
            remove_file_from_server(self.server2_cert)
            remove_file_from_server(self.server2_csr)
            remove_file_from_server(self.server2_key)

    def generate(self):
        """
        Generate certs and keys with default names and location
        """
        self.generate_ca()
        self.generate_server()
        self.generate_client()
        if world.f_cfg.mgmt_address_2 != '':
            self.generate_server_2()

    def generate_ca(self,
                    ca_name: str = "Kea",
                    ca_key_name: str = None,
                    ca_cert_name: str = None):
        """
        Generate CA ( Certificate authority ) cert and key on remote system, and change access right of generated files
        :param ca_name: CN name of cert
        :param ca_key_name: name of key output file
        :param ca_cert_name: name of cert output file
        """
        key = self.ca_key if ca_key_name is None else world.f_cfg.data_join(ca_key_name)
        cert = self.ca_cert if ca_cert_name is None else world.f_cfg.data_join(ca_cert_name)

        generate_ca = f'openssl req ' \
                      f'-x509 ' \
                      f'-nodes ' \
                      f'-days 3650 ' \
                      f'-newkey rsa:4096 ' \
                      f'-keyout {key} ' \
                      f'-out {cert} ' \
                      f'-subj "/C=US/ST=Acme State/L=Acme City/O=Acme Inc./CN={ca_name}"'
        fabric_sudo_command(generate_ca)
        self.change_access([key, cert])

    def generate_server(self,
                        cn: str = world.f_cfg.mgmt_address,
                        server_key_name: str = None,
                        server_csr_name: str = None,
                        server_cert_name: str = None,
                        ca_cert_name: str = None,
                        ca_key_name: str = None):
        """
        Generate server cert and key, sign it with previously generated CA, change access rights
        :param cn: CN parameter of a key
        :param server_key_name: name of server key output file
        :param server_csr_name: name of server csr output file
        :param server_cert_name: name of server cert output file
        :param ca_cert_name: name of CA cert file
        :param ca_key_name: name of CA key file
        """
        s_key = self.server_key if server_key_name is None else world.f_cfg.data_join(server_key_name)
        s_csr = self.server_csr if server_csr_name is None else world.f_cfg.data_join(server_csr_name)
        s_crt = self.server_cert if server_cert_name is None else world.f_cfg.data_join(server_cert_name)

        serv_prv = f'openssl genrsa -out {s_key} 4096 ; ' \
                   f'openssl req ' \
                   f'-new ' \
                   f'-key {s_key} ' \
                   f'-out {s_csr} ' \
                   f'-subj "/C=US/ST=Acme State/L=Acme City/O=Acme Inc./CN={cn}"'

        # Sign server cert
        server = f'openssl x509 -req ' \
                 f'-days 1460 ' \
                 f'-in {s_csr} ' \
                 f'-CA {self.ca_cert if ca_cert_name is None else world.f_cfg.data_join(ca_cert_name)} ' \
                 f'-CAkey {self.ca_key if ca_key_name is None else world.f_cfg.data_join(ca_key_name)} ' \
                 f'-CAcreateserial -out {s_crt} ' \
                 f'-extensions SAN ' \
                 f'-extfile <(cat /etc/ssl/openssl.cnf' \
                 f' <(printf "\n[SAN]\nsubjectAltName=IP:{world.f_cfg.mgmt_address}"))'

        fabric_sudo_command(serv_prv)
        fabric_sudo_command(server)
        self.change_access([s_key, s_csr, s_crt])

    def generate_client(self, cn: str = 'client',
                        client_key_name: str = None,
                        client_csr_name: str = None,
                        ca_cert_name: str = None,
                        ca_key_name: str = None,
                        client_cert_name: str = None):
        """
        Generate client cert and key, sign it with previously generated CA, change access rights
        :param cn: CN parameter of a key
        :param client_key_name:
        :param client_csr_name:
        :param ca_cert_name:
        :param ca_key_name:
        :param client_cert_name:
        :return:
        """
        c_key = self.client_key if client_key_name is None else world.f_cfg.data_join(client_key_name)
        c_crt = self.client_cert if client_cert_name is None else world.f_cfg.data_join(client_cert_name)
        c_csr = self.client_csr if client_csr_name is None else world.f_cfg.data_join(client_csr_name)
        remove_file_from_server(f'{c_key} {c_crt} {c_csr}')
        # Generate client cert and key
        cli_prv = f'openssl genrsa -out {c_key} 4096 ; ' \
                  f'openssl req ' \
                  f'-new ' \
                  f'-key {c_key} ' \
                  f'-out {c_csr} ' \
                  f'-subj "/C=US/ST=Acme State/L=Acme City/O=Acme Inc./CN={cn}"'

        # Sign client cert
        cli_crt = f'openssl x509 -req ' \
                  f'-days 1460 ' \
                  f'-in {c_csr} ' \
                  f'-CA {self.ca_cert if ca_cert_name is None else world.f_cfg.data_join(ca_cert_name)} ' \
                  f'-CAkey {self.ca_key if ca_key_name is None else world.f_cfg.data_join(ca_key_name)} ' \
                  f'-CAcreateserial -out {c_crt} '

        fabric_sudo_command(cli_prv)
        fabric_sudo_command(cli_crt)
        self.change_access([c_key, c_crt, c_csr])

    def generate_server_2(self, cn: str = world.f_cfg.mgmt_address_2,
                          server_key_name: str = None,
                          server_csr_name: str = None,
                          server_cert_name: str = None,
                          ca_cert_name: str = None,
                          ca_key_name: str = None):
        """

        :param cn:
        :param server_key_name:
        :param server_csr_name:
        :param server_cert_name:
        :param ca_cert_name:
        :param ca_key_name:
        :return:
        """
        s_key = self.server2_key if server_key_name is None else world.f_cfg.data_join(server_key_name)
        s_csr = self.server2_csr if server_csr_name is None else world.f_cfg.data_join(server_csr_name)
        s_crt = self.server2_cert if server_cert_name is None else world.f_cfg.data_join(server_cert_name)
        # Generate server cert and key
        serv_prv = f'openssl genrsa -out {s_key} 4096 ; ' \
                   f'openssl req ' \
                   f'-new ' \
                   f'-key {self.server2_key} ' \
                   f'-out {s_csr} ' \
                   f'-subj "/C=US/ST=Acme State/L=Acme City/O=Acme Inc./CN={cn}"'

        # Sign server cert
        serv = f'openssl x509 -req ' \
               f'-days 1460 ' \
               f'-in {s_csr} ' \
               f'-CA {self.ca_cert if ca_cert_name is None else world.f_cfg.data_join(ca_cert_name)} ' \
               f'-CAkey {self.ca_key if ca_key_name is None else world.f_cfg.data_join(ca_key_name)} ' \
               f'-CAcreateserial -out {s_crt} ' \
               f'-extensions SAN ' \
               f'-extfile <(cat /etc/ssl/openssl.cnf' \
               f' <(printf "\n[SAN]\nsubjectAltName=IP:{world.f_cfg.mgmt_address_2}"))'

        fabric_sudo_command(serv_prv)
        fabric_sudo_command(serv)
        self.change_access([s_key, s_csr, s_crt])

    def download(self, cert_name: str = None):
        """ This function downloads selected certificate to test result directory on forge machine
        and returns full path of the file.
        If no certificate name is provided, then function will download all of them
        and return dictionary of name and full file path

        :param cert_name: Select certificate to download or None to download all.
        :return: Full path of the downloaded file on Forge machine or dict with names and path of certificates.
        """
        if cert_name is None:
            certs = {}
            for name, path in self.__dict__.items():
                copy_file_from_server(path, f'{name}.pem')
                certs[name] = path
            return certs
        else:
            if cert_name in self.__dict__.keys():
                copy_file_from_server(self.__dict__[cert_name], f'{cert_name}.pem')
                return os.path.join(world.cfg["test_result_dir"], f'{cert_name}.pem')
            else:
                copy_file_from_server(world.f_cfg.data_join(cert_name), cert_name)
                return os.path.join(world.cfg["test_result_dir"], cert_name)


def generate_certificate():
    return CreateCert()


def _get_option_code(option_name: str):
    """
    Look for option code of standard option
    :param option_name: string option name
    :return: int, option code
    """
    if world.proto == 'v4':
        option_code = world.kea_options4.get(option_name)
    else:
        option_code = world.kea_options6.get(option_name)
        if option_code is None:
            option_code = kea_otheroptions.get(option_name)
    return option_code


def _check_value(value):
    # test_define_value from protosupport.multi_protocol_functions mostly return strings
    # we want to check if string should be boolean or digit and correct type, if not return unchanged value
    if isinstance(value, str):
        if value.isdigit():
            return int(value)
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return value


def add_defaults4():
    # TODO for now I will just change if condition but the way to go is remove pre-setting timers!
    # although it could affect too many tests, at this point I wont do it
    if "renew-timer" not in world.dhcp_cfg:
        world.dhcp_cfg["renew-timer"] = world.cfg["server_times"]["renew-timer"]
    if "rebind-timer" not in world.dhcp_cfg:
        world.dhcp_cfg["rebind-timer"] = world.cfg["server_times"]["rebind-timer"]
    if "valid-lifetime" not in world.dhcp_cfg:
        world.dhcp_cfg["valid-lifetime"] = world.cfg["server_times"]["valid-lifetime"]

    iface = world.f_cfg.server_iface
    add_interface(iface, add_to_existing=False)


def add_defaults6():
    if "renew-timer" not in world.dhcp_cfg:
        world.dhcp_cfg["renew-timer"] = world.cfg["server_times"]["renew-timer"]
    if "rebind-timer" not in world.dhcp_cfg:
        world.dhcp_cfg["rebind-timer"] = world.cfg["server_times"]["rebind-timer"]
    if "preferred-lifetime" not in world.dhcp_cfg:
        world.dhcp_cfg["preferred-lifetime"] = world.cfg["server_times"]["preferred-lifetime"]
    if "valid-lifetime" not in world.dhcp_cfg:
        world.dhcp_cfg["valid-lifetime"] = world.cfg["server_times"]["valid-lifetime"]

    iface = world.f_cfg.server_iface
    add_interface(iface, add_to_existing=False)


def add_logger(log_type, severity, severity_level, logging_file=None, merge_by_name=True):
    """
    Adds a logger with specified values to the Kea configuration.
    :param log_type: name of the logger (e.g. 'kea-dhcp6', 'kea-dhcp6.options')
    :param severity: logger severity (e.g. 'DEBUG', 'INFO')
    :param severity_level: debug level
    :param logging_file: the output for the log messages ('stdout', 'syslog', or file name)
    :param merge_by_name: whether to merge into other existing loggers if the name is matched.
                          True by default. If False, the logger is simply added without any checks.
    """
    if world.f_cfg.install_method == 'make':
        if logging_file is None:
            logging_file = 'kea.log'
        logging_file_path = world.f_cfg.log_join(logging_file)
    else:
        if logging_file is None or logging_file == 'stdout':
            logging_file_path = 'syslog'
            if world.server_system == 'alpine':
                logging_file = f'kea-dhcp{world.proto[1]}.log'
                logging_file_path = world.f_cfg.log_join(logging_file)
        else:
            logging_file_path = world.f_cfg.log_join(logging_file)

    logger = {"name": log_type,
              "output_options": [{"output": logging_file_path}],
              "severity": severity}
    if severity_level != "None":
        logger["debuglevel"] = int(severity_level)

    if "loggers" not in world.dhcp_cfg:
        world.dhcp_cfg["loggers"] = []

    if merge_by_name:
        found = False
        for cfg_logger in world.dhcp_cfg['loggers']:
            if cfg_logger['name'] == logger['name']:
                merge_containers(cfg_logger, logger, {'output_options': 'output'})
                found = True
        if not found:
            world.dhcp_cfg['loggers'].append(logger)
    else:
        world.dhcp_cfg['loggers'].append(logger)


# Configure a control socket.
def open_control_channel_socket(socket_name=None):
    if socket_name is not None:
        socket_path = world.f_cfg.run_join(socket_name)
    else:
        socket_path = world.f_cfg.run_join('control_socket')
    world.dhcp_cfg["control-socket"] = {"socket-type": "unix", "socket-name": socket_path}


def create_new_class(class_name):
    if "client-classes" not in world.dhcp_cfg:
        world.dhcp_cfg["client-classes"] = []
    world.dhcp_cfg["client-classes"].append({"name": class_name})


def add_test_to_class(class_number, parameter_name, parameter_value):
    if parameter_name == "option-def":
        if "option-def" not in world.dhcp_cfg["client-classes"][class_number - 1]:
            world.dhcp_cfg["client-classes"][class_number - 1]["option-def"] = []
        world.dhcp_cfg["client-classes"][class_number - 1][parameter_name].append(parameter_value)
    elif parameter_name == "option-data":
        if "option-data" not in world.dhcp_cfg["client-classes"][class_number - 1]:
            world.dhcp_cfg["client-classes"][class_number - 1]["option-data"] = []
        world.dhcp_cfg["client-classes"][class_number - 1][parameter_name].append(parameter_value)
    else:
        world.dhcp_cfg["client-classes"][class_number - 1][parameter_name] = _check_value(parameter_value)


def add_option_to_defined_class(class_no, option_name, option_value):
    space = world.cfg["space"]
    option_code = _get_option_code(option_name)

    if "option-data" not in world.dhcp_cfg["client-classes"][class_no - 1]:
        world.dhcp_cfg["client-classes"][class_no - 1]["option-data"] = []
    world.dhcp_cfg["client-classes"][class_no - 1]["option-data"].append({"csv-format": True,
                                                                          "code": int(option_code),
                                                                          "data": option_value,
                                                                          "name": option_name,
                                                                          "space": space})


def config_client_classification(subnet, option_value):
    sub = f'subnet{world.proto[1]}'
    world.dhcp_cfg[sub][int(subnet)]["client-class"] = option_value


def config_require_client_classification(subnet, option_value):
    sub = f'subnet{world.proto[1]}'
    subnet = int(subnet)
    if "require-client-classes" not in world.dhcp_cfg[sub][subnet]:
        world.dhcp_cfg[sub][subnet]["require-client-classes"] = []

    world.dhcp_cfg[sub][subnet]["require-client-classes"].append(option_value)


def set_time(which_time, value, subnet=None):
    assert which_time in world.cfg["server_times"], "Unknown time name: %s" % which_time
    value = int(value)
    if subnet is None:
        world.dhcp_cfg[which_time] = value
    else:
        subnet = int(subnet)
        sub = f'subnet{world.proto[1]}'
        world.dhcp_cfg[sub][subnet][which_time] = value


def add_line_in_global(additional_line):
    world.dhcp_cfg.update(additional_line)


def add_line_to_shared_subnet(subnet_id, additional_line):
    world.dhcp_cfg["shared-networks"][subnet_id].update(additional_line)


def add_line_in_subnet(subnet_id, additional_line):
    sub = f'subnet{world.proto[1]}'
    world.dhcp_cfg[sub][subnet_id].update(additional_line)


def prepare_cfg_subnet(subnet, pool, iface=world.f_cfg.server_iface, **kwargs):
    """Creates or updates an element under "subnet[46]" element in Kea's JSON
    configuration.

    Arguments:
    subnet -- the value for "subnet". If None, then continue with configuring an
        already existing subnet element.
    pool -- the value appended to "pools". If None, then leave "pools" alone.
    iface -- the interface to be configured on the subnet element
        (default: SERVER_IFACE)
    """
    if world.proto == 'v4':
        if subnet == "default":
            subnet = "192.168.0.0/24"
        if pool == "default":
            pool = "192.168.0.1 - 192.168.0.254"
    else:
        if subnet == "default":
            subnet = "2001:db8:1::/64"
        if pool == "default":
            pool = "2001:db8:1::1 - 2001:db8:1::ffff"

    sub = f'subnet{world.proto[1]}'
    if sub not in world.dhcp_cfg.keys() and subnet:
        world.dhcp_cfg[sub] = [{}]
    elif sub in world.dhcp_cfg.keys() and subnet:
        world.dhcp_cfg[sub].append({})

    if subnet:
        world.dhcp_cfg[sub][world.dhcp["subnet_cnt"]] = {"subnet": subnet,
                                                         "pools": [],
                                                         "interface": iface}
    if pool:
        world.dhcp_cfg[sub][world.dhcp["subnet_cnt"]]["pools"].append({"pool": pool})
    add_interface(iface)

    for x, y in kwargs.items():
        if y is not None:
            world.dhcp_cfg[sub][world.dhcp["subnet_cnt"]].update({x.replace("_", "-"): y})


def config_srv_another_subnet(subnet, pool, iface=world.f_cfg.server_iface, **kwargs):
    """Like config_srv_subnet(subnet, pool, iface), but increments the subnet
    counter to guarantee that this subnet will be a new one.

    Arguments:
    subnet -- the value for "subnet". If None, then continue with configuring an
        already existing subnet element.
    pool -- the value appended to "pools". If None, then leave "pools" alone.
    iface -- the interface to be configured on the subnet element
        (default: SERVER_IFACE)
    """
    world.dhcp["subnet_cnt"] += 1
    prepare_cfg_subnet(subnet, pool, iface, **kwargs)


def prepare_cfg_subnet_specific_interface(interface, address, subnet, pool):
    if subnet == "default":
        subnet = "2001:db8:1::/64"
    if pool == "default":
        pool = "2001:db8:1::1 - 2001:db8:1::ffff"

    # This is weird, it's not used in any test looks like we have some errors because it was used
    # TODO write missing tests using specific interface!
    sub = f'subnet{world.proto[1]}'
    if sub not in world.dhcp_cfg.keys():
        world.dhcp_cfg[sub] = [{}]

    if subnet:
        world.dhcp_cfg[sub][world.dhcp["subnet_cnt"]] = {"subnet": subnet,
                                                         "pools": [],
                                                         "interface": interface}
    if pool:
        world.dhcp_cfg[sub][world.dhcp["subnet_cnt"]]["pools"].append({"pool": pool})

    add_interface(interface + "/" + address)


def prepare_cfg_add_custom_option(opt_name, opt_code, opt_type, opt_value, space, **kwargs):
    prepare_cfg_add_option(opt_name, opt_value, space, opt_code, 'user', **kwargs)

    if "option-def" not in world.dhcp_cfg.keys():
        world.dhcp_cfg["option-def"] = []

    world.dhcp_cfg["option-def"].append({"code": int(opt_code), "name": opt_name,
                                         "space": space, "encapsulate": "", "record-types": "",
                                         "array": False, "type": opt_type})


def add_interface(iface, add_to_existing=True):
    """Adds an interface to the "interfaces" list under "interfaces-config" in
    Kea JSON configuration.

    Arguments:
    iface -- the interface to be added to the configuration
    add_to_existing -- if True, then add the interface in all circumstances.
        If False, then add the interface only if there are no other interfaces
        configured
    """
    if "interfaces-config" not in world.dhcp_cfg.keys():
        world.dhcp_cfg["interfaces-config"] = {"interfaces": []}

    if iface is not None and iface not in world.dhcp_cfg["interfaces-config"]["interfaces"]:
        if add_to_existing or len(world.dhcp_cfg["interfaces-config"]["interfaces"]) == 0:
            world.dhcp_cfg["interfaces-config"]["interfaces"].append(iface)


def add_pool_to_subnet(pool, subnet):
    sub = f'subnet{world.proto[1]}'
    world.dhcp_cfg[sub][subnet]["pools"].append({"pool": pool})


def add_prefix_to_subnet(prefix, length, delegated,  subnet):
    sub = f'subnet{world.proto[1]}'
    if "pd-pools" not in world.dhcp_cfg[sub][subnet]:
        world.dhcp_cfg[sub][subnet].update({"pd-pools": []})
    world.dhcp_cfg[sub][subnet]["pd-pools"].append({"delegated-len": int(delegated),
                                                    "prefix": prefix,
                                                    "prefix-len": int(length)})


def set_conf_parameter_global(parameter_name, value):
    world.dhcp_cfg[parameter_name] = value


def set_conf_parameter_subnet(parameter_name, value, subnet_id):
    sub = f'subnet{world.proto[1]}'
    world.dhcp_cfg[sub][subnet_id][parameter_name] = _check_value(value)
    if parameter_name in ["interface-id", "relay"]:
        world.dhcp_cfg[sub][subnet_id].pop("interface", None)


def add_to_shared_subnet(subnet_def, shared_network_id):
    sub = f'subnet{world.proto[1]}'
    if len(world.dhcp_cfg["shared-networks"]) <= shared_network_id:
        world.dhcp_cfg["shared-networks"].append({})
    if sub not in world.dhcp_cfg["shared-networks"][shared_network_id]:
        world.dhcp_cfg["shared-networks"][shared_network_id][sub] = []

    for i in range(len(world.dhcp_cfg[sub])):
        if world.dhcp_cfg[sub][i]["subnet"] == subnet_def:
            world.dhcp_cfg["shared-networks"][shared_network_id][sub].append(world.dhcp_cfg[sub][i])
            del world.dhcp_cfg[sub][i]
            world.dhcp["subnet_cnt"] -= 1
            break  # removing one from the list will cause error at the end of the loop


def set_conf_parameter_shared_subnet(parameter_name, value, network_id):
    # magic for backward compatibility, was easier than editing all tests we already have.
    value = value.strip("\"")
    if len(value) > 0:
        if value[0] == "{":
            value = json.loads(value)
    if parameter_name == "option-data":
        if "option-data" not in world.dhcp_cfg["shared-networks"][network_id]:
            world.dhcp_cfg["shared-networks"][network_id]["option-data"] = []
        world.dhcp_cfg["shared-networks"][network_id][parameter_name].append(value)
    else:
        world.dhcp_cfg["shared-networks"][network_id][parameter_name] = _check_value(value)

    if parameter_name in ["interface-id", "relay"]:
        world.dhcp_cfg["shared-networks"][network_id].pop("interface", None)
        for subnet in world.dhcp_cfg["shared-networks"][network_id][f"subnet{world.proto[1]}"]:
            subnet.pop("interface", None)


def _check_empty_value(val):
    return (False, "") if val == "<empty>" else (True, val)


def prepare_cfg_add_option(option_name, option_value, space,
                           option_code=None, opt_type='default', **kwargs):
    """
    Add option data to global kea configuration
    :param option_name: string option name
    :param option_value: string, option value
    :param space: string, option space
    :param option_code: int, option code
    :param opt_type: string, option type
    """

    # check if we are configuring default option or user option via function "prepare_cfg_add_custom_option"
    if opt_type == 'default':
        option_code = _get_option_code(option_name)

    if world.proto == 'v4':
        csv_format, option_value = _check_empty_value(option_value)
    else:
        csv_format = True

    my_opt = {"code": int(option_code),
              "csv-format": csv_format,
              "data": option_value,
              "name": option_name,
              "space": space}

    for x, y in kwargs.items():
        if y is not None:
            my_opt.update({x.replace("_", "-"): y})

    world.dhcp_cfg["option-data"].append(my_opt)


def prepare_cfg_add_option_subnet(option_name: str, subnet: int, option_value: str, **kwargs):
    """
    Add option data to subnet
    :param option_name: string, option name
    :param subnet: int, index of a subnet that will be updated
    :param option_value: string, option value
    """
    space = world.cfg["space"]
    subnet = int(subnet)
    option_code = _get_option_code(option_name)

    if world.proto == 'v4':
        csv_format, option_value = _check_empty_value(option_value)
    else:
        csv_format = True

    my_opt = {"code": int(option_code),
              "csv-format": csv_format,
              "data": option_value,
              "name": option_name,
              "space": space}

    for x, y in kwargs.items():
        if y is not None:
            my_opt.update({x.replace("_", "-"): y})

    sub = f'subnet{world.proto[1]}'
    if "option-data" not in world.dhcp_cfg[sub][subnet]:
        world.dhcp_cfg[sub][subnet]["option-data"] = []
    world.dhcp_cfg[sub][subnet]["option-data"].append(my_opt)


def prepare_cfg_add_option_pool(option_name: str, option_value: str, subnet: int = 0,
                                pool: int = 0, **kwargs):
    """
    Add option data to a pool
    :param option_name: string, option name
    :param option_value: string, option value
    :param subnet: int, index of subnet in the list of subnets
    :param pool: int, index of pool to be updated on the list of pools
    """
    space = world.cfg["space"]
    subnet = int(subnet)

    option_code = _get_option_code(option_name)

    if world.proto == 'v4':
        csv_format, option_value = _check_empty_value(option_value)
    else:
        csv_format = True

    my_opt = {"code": int(option_code),
              "csv-format": csv_format,
              "data": option_value,
              "name": option_name,
              "space": space}

    for x, y in kwargs.items():
        if y is not None:
            my_opt.update({x.replace("_", "-"): y})

    sub = f'subnet{world.proto[1]}'
    if "option-data" not in world.dhcp_cfg[sub][subnet]["pools"][pool]:
        world.dhcp_cfg[sub][subnet]["pools"][pool]["option-data"] = []
    world.dhcp_cfg[sub][subnet]["pools"][pool]["option-data"].append(my_opt)


def prepare_cfg_add_option_shared_network(option_name: str, option_value: str,
                                          shared_network: int = 0, **kwargs):
    """
    Add option data to shared-network
    :param option_name: string, option name
    :param option_value: string, option value
    :param shared_network: int, index of shared network to be updated in the list of shared networks
    """
    space = world.cfg["space"]
    shared_network = int(shared_network)
    option_code = _get_option_code(option_name)

    assert option_code is not None, "Unsupported option name for other Kea4 options: " + option_name

    my_opt = {"code": int(option_code),
              "csv-format": True,
              "data": option_value,
              "name": option_name,
              "space": space}

    for x, y in kwargs.items():
        if y is not None:
            my_opt.update({x.replace("_", "-"): y})

    if "option-data" not in world.dhcp_cfg["shared-networks"][shared_network]:
        world.dhcp_cfg["shared-networks"][shared_network]["option-data"] = []
    world.dhcp_cfg["shared-networks"][shared_network]["option-data"].append(my_opt)


def host_reservation(reservation_type, reserved_value, unique_host_value_type, unique_host_value, subnet):
    """Configure a subnet-level host reservation.

    Arguments:
    reservation_type -- the type of the reserved resource: "client-classes",
        "hostname", "ip-addresses", "option-data", "prefixes"
    reserved_value -- the value of the reserved resource
    unique_host_value_type -- the type for the reservation's identifier:
        "circuit-id", "client-id", "duid", "flex-id", "hw-address"
    unique_host_value -- the value for the reservation's identifier
    subnet -- the ordinal number of the subnet under which the reservation will
        be made. Careful, this is not the subnet ID. Subnet 0 is the first subnet.
    """
    sub = f'subnet{world.proto[1]}'
    if "reservations" not in world.dhcp_cfg[sub][subnet]:
        world.dhcp_cfg[sub][subnet]["reservations"] = []

    # v6 for ip-address reservation and prefixes using different format and names:
    if world.proto[1] == '6':
        if reservation_type in ["ip-address", "prefix", "prefixes"]:
            # Make sure it ends in "es".
            if reservation_type[-2:] != "es":
                reservation_type += "es"
            # add reservation as list if it's prefix or address
            world.dhcp_cfg[sub][subnet]["reservations"].append({unique_host_value_type: unique_host_value,
                                                                reservation_type: [reserved_value]})
        else:
            world.dhcp_cfg[sub][subnet]["reservations"].append({unique_host_value_type: unique_host_value,
                                                                reservation_type: reserved_value})
    else:
        world.dhcp_cfg[sub][subnet]["reservations"].append({unique_host_value_type: unique_host_value,
                                                            reservation_type: reserved_value})


def host_reservation_extension(reservation_number, subnet, reservation_type, reserved_value):
    sub = f'subnet{world.proto[1]}'
    if world.proto[1] == '6':
        if reservation_type in ["ip-address", "prefix", "prefixes"]:
            # Make sure it ends in "es".
            if reservation_type[-2:] != "es":
                reservation_type += "es"
            if reservation_type not in world.dhcp_cfg[sub][subnet]["reservations"][reservation_number]:
                world.dhcp_cfg[sub][subnet]["reservations"][reservation_number][reservation_type] = []
            world.dhcp_cfg[sub][subnet]["reservations"][reservation_number][reservation_type].append(reserved_value)
        else:
            world.dhcp_cfg[sub][subnet]["reservations"][reservation_number].update({reservation_type: reserved_value})
    else:
        world.dhcp_cfg[sub][subnet]["reservations"][reservation_number].update({reservation_type: reserved_value})


def _config_db_backend():
    if world.f_cfg.db_type == "" or world.f_cfg.db_type == "memfile":
        if "lease-database" not in world.dhcp_cfg:
            world.dhcp_cfg["lease-database"] = {"type": "memfile"}
    else:
        world.dhcp_cfg["lease-database"] = {"type": world.f_cfg.db_type,
                                            "name": world.f_cfg.db_name,
                                            "host": world.f_cfg.db_host,
                                            "user": world.f_cfg.db_user,
                                            "password": world.f_cfg.db_passwd}

    # set reservations
    if world.reservation_backend in ["mysql", "postgresql"]:
        world.dhcp_cfg["hosts-database"] = {"type": world.reservation_backend,
                                            "name": world.f_cfg.db_name,
                                            "host": world.f_cfg.db_host,
                                            "user": world.f_cfg.db_user,
                                            "password": world.f_cfg.db_passwd}


def add_hooks(library_path):
    if "libdhcp_ha" in library_path:
        world.dhcp_cfg["hooks-libraries"].append({"library": library_path,
                                                  "parameters": {
                                                      "high-availability": [{"peers": [],
                                                                             "state-machine": {"states": []}}]}})
    else:
        world.dhcp_cfg["hooks-libraries"].append({"library": library_path})


def delete_hooks(hook_patterns):
    """
    Delete hook whose path matches one of the patterns given as parameters.

    :param hook_patterns: list of patterns used to match library paths
    """
    for hp in hook_patterns:
        for i, hook_library in enumerate(world.dhcp_cfg['hooks-libraries']):
            if re.search(hp, hook_library['library']):
                del world.dhcp_cfg['hooks-libraries'][i]


def add_parameter_to_hook(hook_number_or_name, parameter_name, parameter_value):
    """
    Determine the hook library with number {hook_number_or_name} if it's an int,
    or that contains pattern {hook_number_or_name} if it's a str.
    Add to the hook library's parameters: "{parameter_name}": {parameter_value}

    Other usage is to pass full dictionary as second argument and parameter_value set to None,
    this way passed dictionary will be saved in parameters of particular hook

    :param hook_number_or_name: hook index starting with 1 or pattern contained in the library name
    :param parameter_name: the parameter's JSON key
    :param parameter_value: the parameter's JSON value
    """

    # Get the hook number.
    if isinstance(hook_number_or_name, int):
        hook_no = hook_number_or_name - 1
    if isinstance(hook_number_or_name, str):
        for i, hook_library in enumerate(world.dhcp_cfg['hooks-libraries']):
            if re.search(hook_number_or_name, hook_library['library']):
                hook_no = i

    if "parameters" not in world.dhcp_cfg["hooks-libraries"][hook_no].keys():
        world.dhcp_cfg["hooks-libraries"][hook_no]["parameters"] = {}
    if isinstance(parameter_name, dict) and parameter_value is None:
        world.dhcp_cfg["hooks-libraries"][hook_no]["parameters"] = parameter_name
        return
    elif parameter_value in ["True", "true"]:
        parameter_value = True
    elif parameter_value in ["False", 'false']:
        parameter_value = False
    elif parameter_value.isdigit():
        parameter_value = int(parameter_value)
    world.dhcp_cfg["hooks-libraries"][hook_no]["parameters"][parameter_name] = parameter_value


def delete_parameter_from_hook(hook_number_or_name, parameter_name: str):
    """
    Determine the hook library with number {hook_number_or_name} if it's an int,
    or that contains pattern {hook_number_or_name} if it's a str.
    Remove {parameter_name} from the hook library's parameters.

    :param hook_number_or_name: hook index starting with 1 or pattern contained in the library name
    :param parameter_name: the parameter's JSON key
    """

    # Get the hook number.
    hook_no = None
    if isinstance(hook_number_or_name, int):
        hook_no = hook_number_or_name - 1
    if isinstance(hook_number_or_name, str):
        for i, hook_library in enumerate(world.dhcp_cfg['hooks-libraries']):
            if re.search(hook_number_or_name, hook_library['library']):
                hook_no = i
    if hook_no is None:
        return

    if 'parameters' not in world.dhcp_cfg['hooks-libraries'][hook_no].keys():
        return

    if parameter_name in world.dhcp_cfg["hooks-libraries"][hook_no]["parameters"]:
        del world.dhcp_cfg["hooks-libraries"][hook_no]["parameters"][parameter_name]


def ha_add_parameter_to_hook(parameter_name, parameter_value):
    # First let's find HA hook in the list:
    # btw.. I wonder why "high-availability" is list of dictionaries not dictionary
    # and it's just for current backward compatibility, I will change it when I will get back to HA tests
    for hook in world.dhcp_cfg["hooks-libraries"]:
        if "libdhcp_ha" in hook["library"]:
            if parameter_name == "machine-state":
                hook["parameters"]["high-availability"][0]["state-machine"]["states"].append(parameter_value)
            elif parameter_name == "peers":
                if isinstance(parameter_value, str):
                    parameter_value.strip("'")
                    parameter_value = json.loads(parameter_value)
                hook["parameters"]["high-availability"][0]["peers"].append(parameter_value)
            elif parameter_name == "lib":
                pass
            else:
                if parameter_value.isdigit():
                    parameter_value = int(parameter_value)
                else:
                    parameter_value = parameter_value.strip("\"")
                hook["parameters"]["high-availability"][0][parameter_name] = parameter_value


def update_ha_hook_parameter(param):
    assert isinstance(param, dict), "pass just dict as parameter"
    for hook in world.dhcp_cfg["hooks-libraries"]:
        if "libdhcp_ha" in hook["library"]:
            hook["parameters"]["high-availability"][0].update(param)


def disable_lease_affinity():
    world.dhcp_cfg.update({"expired-leases-processing": {"hold-reclaimed-time": 0,
                                                         "flush-reclaimed-timer-wait-time": 0}})


def update_expired_leases_processing(param):
    if isinstance(param, str):
        if param == 'default':
            if "expired-leases-processing" in world.dhcp_cfg:
                del world.dhcp_cfg["expired-leases-processing"]
    elif isinstance(param, dict):
        if "expired-leases-processing" not in world.dhcp_cfg:
            world.dhcp_cfg.update({"expired-leases-processing": {}})
        world.dhcp_cfg["expired-leases-processing"].update(param)
    else:
        assert False, "Please use 'default' to remove expired leases configuration or use dict to pass params " \
                      "and values inside 'expired-leases-processing'"


# Start kea-ctrl-agent.
def agent_control_channel(host_address, host_port, socket_name='control_socket'):
    if world.f_cfg.install_method == 'make' or world.server_system == 'alpine':
        logging_file = 'kea-ctrl-agent.log'
        logging_file_path = world.f_cfg.log_join(logging_file)
    else:
        logging_file_path = 'stdout'

    world.ctrl_enable = True
    server_socket_type = f'dhcp{world.proto[1]}'
    world.ca_cfg["Control-agent"] = {'http-host': host_address,
                                     'http-port':  int(host_port),
                                     'control-sockets': {server_socket_type: {"socket-type": "unix",
                                                                              "socket-name": world.f_cfg.run_join(socket_name)}},
                                     "loggers": [
                                         {"debuglevel": 99, "name": "kea-ctrl-agent",
                                          "output_options": [{"output": logging_file_path}],
                                          "severity": "DEBUG"}]}


def config_srv_id(id_type, id_value):
    if world.proto == 'v4':
        assert False, "Not yet available for Kea4"

    id_value = id_value.replace(":", "")
    if id_type == "EN":
        world.dhcp_cfg["server-id"] = {"type": "EN",
                                       "enterprise-id": int(id_value[4:12], 16),
                                       "identifier": id_value[12:]}
    elif id_type == "LLT":
        world.dhcp_cfg["server-id"] = {"type": "LLT",
                                       "htype": int(id_value[4:8], 16),
                                       "identifier": id_value[16:],
                                       "time": int(id_value[8:16], 16)}
    elif id_type == "LL":
        world.dhcp_cfg["server-id"] = {"type": "LL",
                                       "htype": int(id_value[4:8], 16),
                                       "identifier": id_value[8:]}


def prepare_cfg_prefix(prefix, length, delegated_length, subnet, **kwargs):
    """
    Adds a new prefix delegation pool to the given subnet configuration.
    :param prefix: the IPv6 prefix to delegate prefixes from
    :param length: the length of the IPv6 prefix to delegate prefixes from
    :param delegated_length: the IPv6 prefix to delegate prefixes from
    :param subnet: the ordinal number of the subnet under which the reservation will be made.
                   Careful, this is not the subnet ID. Subnet 0 is the first subnet.
    :param kwargs: additional entries in the pool
    """
    if world.proto == 'v4':
        assert False, "Not available for DHCPv4"

    sub = f'subnet{world.proto[1]}'

    if 'pd-pools' not in world.dhcp_cfg[sub][int(subnet)]:
        world.dhcp_cfg[sub][int(subnet)]['pd-pools'] = []

    pd = {
        "delegated-len": int(delegated_length),
        "prefix": prefix,
        "prefix-len": int(length)
    }

    for x, y in kwargs.items():
        if y is not None:
            pd.update({x.replace("_", "-"): y})

    world.dhcp_cfg[sub][int(subnet)]['pd-pools'].append(pd)


def add_siaddr(addr, subnet_number):
    if world.proto == 'v6':
        assert False, "Not available for DHCPv6"

    if subnet_number is None:
        world.dhcp_cfg["next-server"] = addr
    else:
        world.dhcp_cfg["subnet4"][int(subnet_number)]["next-server"] = addr


def disable_client_echo():
    if world.proto == 'v6':
        assert False, "Not available for DHCPv6"
    world.dhcp_cfg["echo-client-id"] = False


def _set_kea_ctrl_config():
    if world.f_cfg.software_install_path.endswith('/'):
        path = world.f_cfg.software_install_path[:-1]
    else:
        path = world.f_cfg.software_install_path

    kea6 = 'no'
    kea4 = 'no'
    ddns = 'no'
    ctrl_agent = 'no'
    if "kea6" in world.cfg["dhcp_under_test"]:
        kea6 = 'yes'
    elif "kea4" in world.cfg["dhcp_under_test"]:
        kea4 = 'yes'
    if world.ddns_enable:
        ddns = 'yes'
    if world.ctrl_enable:
        ctrl_agent = 'yes'
    world.cfg["keactrl"] = '''kea_config_file={path}/etc/kea/kea.conf
    dhcp4_srv={path}/sbin/kea-dhcp4
    dhcp6_srv={path}/sbin/kea-dhcp6
    dhcp_ddns_srv={path}/sbin/kea-dhcp-ddns
    ctrl_agent_srv={path}/sbin/kea-ctrl-agent
    netconf_srv={path}/sbin/kea-netconf
    kea_dhcp4_config_file={path}/etc/kea/kea-dhcp4.conf
    kea_dhcp6_config_file={path}/etc/kea/kea-dhcp6.conf
    kea_dhcp_ddns_config_file={path}/etc/kea/kea-dhcp-ddns.conf
    kea_ctrl_agent_config_file={path}/etc/kea/kea-ctrl-agent.conf
    kea_netconf_config_file={path}/etc/kea/kea-netconf.conf
    dhcp4={kea4}
    dhcp6={kea6}
    dhcp_ddns={ddns}
    kea_verbose=no
    netconf=no
    ctrl_agent={ctrl_agent}
    '''.format(**locals())


def configure_multi_threading(enable_mt, pool=0, queue=0):
    world.dhcp_cfg.update({"multi-threading": {"enable-multi-threading": enable_mt,
                                               "thread-pool-size": pool,
                                               "packet-queue-size": queue}})
    world.f_cfg.auto_multi_threading_configuration = False  # MT configured, automated process is not needed


def disable_mt_if_required(cfg):
    # core MT is enabled by default, HA MT as well. So we need to cover couple cases:
    # * if auto_multi_threading_configuration is false than do nothing
    # * if we detect hooks that are not MT compatible we have to disable MT in core, and in HA
    # * radius + HA tests are weird, first server is configured with radius and than reconfigured with HA

    if world.f_cfg.auto_multi_threading_configuration is False:
        return cfg

    list_of_non_mt_hooks = ["libdhcp_host_cache.so", "libdhcp_radius.so", "libdhcp_user_chk.so"]

    # all configured hooks
    list_of_used_hooks = []
    for hooks in cfg[f'Dhcp{world.proto[1]}']["hooks-libraries"]:
        list_of_used_hooks.append(hooks["library"].split("/")[-1])

    # if any of configured hooks is not working with multi-threading then disable multi-threading in kea config
    if len(set(list_of_used_hooks).intersection(list_of_non_mt_hooks)) != 0:
        if 'multi-threading' not in cfg[f'Dhcp{world.proto[1]}']:
            log.debug("Disable MT")
            cfg[f"Dhcp{world.proto[1]}"].update({"multi-threading": {"enable-multi-threading": False}})
            # ha will be enabled by default, so let's turn that off
            if "libdhcp_ha.so" in list_of_used_hooks:
                ha_mt = {"multi-threading": {"enable-multi-threading": False}}
                for hook in cfg[f"Dhcp{world.proto[1]}"]["hooks-libraries"]:
                    if "libdhcp_ha.so" in hook["library"]:
                        hook["parameters"]["high-availability"][0].update(ha_mt)
                        # let's make sure that HA has correct port number
                        for peer in hook["parameters"]["high-availability"][0]["peers"]:
                            peer["url"] = ":".join(peer["url"].split(":")[:2]) + ":8000/"

    # if non of forbidden hooks were found and ha is detected, enable MT mode in HA and change
    elif "libdhcp_ha.so" in list_of_used_hooks:
        ha_mt = {"multi-threading": {"enable-multi-threading": True,
                                     "http-dedicated-listener": True,
                                     "http-listener-threads": 0,
                                     "http-client-threads": 0}}

        # HA needs to enable it's own MT connectivity
        for hook in cfg[f"Dhcp{world.proto[1]}"]["hooks-libraries"]:
            if "libdhcp_ha.so" in hook["library"]:
                # change port number to not go through CA, CA will be run in the test for all other commands
                for peer in hook["parameters"]["high-availability"][0]["peers"]:
                    # let's replace any port number with new
                    peer["url"] = ":".join(peer["url"].split(":")[:2])+":8003/"
                # and add mt settings
                hook["parameters"]["high-availability"][0].update(ha_mt)
    return cfg


def _cfg_write():
    # For now let's keep to old system of sending config file
    with open(world.cfg["cfg_file_2"], 'w') as cfg_file:
        cfg_file.write(world.cfg["keactrl"])

    if world.f_cfg.install_method == 'make':
        logging_file = world.f_cfg.log_join('kea.log')
    else:
        logging_file = 'stdout'

    add_logger(f'kea-dhcp{world.proto[1]}', "DEBUG", 99, logging_file)

    _config_db_backend()

    dhcp = f'Dhcp{world.proto[1]}'

    world.dhcp_cfg = {dhcp: world.dhcp_cfg}

    world.dhcp_cfg = disable_mt_if_required(world.dhcp_cfg)

    if world.ddns_enable:
        world.ddns_cfg = {"DhcpDdns": world.ddns_cfg}
        add_variable("DDNS_CONFIG", json.dumps(world.ddns_cfg), False)
        with open("kea-dhcp-ddns.conf", 'w') as conf_file:
            conf_file.write(json.dumps(world.ddns_cfg, indent=4, sort_keys=False))

    if world.ctrl_enable:
        add_variable("AGENT_CONFIG", json.dumps(world.ca_cfg), False)
        with open("kea-ctrl-agent.conf", 'w') as conf_file:
            conf_file.write(json.dumps(world.ca_cfg, indent=4, sort_keys=False))

    add_variable("DHCP_CONFIG", json.dumps(world.dhcp_cfg), False)
    with open(f'kea-dhcp{world.proto[1]}.conf', 'w') as conf_file:
        conf_file.write(json.dumps(world.dhcp_cfg, indent=4, sort_keys=False))


def _write_cfg2(cfg):
    if "Control-agent" in cfg:
        with open("kea-ctrl-agent.conf", 'w') as cfg_file:
            json.dump({"Control-agent": cfg["Control-agent"]}, cfg_file, sort_keys=False,
                      indent=4, separators=(',', ': '))

    if f'Dhcp{world.proto[1]}' in cfg:
        cfg = disable_mt_if_required(cfg)
        with open(f'kea-dhcp{world.proto[1]}.conf', 'w') as cfg_file:
            json.dump({f'Dhcp{world.proto[1]}': cfg[f'Dhcp{world.proto[1]}']},
                      cfg_file, sort_keys=False, indent=4, separators=(',', ': '))

    if "DhcpDdns" in cfg:
        with open("kea-dhcp-ddns.conf", 'w') as cfg_file:
            json.dump({"DhcpDdns": cfg["DhcpDdns"]}, cfg_file, sort_keys=False, indent=4, separators=(',', ': '))

    with open(world.cfg["cfg_file_2"], 'w') as cfg_file:
        cfg_file.write(world.cfg["keactrl"])


def build_config_files(cfg=None):
    substitute_vars(world.dhcp_cfg)
    if world.proto == 'v4':
        add_defaults4()
    else:
        add_defaults6()

    _set_kea_ctrl_config()

    if cfg is None:
        _cfg_write()
    else:
        _write_cfg2(cfg)


def build_and_send_config_files(destination_address=world.f_cfg.mgmt_address, cfg=None):
    """
    Generate final config file, save it to test result directory
    and send it to remote system unless testing step will define differently.
    :param destination_address: address of remote system to which conf file will be send,
    default it's world.f_cfg.mgmt_address
    """

    # generate config files content
    build_config_files(cfg)

    if destination_address not in world.f_cfg.multiple_tested_servers:
        world.multiple_tested_servers.append(destination_address)

    # use mode="0o666" to make config writable to enable config-write tests

    # send to server
    if world.f_cfg.install_method == 'make':
        fabric_send_file(world.cfg["cfg_file_2"],
                         world.f_cfg.etc_join("keactrl.conf"),
                         destination_host=destination_address)

    fabric_send_file(f'kea-dhcp{world.proto[1]}.conf',
                     world.f_cfg.etc_join(f'kea-dhcp{world.proto[1]}.conf'),
                     destination_host=destination_address,
                     mode="0o666")

    if world.ctrl_enable:
        fabric_send_file("kea-ctrl-agent.conf",
                         world.f_cfg.etc_join("kea-ctrl-agent.conf"),
                         destination_host=destination_address,
                         mode="0o666")

    if world.ddns_enable:
        fabric_send_file("kea-dhcp-ddns.conf",
                         world.f_cfg.etc_join("kea-dhcp-ddns.conf"),
                         destination_host=destination_address,
                         mode="0o666")

    # store files back to local for debug purposes
    if world.f_cfg.install_method == 'make':
        copy_configuration_file(world.cfg["cfg_file_2"], "kea_ctrl_config", destination_host=destination_address)
        remove_local_file(world.cfg["cfg_file_2"])

    copy_configuration_file(f'kea-dhcp{world.proto[1]}.conf',
                            f'kea-dhcp{world.proto[1]}.conf', destination_host=destination_address)
    remove_local_file(f'kea-dhcp{world.proto[1]}.conf')

    if world.ctrl_enable:
        copy_configuration_file("kea-ctrl-agent.conf", "kea-ctrl-agent.conf", destination_host=destination_address)
        remove_local_file("kea-ctrl-agent.conf")

    if world.ddns_enable:
        copy_configuration_file("kea-dhcp-ddns.conf", "kea-dhcp-ddns.conf", destination_host=destination_address)
        remove_local_file("kea-dhcp-ddns.conf")


def clear_logs(destination_address=world.f_cfg.mgmt_address):
    fabric_remove_file_command(world.f_cfg.log_join('kea*'),
                               destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)


def clear_leases(db_name=world.f_cfg.db_name, db_user=world.f_cfg.db_user, db_passwd=world.f_cfg.db_passwd,
                 destination_address=world.f_cfg.mgmt_address):

    if world.f_cfg.db_type == "mysql":
        # that is tmp solution - just clearing not saving.
        command = 'for table_name in dhcp4_options dhcp6_options ipv6_reservations hosts lease4 lease6 logs; ' \
                  'do mysql -u {db_user} -p{db_passwd} -e' \
                  ' "SET foreign_key_checks = 0; delete from $table_name" {db_name}; done'.format(**locals())
        fabric_run_command(command, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)
    elif world.f_cfg.db_type == "postgresql":
        command = 'for table_name in dhcp4_options dhcp6_options ipv6_reservations hosts lease4 lease6 logs;' \
                  ' do psql -U {db_user} -d {db_name} -c "delete from $table_name" ; done'.format(**locals())
        fabric_run_command(command, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)
    elif world.f_cfg.db_type in ["memfile", ""]:
        fabric_remove_file_command(world.f_cfg.get_leases_path(), destination_host=destination_address,
                                   hide_all=not world.f_cfg.forge_verbose)
    else:
        raise Exception('Unsupported db type %s' % world.f_cfg.db_type)


def clear_pid_leftovers(destination_address):
    # we are using rm -f for files so command always succeed, so let's download it first than remove and rise error
    result = fabric_download_file(world.f_cfg.run_join('kea.kea-dhcp*.pid'),
                                  check_local_path_for_downloaded_files(world.cfg["test_result_dir"],
                                                                        'PID_FILE',
                                                                        destination_address),
                                  destination_host=destination_address, ignore_errors=True)
    if result.succeeded:
        fabric_remove_file_command(world.f_cfg.run_join('kea.kea-dhcp*.pid'),
                                   destination_host=destination_address)

        assert False, "KEA PID FILE FOUND! POSSIBLE KEA CRASH"


def clear_all(destination_address=world.f_cfg.mgmt_address,
              software_install_path=world.f_cfg.software_install_path, db_user=world.f_cfg.db_user,
              db_passwd=world.f_cfg.db_passwd, db_name=world.f_cfg.db_name):
    clear_logs(destination_address)

    # remove pid files
    clear_pid_leftovers(destination_address=destination_address)

    # remove other kea runtime data
    fabric_remove_file_command(world.f_cfg.data_join('*'), destination_host=destination_address,
                               hide_all=not world.f_cfg.forge_verbose)
    fabric_remove_file_command(world.f_cfg.run_join('*'), destination_host=destination_address,
                               hide_all=not world.f_cfg.forge_verbose)

    # use kea script for cleaning mysql
    cmd = 'bash {software_install_path}/share/kea/scripts/mysql/wipe_data.sh '
    cmd += ' `mysql -u{db_user} -p{db_passwd} {db_name} -N -B'
    cmd += '   -e "SELECT CONCAT_WS(\'.\', version, minor) FROM schema_version;" 2>/dev/null` -N -B'
    cmd += ' -u{db_user} -p{db_passwd} {db_name}'
    cmd = cmd.format(software_install_path=software_install_path,
                     db_user=db_user,
                     db_passwd=db_passwd,
                     db_name=db_name)
    fabric_run_command(cmd, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)

    # use kea script for cleaning pgsql
    cmd = 'PGPASSWORD={db_passwd} bash {software_install_path}/share/kea/scripts/pgsql/wipe_data.sh '
    cmd += ' `PGPASSWORD={db_passwd} psql --set ON_ERROR_STOP=1 -A -t -h "localhost" '
    cmd += '   -q -U {db_user} -d {db_name} -c "SELECT version || \'.\' || minor FROM schema_version;" 2>/dev/null`'
    cmd += ' --set ON_ERROR_STOP=1 -A -t -h "localhost" -q -U {db_user} -d {db_name}'
    cmd = cmd.format(software_install_path=software_install_path,
                     db_user=db_user,
                     db_passwd=db_passwd,
                     db_name=db_name)
    fabric_run_command(cmd, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)

    # clear kea logs in journald (actually all logs)
    if world.f_cfg.install_method != 'make':
        if world.server_system == 'alpine':
            cmd = 'truncate /var/log/messages -s0'
            fabric_sudo_command(cmd, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)
        else:
            cmd = 'journalctl --rotate'
            fabric_sudo_command(cmd, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)
            cmd = 'journalctl --vacuum-time=1s'
            fabric_sudo_command(cmd, destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)


def _check_kea_status(destination_address=world.f_cfg.mgmt_address):
    v4 = False
    v6 = False
    result = fabric_sudo_command(os.path.join(world.f_cfg.software_install_path, "sbin/keactrl") + " status",
                                 destination_host=destination_address, hide_all=not world.f_cfg.forge_verbose)
    # not very sophisticated but easiest fastest way ;)
    if "DHCPv4 server: inactive" in result:
        v4 = False
    elif "DHCPv4 server: active" in result:
        v4 = True
    if "DHCPv6 server: inactive" in result:
        v6 = False
    elif "DHCPv6 server: active" in result:
        v6 = True
    return v4, v6


def _restart_kea_with_systemctl(destination_address):
    cmd_tpl = 'systemctl reset-failed {service} ;'  # prevent failing due to too many restarts
    cmd_tpl += ' systemctl restart {service} &&'  # restart service
    cmd_tpl += ' ts=`systemctl show -p ActiveEnterTimestamp {service}.service | awk \'{{print $2 $3}}\'`;'  # get time of log beginning
    cmd_tpl += ' ts=${{ts:-$(date +"%Y-%m-%d%H:%M:%S")}};'  # if started for the first time then ts is empty so set to current date
    cmd_tpl += ' SECONDS=0; while (( SECONDS < 4 )); do'  # watch logs for max 4 seconds
    cmd_tpl += ' journalctl -u {service}.service --since $ts |'  # get logs since last start of kea service
    cmd_tpl += ' grep "server version .* started" 2>/dev/null;'  # if in the logs there is given sequence then ok
    cmd_tpl += ' if [ $? -eq 0 ]; then break; fi done'

    if world.server_system == 'redhat':
        service_name = f'kea-dhcp{world.proto[1]}'
    else:
        service_name = f'isc-kea-dhcp{world.proto[1]}-server'

    cmd = cmd_tpl.format(service=service_name)
    fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ctrl_enable:
        if world.server_system == 'redhat':
            service_name = 'kea-ctrl-agent'
        else:
            service_name = 'isc-kea-ctrl-agent'
        cmd = cmd_tpl.format(service=service_name)
        fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ddns_enable:
        if world.server_system == 'redhat':
            service_name = 'kea-dhcp-ddns'
        else:
            service_name = 'isc-kea-dhcp-ddns-server'
        cmd = cmd_tpl.format(service=service_name)
        fabric_sudo_command(cmd, destination_host=destination_address)


def _restart_kea_with_openrc(destination_address):
    cmd_tpl = 'rc-service {service} restart &&'  # reload service
    cmd_tpl += ' SECONDS=0; while (( SECONDS < 4 )); do'  # watch logs for max 4 seconds
    cmd_tpl += ' rc-status -f ini | grep "{service} =  started" 2>/dev/null;'
    cmd_tpl += ' if [ $? -eq 0 ]; then break; fi done'

    service_name = f'kea-dhcp{world.proto[1]}'
    cmd = cmd_tpl.format(service=service_name)
    fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ctrl_enable:
        service_name = 'kea-ctrl-agent'
        cmd = cmd_tpl.format(service=service_name)
        fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ddns_enable:
        service_name = 'kea-dhcp-ddns'
        cmd = cmd_tpl.format(service=service_name)
        fabric_sudo_command(cmd, destination_host=destination_address)


def _reload_kea_with_systemctl(destination_address):
    cmd_tpl = 'systemctl reload {service} &&'  # reload service
    cmd_tpl += ' ts=`systemctl show -p ExecReload {service}.service | sed -E -n \'s/.*stop_time=\\[(.*)\\].*/\\1/p\'`;'  # get time of log beginning
    cmd_tpl += ' ts=${{ts:-$(date +"%Y-%m-%d%H:%M:%S")}};'  # if started for the first time then ts is empty so set to current date
    cmd_tpl += ' SECONDS=0; while (( SECONDS < 4 )); do'  # watch logs for max 4 seconds
    cmd_tpl += ' journalctl -u {service}.service --since "$ts" |'  # get logs since last start of kea service
    cmd_tpl += ' grep "{sentence}" 2>/dev/null;'  # if in the logs there is given sequence then ok
    cmd_tpl += ' if [ $? -eq 0 ]; then break; fi done'

    if world.server_system == 'redhat':
        service_name = f'kea-dhcp{world.proto[1]}'
    else:
        service_name = f'isc-kea-dhcp{world.proto[1]}-server'

    cmd = cmd_tpl.format(service=service_name, sentence='initiate server reconfiguration')
    fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ctrl_enable:
        if world.server_system == 'redhat':
            service_name = 'kea-ctrl-agent'
        else:
            service_name = 'isc-kea-ctrl-agent'
        cmd = cmd_tpl.format(service=service_name, sentence='reloading configuration')
        fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ddns_enable:
        if world.server_system == 'redhat':
            service_name = 'kea-dhcp-ddns'
        else:
            service_name = 'isc-kea-dhcp-ddns-server'
        cmd = cmd_tpl.format(service=service_name, sentence='reloading configuration')
        fabric_sudo_command(cmd, destination_host=destination_address)


def _reload_kea_with_openrc(destination_address):
    # SIGHUP to reload
    cmd_tpl = ' kill -s HUP {pid} &&'
    cmd_tpl += ' SECONDS=0; while (( SECONDS < 4 )); do'  # watch logs for max 4 seconds
    cmd_tpl += ' rc-status -f ini | grep "{service} =  started" 2>/dev/null;'
    cmd_tpl += ' if [ $? -eq 0 ]; then break; fi done'

    service_name = f'kea-dhcp{world.proto[1]}'
    pid = fabric_sudo_command(f'pidof {service_name}', destination_host=destination_address)
    cmd = cmd_tpl.format(service=service_name, pid=pid)
    fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ctrl_enable:
        pid = fabric_sudo_command(f'pidof {service_name}', destination_host=destination_address)
        cmd = cmd_tpl.format(service=service_name, pid=pid)
        fabric_sudo_command(cmd, destination_host=destination_address)

    if world.ddns_enable:
        pid = fabric_sudo_command(f'pidof {service_name}', destination_host=destination_address)
        cmd = cmd_tpl.format(service=service_name, pid=pid)
        fabric_sudo_command(cmd, destination_host=destination_address)


def start_srv(should_succeed: bool, destination_address: str = world.f_cfg.mgmt_address, process=""):
    """
    Start kea with generated config
    :param should_succeed: whether the action is supposed to succeed or fail
    :param destination_address: management address of server
    :param process: name of the single process we want to start (using -s option of keactrl)
    """
    if destination_address not in world.f_cfg.multiple_tested_servers:
        world.multiple_tested_servers.append(destination_address)

    if world.f_cfg.install_method == 'make':
        v4_running, v6_running = _check_kea_status(destination_address)

        if v4_running and world.proto == 'v4' or v6_running and world.proto == 'v6':
            _stop_kea_with_keactrl(destination_address)

        result = _start_kea_with_keactrl(destination_address, specific_process=process)
        _check_kea_process_result(should_succeed, result, 'start')
    else:
        if world.server_system == 'alpine':
            _restart_kea_with_openrc(destination_address)
        else:
            _restart_kea_with_systemctl(destination_address)


def stop_srv(value=False, destination_address=world.f_cfg.mgmt_address):
    if world.f_cfg.install_method == 'make':
        # for now just killall kea processes and ignore errors
        fabric_sudo_command("killall -q kea-ctrl-agent  kea-dhcp-ddns  kea-dhcp4  kea-dhcp6",
                            ignore_errors=True, destination_host=destination_address, hide_all=value)

    else:
        if world.server_system in ['redhat', 'alpine']:
            service_names = 'kea-dhcp4 kea-dhcp6 kea-ctrl-agent kea-dhcp-ddns'
        else:
            service_names = 'isc-kea-dhcp4-server isc-kea-dhcp6-server isc-kea-ctrl-agent isc-kea-dhcp-ddns-server'

        if world.server_system == 'alpine':
            service_names = service_names.split()
            for name in service_names:
                cmd = 'rc-service %s stop' % name
                fabric_sudo_command(cmd, destination_host=destination_address)
        else:
            cmd = 'systemctl stop %s' % service_names
            fabric_sudo_command(cmd, destination_host=destination_address)


def _check_kea_process_result(succeed: bool, result: str, action: str):
    """
    Check if a server's logs or a server's output contains failure messages.
    :param succeed: whether the result is supposed to be success or failure
    :param result: the logs or output resulted from an action on the server
    :param action: one-word description of the action done on the server
    """
    errors = ["Failed to apply configuration", "Failed to initialize server",
              "Service failed", "failed to initialize Kea"]

    if succeed:
        if any(error_message in result for error_message in errors):
            assert False, 'Server operation: ' + action + ' failed! '
    if not succeed:
        if not any(error_message in result for error_message in errors):
            assert False, 'Server operation: ' + action + ' NOT failed!'


def _start_kea_with_keactrl(destination_host, specific_process=""):
    # Start kea services and check if they started ok.
    # - nohup to shield kea services from getting SIGHUP from SSH
    # - in a loop check if there is 'server version .* started' expression in the logs;
    #   repeat the loop only for 4 seconds
    # - sync to disk any logs traced by keactrl or kea services
    # - display these logs to screen using cat so forge can catch errors in the logs
    if specific_process != "":
        specific_process = f" -s {specific_process} "
    start_cmd = 'nohup ' + os.path.join(world.f_cfg.software_install_path, 'sbin/keactrl')
    start_cmd += f" start {specific_process}< /dev/null > /tmp/keactrl.log 2>&1; SECONDS=0; while (( SECONDS < 4 ));"
    start_cmd += " do tail %s/var/kea/kea.log 2>/dev/null | grep 'server version .* started' 2>/dev/null;" % world.f_cfg.software_install_path
    start_cmd += " if [ $? -eq 0 ]; then break; fi done;"
    start_cmd += " sync; cat /tmp/keactrl.log"
    return fabric_sudo_command(start_cmd, destination_host=destination_host)


def _stop_kea_with_keactrl(destination_host):
    stop_cmd = os.path.join(world.f_cfg.software_install_path, 'sbin/keactrl') + ' stop'
    started_at = datetime.datetime.now()
    should_finish_by = started_at + datetime.timedelta(seconds=8)
    fabric_sudo_command(stop_cmd, destination_host=destination_host)

    while True:
        kea_dhcp4, kea_dhcp6 = _check_kea_status()
        if not kea_dhcp4 and not kea_dhcp6:
            break

        # Assert that the timeout hasn't passed yet.
        assert datetime.datetime.now() < should_finish_by, \
            'Timeout 8s exceeded while waiting for Kea to stop after "keactrl stop".\n' \
            'kea-dhcp4: ' + ('active' if kea_dhcp4 else 'inactive') + '\n' \
            'kea-dhcp6: ' + ('active' if kea_dhcp6 else 'inactive')

        # Sleep a bit to avoid busy waiting.
        srv_msg.forge_sleep(100, 'milliseconds')


def _reload_kea_with_keactrl(destination_host):
    stop_cmd = os.path.join(world.f_cfg.software_install_path, 'sbin/keactrl') + ' reload'
    return fabric_sudo_command(stop_cmd, destination_host=destination_host)


def reconfigure_srv(should_succeed: bool = True,
                    destination_address: str = world.f_cfg.mgmt_address):
    """
    Send signal to Kea server to reconfigure itself.
    :param should_succeed: whether the reconfiguration is supposed to succeed or fail
    :param destination_address: management address of server
    """
    if world.f_cfg.install_method == 'make':
        result = _reload_kea_with_keactrl(destination_address)
        _check_kea_process_result(should_succeed, result, 'reconfigure')
    else:
        if world.server_system == 'alpine':
            _reload_kea_with_openrc(destination_address)
        else:
            _reload_kea_with_systemctl(destination_address)
    wait_for_message_in_log('dynamic server reconfiguration succeeded with file')


def restart_srv(destination_address=world.f_cfg.mgmt_address):
    if world.f_cfg.install_method == 'make':
        _stop_kea_with_keactrl(destination_address)

        # save log (if required) and then remove it so start can work correctly
        # (start checks in the log if there is expected pattern)
        if world.f_cfg.save_logs:
            save_logs(destination_address=destination_address)
        fabric_sudo_command('rm -f %s' % world.f_cfg.log_join('kea.log'),
                            destination_host=destination_address)

        result = _start_kea_with_keactrl(destination_address)
    else:
        if world.server_system == 'alpine':
            _restart_kea_with_openrc(destination_address)
        else:
            _restart_kea_with_systemctl(destination_address)


def save_leases(tmp_db_type=None, destination_address=world.f_cfg.mgmt_address):
    if world.f_cfg.db_type in ["mysql", "postgresql"]:
        # TODO
        pass
    else:
        if world.server_system == 'alpine':
            lease_file = '/tmp/leases.csv'
            cmd = f'cat {world.f_cfg.get_leases_path()} > {lease_file}'
            fabric_sudo_command(cmd, destination_host=destination_address,
                                ignore_errors=True)
        else:
            lease_file = world.f_cfg.get_leases_path()

        fabric_download_file(lease_file,
                             check_local_path_for_downloaded_files(world.cfg["test_result_dir"],
                                                                   'leases.csv',
                                                                   destination_address),
                             destination_host=destination_address, ignore_errors=True,
                             hide_all=not world.f_cfg.forge_verbose)


def save_logs(destination_address=world.f_cfg.mgmt_address):
    if world.f_cfg.install_method == 'make':
        # download all logs, ie. kea.log, kea.log1, etc.
        log_path = world.f_cfg.log_join('kea.log*')
    else:
        if world.server_system in ['redhat', 'alpine']:
            service_name = f'kea-dhcp{world.proto[1]}'
        else:
            service_name = f'isc-kea-dhcp{world.proto[1]}-server'
        if world.server_system == 'alpine':
            logging_file_path = world.f_cfg.log_join(f'{service_name}.log')
            cmd = f'cat {logging_file_path} > '  # get logs of kea service
            cmd += ' /tmp/kea.log'
        else:
            cmd = 'journalctl -u %s > ' % service_name  # get logs of kea service
            cmd += ' /tmp/kea.log'
        result = fabric_sudo_command(cmd,
                                     destination_host=destination_address,
                                     ignore_errors=True)
        log_path = '/tmp/kea.log'

    local_dest_dir = check_local_path_for_downloaded_files(world.cfg["test_result_dir"],
                                                           '.',
                                                           destination_address)

    # If there are already saved logs then the next ones save in separate folder.
    # For subsequent logs create folder kea-logs-1. If it exists then kea-logs-2,
    # and so on.
    if glob.glob(os.path.join(local_dest_dir, 'kea.log*')):
        # Look for free subdir for logs, try at least 100 times and then give up.
        # There should not be so many stored logs.
        for i in range(1, 100):
            dir2 = os.path.join(local_dest_dir, 'kea-logs-%d' % i)
            if not os.path.exists(dir2):
                found = True
                local_dest_dir = dir2
                os.makedirs(local_dest_dir)
                break
        if not found:
            raise Exception('cannot store log, there is already 100 files stored')

    fabric_download_file(log_path,
                         local_dest_dir,
                         destination_host=destination_address, ignore_errors=True,
                         hide_all=not world.f_cfg.forge_verbose)

    if world.ctrl_enable:
        if world.server_system in ['redhat', 'alpine']:
            service_name = 'kea-ctrl-agent'
        else:
            service_name = 'isc-kea-ctrl-agent'
        if world.server_system == 'alpine':
            logging_file_path = world.f_cfg.log_join('kea-ctrl-agent.log')
            cmd = f'cat {logging_file_path} > '   # get logs of kea service
            cmd += ' /tmp/kea-ctrl-agent.log'
        else:
            cmd = 'journalctl -u %s > ' % service_name  # get logs of kea service
            cmd += ' /tmp/kea-ctrl-agent.log'
        result = fabric_sudo_command(cmd,
                                     destination_host=destination_address,
                                     ignore_errors=True)
        log_path = '/tmp/kea-ctrl-agent.log'
        fabric_download_file(log_path,
                             local_dest_dir,
                             destination_host=destination_address, ignore_errors=True,
                             hide_all=not world.f_cfg.forge_verbose)

    if world.ddns_enable:
        if world.server_system in ['redhat', 'alpine']:
            service_name = 'kea-dhcp-ddns'
        else:
            service_name = 'isc-kea-dhcp-ddns'
        if world.server_system == 'alpine':
            logging_file_path = world.f_cfg.log_join('kea-dhcp-ddns.log')
            cmd = f'cat {logging_file_path} > '   # get logs of kea service
            cmd += ' /tmp/kea.log-ddns'
        else:
            cmd = 'journalctl -u %s > ' % service_name  # get logs of kea service
            cmd += ' /tmp/kea.log-ddns'
        result = fabric_sudo_command(cmd,
                                     destination_host=destination_address,
                                     ignore_errors=True)
        log_path = '/tmp/kea.log-ddns'
        fabric_download_file(log_path,
                             local_dest_dir,
                             destination_host=destination_address, ignore_errors=True,
                             hide_all=not world.f_cfg.forge_verbose)


def db_setup(dest=world.f_cfg.mgmt_address, db_name=world.f_cfg.db_name,
             db_user=world.f_cfg.db_user, db_passwd=world.f_cfg.db_passwd,
             init_db=True, disable=world.f_cfg.disable_db_setup):
    if disable:
        return

    if world.f_cfg.install_method != 'make':
        if world.server_system == 'redhat':
            fabric_run_command("rpm -qa '*kea*'", destination_host=dest)
        elif world.server_system == 'alpine':
            fabric_run_command("apk list '*kea*' | grep 'installed'", destination_host=dest)
        else:
            fabric_run_command("dpkg -l '*kea*'", destination_host=dest)

    kea_admin = world.f_cfg.sbin_join('kea-admin')

    # -------------------------------- MySQL --------------------------------- #
    cmd = "mysql -u root -N -B -e \"DROP DATABASE IF EXISTS {db_name};\"".format(**locals())
    result = fabric_sudo_command(cmd, destination_host=dest)
    assert result.succeeded
    cmd = "mysql -u root -N -B -e \"DROP USER IF EXISTS '{db_user}'@'localhost';\"".format(**locals())
    result = fabric_sudo_command(cmd, destination_host=dest)
    assert result.succeeded
    cmd = "mysql -u root -N -B -e \"FLUSH PRIVILEGES;\"".format(**locals())
    result = fabric_sudo_command(cmd, destination_host=dest)
    assert result.succeeded

    cmd = "mysql -u root -e 'CREATE DATABASE {db_name};'".format(**locals())
    fabric_sudo_command(cmd, destination_host=dest)
    cmd = "mysql -u root -e \"CREATE USER '{db_user}'@'localhost' IDENTIFIED BY '{db_passwd}';\"".format(**locals())
    fabric_sudo_command(cmd, ignore_errors=True, destination_host=dest)
    cmd = "mysql -u root -e \"SET GLOBAL log_bin_trust_function_creators=1;\""
    fabric_sudo_command(cmd, ignore_errors=True, destination_host=dest)
    cmd = "mysql -u root -e 'GRANT ALL ON {db_name}.* TO {db_user}@localhost;'".format(**locals())
    fabric_sudo_command(cmd, destination_host=dest)
    if init_db:
        cmd = "{kea_admin} db-init mysql -u {db_user} -p {db_passwd} -n {db_name}".format(**locals())
        result = fabric_run_command(cmd, destination_host=dest)
    assert result.succeeded

    # ------------------------------ PostgreSQL ------------------------------ #

    # This command is required to drop {db_user}, but fails if {db_name} is not created.
    # Let's ignore its result.
    cmd = f"cd /; psql -U postgres -c 'ALTER DATABASE {db_name} OWNER TO postgres;'"
    fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest, ignore_errors=True)

    cmd = "cd /; psql -U postgres -t -c \"DROP DATABASE IF EXISTS {db_name}\"".format(**locals())
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded
    cmd = "cd /; psql -U postgres -c \"DROP USER IF EXISTS {db_user};\"".format(**locals())
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded

    cmd = "cd /; psql -U postgres -c \"CREATE DATABASE {db_name};\"".format(**locals())
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded
    cmd = "cd /; psql -U postgres -c \"CREATE USER {db_user} WITH PASSWORD '{db_passwd}';\"".format(**locals())
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded
    cmd = "cd /; psql -U postgres -c \"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};\"".format(**locals())
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded
    cmd = f"cd /; psql -U postgres -c 'ALTER DATABASE {db_name} OWNER TO {db_user};'"
    result = fabric_sudo_command(cmd, sudo_user='postgres', destination_host=dest)
    assert result.succeeded
    if init_db:
        cmd = "{kea_admin} db-init pgsql -u {db_user} -p {db_passwd} -n {db_name}".format(**locals())
        result = fabric_run_command(cmd, destination_host=dest)
    assert result.succeeded


def insert_message_in_server_logs(message: str):
    """
    If kea is installed from the source, then insert a message in all the server logs for debugging purposes.
    The messages are formatted in similar fashion to Kea's log messages.

    :param message: the message to be logged
    """
    if world.f_cfg.install_method != 'make':
        return
    # Get only the hosts that are configured in forge.
    hosts = [host for host in [world.f_cfg.mgmt_address, world.f_cfg.mgmt_address_2] if len(host)]

    # Format the message.
    message = f'{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]} FORGE {message}'

    # Log.
    for host in hosts:
        for file in [world.cfg["kea_log_file"], world.cfg["kea_ca_log_file"]]:
            result = fabric_sudo_command(f'echo {message} >> {file}', destination_host=host)
            assert result.succeeded
