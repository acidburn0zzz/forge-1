# Copyright (C) 2012-2023 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# Author: Wlodzimierz Wencel

# This file contains a number of common steps that are general and may be used
# by a lot of feature files.

# pylint: disable=bad-indentation
# pylint: disable=consider-using-enumerate
# pylint: disable=consider-using-f-string
# pylint: disable=import-outside-toplevel
# pylint: disable=inconsistent-return-statements
# pylint: disable=invalid-name
# pylint: disable=line-too-long
# pylint: disable=logging-not-lazy
# pylint: disable=no-else-return
# pylint: disable=no-value-for-parameter
# pylint: disable=possibly-unused-variable
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-branches
# pylint: disable=too-many-function-args
# pylint: disable=undefined-variable
# pylint: disable=unknown-option-value
# pylint: disable=unidiomatic-typecheck
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import codecs
import random
import os
import logging
import select
import socket
from time import time

import scapy
from scapy.compat import raw
from scapy.sendrecv import sr
from scapy.layers import dhcp6
from scapy.layers.inet6 import IPv6, UDP
from scapy.config import conf
from scapy.volatile import RandMAC
from scapy.all import Raw

from src import misc
from src.protosupport.dhcp4_scen import DHCPv6_STATUS_CODES
from src.forge_cfg import world
from src.terrain import client_id, ia_id, ia_pd

log = logging.getLogger('forge')


# option codes for options and sub-options for dhcp v6
OPTIONS = {"client-id": 1,
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
           "vendor-class": 16,
           "vendor-specific-info": 17,
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
           "remote-id": 37,
           "subscriber-id": 38,
           "fqdn": 39,
           "lq-client-data": 45,
           "client-arch-type": 61,
           "erp-local-domain-name": 65,
           "client-link-layer-addr": 79}


def get_option_code(opt_code) -> int:
    '''
    Return an integer representation of the option code or name {opt_code}.
    :param opt_code: integer or string representing the option's code or name
    '''
    if isinstance(opt_code, str):
        if opt_code.isdigit():
            # It was an integer in string format.
            opt_code = int(opt_code)
        else:
            # It was an option name.
            opt_code = OPTIONS[opt_code]
    return opt_code

# ------------------- PREPARE MESSAGE OPTIONS BLOCK START -------------------- #


decode_hex = codecs.getdecoder("hex_codec")


def client_requests_option(opt_type):
    """
    Add RequestOption to message.
    """
    if not hasattr(world, 'oro'):
        # There was no ORO at all, create new one
        world.oro = dhcp6.DHCP6OptOptReq()
        # Scapy creates ORO with 23, 24 options request. Let's get rid of them
        world.oro.reqopts = []  # don't request anything by default

    world.oro.reqopts.append(int(opt_type))


def client_send_msg(msgname, iface=None, addr=None):
    """
    Sends specified message with defined options.
    Parameters:
    msg ('<msg> message'): name of the message.
    """
    # iface and addr not used for v6 for now.

    # Remove previous message waiting to be sent, just in case this is a
    # REQUEST after we received ADVERTISE. We don't want to send SOLICIT
    # the second time.
    world.climsg = []

    if msgname == "SOLICIT":
        msg = build_msg(dhcp6.DHCP6_Solicit())

    elif msgname == "REQUEST":
        msg = build_msg(dhcp6.DHCP6_Request())

    elif msgname == "CONFIRM":
        msg = build_msg(dhcp6.DHCP6_Confirm())

    elif msgname == "RENEW":
        msg = build_msg(dhcp6.DHCP6_Renew())

    elif msgname == "REBIND":
        msg = build_msg(dhcp6.DHCP6_Rebind())

    elif msgname == "DECLINE":
        msg = build_msg(dhcp6.DHCP6_Decline())

    elif msgname == "RELEASE":
        msg = build_msg(dhcp6.DHCP6_Release())

    elif msgname == "INFOREQUEST":
        msg = build_msg(dhcp6.DHCP6_InfoRequest())

    elif msgname == "LEASEQUERY":
        msg = build_msg(dhcp6.DHCP6_Leasequery())

    else:
        assert False, "Invalid message type: %s" % msgname

    assert msg, "Message preparation failed"

    if msg:
        world.climsg.append(msg)

    log.debug("Message %s will be sent over %s interface." % (msgname, world.cfg["iface"]))


def client_sets_value(value_name, new_value):
    if value_name in world.cfg["values"]:
        if isinstance(world.cfg["values"][value_name], str):
            world.cfg["values"][value_name] = str(new_value)
        elif isinstance(world.cfg["values"][value_name], int):
            world.cfg["values"][value_name] = int(new_value)
        else:
            world.cfg["values"][value_name] = new_value
    else:
        assert value_name in world.cfg["values"], "Unknown value name : %s" % value_name


def unicast_address(addr_type):
    """
    Turn off sending on All_DHCP_Relay_Agents_and_Servers, and use UNICAST address.
    """
    if addr_type:
        world.cfg["address_v6"] = world.f_cfg.srv_ipv6_addr_global
    else:
        world.cfg["address_v6"] = world.f_cfg.srv_ipv6_addr_link_local


def client_does_include(sender_type, opt_type, value=None):
    """
    Include options to message. This function refers to @step in lettuce
    """

    assert sender_type in ["Client", "RelayAgent", "Relay-Supplied-Option"], "Two sender type accepted: Client or" \
                                                                             " RelayAgent, your choice is: " \
                                                                             + sender_type
    world.sender_type = sender_type
    # value variable not used in v6
    # If you want to use options of received message to include it,
    # please use 'Client copies (\S+) option from received message.' step.
    if world.cfg["values"]["DUID"] is not None:
        world.cfg["values"]["cli_duid"] = convert_DUID(world.cfg["values"]["DUID"])

    if opt_type == "client-id":
        add_client_option(dhcp6.DHCP6OptClientId(duid=world.cfg["values"]["cli_duid"]))

    if opt_type == "wrong-client-id":
        # used for backwards compatibility
        add_client_option(dhcp6.DHCP6OptClientId(duid=dhcp6.DUID_LLT(timeval=int(time()), lladdr=RandMAC())))

    elif opt_type == "empty-client-id":
        add_client_option(dhcp6.DHCP6OptClientId())

    elif opt_type == "wrong-server-id":
        # used for backwards compatibility
        add_client_option(dhcp6.DHCP6OptServerId(duid=convert_DUID(world.cfg["values"]["server_id"])))

    elif opt_type == "server-id":
        add_client_option(dhcp6.DHCP6OptServerId(duid=convert_DUID(world.cfg["values"]["server_id"])))

    elif opt_type == "relay-id":
        if convert_DUID(world.cfg["values"]["relay_id"]):
            add_client_option(dhcp6.DHCP6OptRelayId(duid=convert_DUID(world.cfg["values"]["relay_id"])))
        else:
            add_client_option(dhcp6.DHCP6OptRelayId())

    elif opt_type == "empty-server-id":
        add_client_option(dhcp6.DHCP6OptServerId())

    elif opt_type == "preference":
        add_client_option(dhcp6.DHCP6OptPref(prefval=world.cfg["values"]["prefval"]))

    elif opt_type == "rapid-commit":
        add_client_option(dhcp6.DHCP6OptRapidCommit())

    elif opt_type in ["time", "elapsedtime"]:
        add_client_option(dhcp6.DHCP6OptElapsedTime(elapsedtime=world.cfg["values"]["elapsedtime"]))

    elif opt_type == "relay-msg":
        add_client_option(dhcp6.DHCP6OptRelayMsg(message=dhcp6.DHCP6_Solicit()))

    elif opt_type == "server-unicast":
        add_client_option(dhcp6.DHCP6OptServerUnicast(srvaddr=world.cfg["values"]["srvaddr"]))

    elif opt_type == "status-code":
        add_client_option(dhcp6.DHCP6OptStatusCode(statuscode=world.cfg["values"]["statuscode"],
                                                   statusmsg=world.cfg["values"]["statusmsg"]))

    elif opt_type == "interface-id":
        add_client_option(dhcp6.DHCP6OptIfaceId(ifaceid=world.cfg["values"]["ifaceid"]))

    elif opt_type == "reconfigure":
        add_client_option(dhcp6.DHCP6OptReconfMsg(msgtype=world.cfg["values"]["reconfigure_msg_type"]))

    elif opt_type == "reconfigure-accept":
        add_client_option(dhcp6.DHCP6OptReconfAccept())

    elif opt_type == "option-request":
        # later we can make it adjustable
        add_client_option(dhcp6.DHCP6OptOptReq(reqopts=world.cfg["values"]["reqopts"]))

    elif opt_type == "IA-PD":
        if len(world.iapd) > 0:
            add_client_option(dhcp6.DHCP6OptIA_PD(iaid=int(world.cfg["values"]["ia_pd"]),
                                                  T1=world.cfg["values"]["T1"],
                                                  T2=world.cfg["values"]["T2"],
                                                  iapdopt=world.iapd))
            world.iapd = []
        else:
            add_client_option(dhcp6.DHCP6OptIA_PD(iaid=int(world.cfg["values"]["ia_pd"]),
                                                  T1=world.cfg["values"]["T1"],
                                                  T2=world.cfg["values"]["T2"]))

    elif opt_type == "IA-NA":
        if len(world.iaad) > 0:
            add_client_option(dhcp6.DHCP6OptIA_NA(iaid=int(world.cfg["values"]["ia_id"]),
                                                  T1=world.cfg["values"]["T1"],
                                                  T2=world.cfg["values"]["T2"],
                                                  ianaopts=world.iaad))
            world.iaad = []
        else:
            add_client_option(dhcp6.DHCP6OptIA_NA(iaid=int(world.cfg["values"]["ia_id"]),
                                                  T1=world.cfg["values"]["T1"],
                                                  T2=world.cfg["values"]["T2"]))

    elif opt_type == "IA_Prefix":
        world.iapd.append(dhcp6.DHCP6OptIAPrefix(preflft=world.cfg["values"]["preflft"],
                                                 validlft=world.cfg["values"]["validlft"],
                                                 plen=world.cfg["values"]["plen"],
                                                 prefix=world.cfg["values"]["prefix"]))

    elif opt_type == "IA_Address":
        world.iaad.append(dhcp6.DHCP6OptIAAddress(addr=world.cfg["values"]["IA_Address"],
                                                  preflft=world.cfg["values"]["preflft"],
                                                  validlft=world.cfg["values"]["validlft"]))

    elif opt_type == "user-class":
        if world.cfg["values"]["user_class_data"] == "":
            add_client_option(dhcp6.DHCP6OptUserClass())
        else:
            add_client_option(dhcp6.DHCP6OptUserClass(userclassdata=dhcp6.USER_CLASS_DATA(data=str(world.cfg["values"]["user_class_data"]))))

    elif opt_type == "vendor-class":
        if world.cfg["values"]["vendor_class_data"] == "":
            add_client_option(dhcp6.DHCP6OptVendorClass(enterprisenum=world.cfg["values"]["enterprisenum"]))
        else:
            add_client_option(dhcp6.DHCP6OptVendorClass(enterprisenum=world.cfg["values"]["enterprisenum"],
                                                        vcdata=dhcp6.VENDOR_CLASS_DATA(
                                                            data=world.cfg["values"]["vendor_class_data"])))

    elif opt_type == "vendor-specific-info":
        # convert data for world.vendor with code == 1 (option request)
        # that is the only one option that needs converting.
        vendor_option_request_convert()

        # build VENDOR_CPECIDIC_OPTIONs depending on world.vendor:
        vso_tmp = []
        for each in world.vendor:
            vso_tmp.append(dhcp6.VENDOR_SPECIFIC_OPTION(optcode=each[0],
                                                        optdata=each[1]))
        add_client_option(dhcp6.DHCP6OptVendorSpecificInfo(enterprisenum=world.cfg["values"]["enterprisenum"],
                                                           vso=vso_tmp))
        # clear vendor list
        world.vendor = []

    elif opt_type == "fqdn":
        if world.cfg["values"]["FQDN_flags"] is None:
            assert False, "Please define FQDN flags first."

        converted_fqdn = world.cfg["values"]["FQDN_domain_name"]
        add_client_option(dhcp6.DHCP6OptClientFQDN(flags=str(world.cfg["values"]["FQDN_flags"]),
                                                   fqdn=converted_fqdn))

    elif opt_type == "client-link-layer-addr":
        add_client_option(dhcp6.DHCP6OptClientLinkLayerAddr(lltype=world.cfg["values"]["address_type"],
                                                            clladdr=world.cfg["values"]["link_local_mac_addr"]))

    elif opt_type == "remote-id":
        add_client_option(dhcp6.DHCP6OptRemoteID(enterprisenum=world.cfg["values"]["enterprisenum"],
                                                 remoteid=decode_hex(world.cfg["values"]["remote_id"].replace(':', ''))[0]))

    elif opt_type == "subscriber-id":
        add_client_option(dhcp6.DHCP6OptSubscriberID(subscriberid=decode_hex(world.cfg["values"]["subscriber_id"].replace(':', ''))[0]))

    elif opt_type == "interface-id":
        add_client_option(dhcp6.DHCP6OptIfaceId(ifaceid=world.cfg["values"]["ifaceid"]))

    elif opt_type == "nii":
        add_client_option(dhcp6.DHCP6OptClientNetworkInterId(iitype=world.cfg["values"]["iitype"],
                                                             iimajor=world.cfg["values"]["iimajor"],
                                                             iiminor=world.cfg["values"]["iiminor"]))

    elif opt_type == "client-arch-type":
        add_client_option(dhcp6.DHCP6OptClientArchType(archtypes=world.cfg["values"]["archtypes"]))

    elif opt_type == "erp-local-domain-name":
        add_client_option(dhcp6.DHCP6OptERPDomain(erpdomain=[world.cfg["values"]["erpdomain"]]))

    elif opt_type == "rsoo":
        add_client_option(dhcp6.DHCP6OptRelaySuppliedOpt(relaysupplied=world.rsoo))

    elif opt_type == "time-elapsed":
        add_client_option(dhcp6.DHCP6OptElapsedTime(elapsedtime=world.cfg["values"]["elapsedtime"]))
    elif opt_type == "lq-query":
        tmp = world.cliopts.copy()
        world.cliopts = []
        add_client_option(dhcp6.DHCP6OptLqQuery(querytype=world.cfg["values"]["lq-query-type"],
                                                linkaddr=world.cfg["values"]["lq-query-address"],
                                                queryopts=tmp))
    else:
        assert "unsupported option: " + opt_type


def change_message_field(message_filed, value, value_type):
    convert_type = {"int": int,
                    "string": str,
                    "str": str,
                    "unicode": str}

    convert = convert_type[value_type]
    world.message_fields.append([str(message_filed), convert(value)])


def apply_message_fields_changes():
    for field_details in world.message_fields:

        try:
            setattr(world.climsg[0], field_details[0], field_details[1])
        except BaseException:
            assert False, "Message does not contain field: %s " % str(field_details[0])


def add_vendor_suboption(code, data):
    # if code == 1 we need check if we added code=1 before
    # if we do, we need append only data not whole suboption
    if code == 1 and len(world.vendor) > 0:
        for each in world.vendor:
            if each[0] == 1:
                each[1].append(int(data))

    # if world.vendor is empty and code == 1 add
    # code =1 and data as int (required to further conversion)
    elif code == 1:
        world.vendor.append([code, [int(data)]])

    # every other option just add
    else:
        world.vendor.append([code, str(data)])


def generate_new(opt):
    """
    Generate new client id with random MAC address.
    """
    if opt == 'client':
        client_id(RandMAC())
        ia_id()
    elif opt == 'Client_ID':
        client_id(RandMAC())
    elif opt == 'IA':
        ia_id()
    elif opt == 'IA_PD':
        ia_pd()

    else:
        assert False,  opt + " generation unsupported"


# -------------------- PREPARE MESSAGE OPTIONS BLOCK END --------------------- #


# ------------------------ BUILD MESSAGE BLOCK START ------------------------- #


def add_client_option(option):
    if world.sender_type == "Client":
        world.cliopts.append(option)
    elif world.sender_type == "RelayAgent":
        world.relayopts.append(option)
    elif world.sender_type == "Relay-Supplied-Option":
        world.rsoo.append(option)
    else:
        assert False, "Something went wrong with sender_type in add_client_option- you should never seen this error"


def add_option_to_msg(msg, option):
    # this is request_option option
    msg /= option
    return msg


def client_add_saved_option(erase, count="all"):
    """
    Add saved option to message, and erase.
    """
    if count == "all":
        for each_key in list(world.savedmsg.keys()):
            for every_opt in world.savedmsg[each_key]:
                world.cliopts.append(every_opt)
            if erase:
                world.savedmsg = {}
    else:
        if count not in world.savedmsg:
            assert False, "There is no set no. {count} in saved options".format(**locals())

        for each in world.savedmsg[count]:
            world.cliopts.append(each)
        if erase:
            world.savedmsg[count] = []


def vendor_option_request_convert():
    data_tmp = ''
    for each in world.vendor:
        if each[0] == 1:
            for number in each[1]:
                data_tmp += '\00' + str(chr(number))
            each[1] = data_tmp
        else:
            # each[1] = each[1].replace(':', '').decode('hex')
            each[1] = decode_hex(each[1].replace(':', ''))[0]


def convert_DUID_hwaddr(duid, threshold):
    tmp = duid[threshold:]
    hwaddr = ':'.join(tmp[i:i+2] for i in range(0, len(tmp), 2))
    return hwaddr


def convert_DUID(duid):
    """
    We can use two types of DUID:
        DUID_LLT link layer address + time (e.g. 00:01:00:01:52:7b:a8:f0:08:00:27:58:f1:e8 )
        DUID_LL link layer address (e.g. 00:03:00:01:ff:ff:ff:ff:ff:01 )

        third DUID based on vendor is not supported (also not planned to be ever supported)

        In case of using DUID_LLT:
            00:01:00:01:52:7b:a8:f0:08:00:27:58:f1:e8
            00:01 - duid type, it need to be 0001 for DUID_LLT
                  00:01 - hardware type, make it always 0001
                        52:7b:a8:f0 - converted time value
                                    08:00:27:58:f1:e8 - link layer address

        In case of using DUID_LL:
            00:03:00:01:ff:ff:ff:ff:ff:01
            00:03 - duid type, it need to be 0003 for DUID_LL
                  00:01 - hardware type, make it always 0001
                        ff:ff:ff:ff:ff:01 - link layer address

        You can use two forms for each DUID type, with ":" and without.
        For example
                00:01:00:01:52:7b:a8:f0:08:00:27:58:f1:e8
            it's same as:
                00010001527ba8f008002758f1e8
            and
                00:03:00:01:ff:ff:ff:ff:ff:01
            it's same as:
                00030001ffffffffff01

        Other configurations will cause to fail test.
    """
    if isinstance(duid, (dhcp6.DUID_LLT, dhcp6.DUID_LL, dhcp6.DUID_EN)):
        return duid

    duid = duid.replace(":", "")

    if duid[:8] == "00030001":
        return dhcp6.DUID_LL(lladdr=convert_DUID_hwaddr(duid, 8))
    elif duid[:8] == "00010001":
        return dhcp6.DUID_LLT(timeval=int(duid[8:16], 16), lladdr=convert_DUID_hwaddr(duid, 16))
    else:
        assert False, "DUID value is not valid! DUID: " + duid


def build_raw(msg, append):
    if msg == "":
        world.climsg.append(build_msg("") / Raw(load=append))
    else:
        client_send_msg(msg, None, None)
        world.climsg[0] = world.climsg[0] / Raw(load=append)


def build_msg(msg_dhcp):
    msg = IPv6(dst=world.cfg["address_v6"], src=world.cfg["cli_link_local"])
    msg /= UDP(sport=world.cfg["source_port"], dport=world.cfg["destination_port"])

    # print("IP/UDP layers in bytes: ", raw(msg))

    msg /= msg_dhcp

    # get back to multicast address.
    world.cfg["address_v6"] = "ff02::1:2"

    # transaction id
    if world.cfg["values"]["tr_id"] is None:
        msg.trid = random.randint(0, 256*256*256)
    else:
        msg.trid = int(world.cfg["values"]["tr_id"])
    world.cfg["values"]["tr_id"] = msg.trid

    # add option request if any
    try:
        if len(world.oro.reqopts) > 0:
            msg = add_option_to_msg(msg, world.oro)
    except BaseException:
        pass

    # add all rest options to message.
    world.cliopts = world.cliopts[::-1]
    while world.cliopts:
        msg /= world.cliopts.pop()

    # print("DHCP layer in bytes: ", raw(msg.getlayer(2)), "\n")
    return msg


def create_relay_forward(level=1):
    """
    Encapsulate message in relay-forward message.
    """
    assert level > 0
    # set flag for adding client option client-id which is added by default
    world.cfg["relay"] = True

    # we pretend to be relay-server so we need to listen on 547 port
    world.cfg["source_port"] = 547

    # get only DHCPv6 part of the message
    msg = world.climsg.pop().getlayer(2)

    # message encapsulation
    for lvl in range(level):
        # all three values: linkaddr, peeraddr and hopcount must be filled
        relay_msg = dhcp6.DHCP6_RelayForward(hopcount=lvl,
                                             linkaddr=world.cfg["values"]["linkaddr"],
                                             peeraddr=world.cfg["values"]["peeraddr"])
        for each_option in world.relayopts:
            relay_msg /= each_option
        relay_msg /= dhcp6.DHCP6OptRelayMsg(message=msg)

        msg = relay_msg

    # build full message
    full_msg = IPv6(dst=world.cfg["address_v6"],
                    src=world.cfg["cli_link_local"])
    full_msg /= UDP(sport=world.cfg["source_port"],
                    dport=world.cfg["destination_port"])
    full_msg /= msg

    # in case if unicast used, get back to multicast address.
    world.cfg["address_v6"] = "ff02::1:2"

    world.climsg.append(full_msg)
    world.relayopts = []
    world.cfg["source_port"] = 546  # we should be able to change relay ports from test itself
    world.cfg["relay"] = False


# ------------------------- BUILD MESSAGE BLOCK END -------------------------- #

# --------------------- SEND/RECEIVE MESSAGE BLOCK START --------------------- #

def read_dhcp6_msgs(d: bytes, msg: list):
    """
    Recursively parse bytes received via TCP channel
    :param d: bytes
    :param msg: list of DHCP6 messages
    :return: list of DHCP6 messages
    """
    if len(d) == 0:
        return msg
    stop = int.from_bytes(d[:2], "big")
    pkt = dhcp6.DHCP6(d[2:stop + 2])
    pkt.build()
    msg.append(pkt)
    if len(d[stop:]) > 0:
        msg = read_dhcp6_msgs(d[stop+2:], msg)
    return msg


def close_sockets(socket_list):
    for each_socket in socket_list:
        each_socket.close()


def send_over_tcp(msg: bytes, address: str = None, port: int = None, timeout: int = 3, parse: bool = True,
                  number_of_connections: int = 1, print_all: bool = True):
    """
    Send message over TCP channel and listen for response
    :param msg: bytes representing DHCP6 message
    :param address: address to which message will be sent
    :param port: port number on which receiving end is listening
    :param timeout: how long kea will wait from last received message
    :param parse: should received bytes be parsed into DHCP6 messages
    :param number_of_connections: how many connections should forge open
    :param print_all: print all to stdout (use false for massive messages)
    :return: list of parsed DHCP6 messages
    """
    if address is None:
        address = world.f_cfg.srv_ipv6_addr_global
    if port is None:
        port = 547
    received = b''

    socket_list = [socket.socket(socket.AF_INET6, socket.SOCK_STREAM) for _ in range(number_of_connections)]
    new_xid = random.randint(100, 3000)  # to generate transaction id
    try:
        for each_socket in socket_list:
            each_socket.connect((address, port))
            world.blq_trid = new_xid
            d = msg[:1] + new_xid.to_bytes(3, 'big') + msg[4:]
            msg_length = len(d)
            c_msg = msg_length.to_bytes(2, 'big') + d
            if world.f_cfg.show_packets_from in ['both', 'client'] and print_all:
                log.info('Transaction id of BLQ message was changed to %s', new_xid)
                log.info("TCP msg (bytes): %s", c_msg)
                log.info("TCP msg (hex): %s", ' '.join(c_msg.hex()[i:i+2] for i in range(0, len(c_msg.hex()), 2)))
            each_socket.send(c_msg)
            new_xid += 1
    except ConnectionRefusedError as e:
        assert False, f"TCP connection on {socket} to {address}:{port} was unsuccessful with error: {e}"

    end = time() + timeout
    while 1:
        read_sockets, write_sockets, error_sockets = select.select(socket_list, [], [], 3)
        for r_sock in read_sockets:
            data = r_sock.recv(4096)
            if data:
                received += data
                log.info("%d bytes received via TCP connection.", len(received))
        if parse and len(received) > 0:
            msgs = read_dhcp6_msgs(received, [])
            # At this point of forge and kea development we expect only leasequery messages via tcp
            # and correct message exchange will be concluded with leasequery-done message (type 16)
            # so that's the point in which we close sockets and return all messages. If message
            # leasequery-done will not be last message received and we reach timeout value - messages
            # will also be returned, infinite wait won't happen
            if msgs[-1].msgtype == 16:
                close_sockets(socket_list)
                return msgs
        else:
            msgs = received
        if time() > end:
            close_sockets(socket_list)
            break

    return msgs


def send_wait_for_message(requirement_level: str, presence: bool, exp_message: str,
                          protocol: str = 'UDP', address: str = None, port: int = None):
    world.cliopts = []  # clear options, always build new message, also possible make it in client_send_msg
    # debug.recv=[]
    # Uncomment this to get debug.recv filled with all received messages
    conf.debug_match = True

    # checkIPsrc must be False so scapy can correctly match response to request
    conf.checkIPsrc = False
    apply_message_fields_changes()

    factor = 1
    world.srvmsg = []
    world.tcpmsg = []
    received_name = ""

    pytest_current_test = os.environ.get('PYTEST_CURRENT_TEST')
    if 'HA' in pytest_current_test.split('/'):
        factor = max(factor, world.f_cfg.ha_packet_wait_interval_factor)
    if '_radius' in pytest_current_test.lower():
        factor = max(factor, world.f_cfg.radius_packet_wait_interval_factor)

    if world.f_cfg.show_packets_from in ['both', 'client']:
        world.climsg[0].show()

    if protocol == 'UDP':
        ans, unans = sr(world.climsg,
                        iface=world.cfg["iface"],
                        timeout=factor * world.cfg['wait_interval'],
                        nofilter=1,
                        verbose=int(world.f_cfg.forge_verbose))
        if world.f_cfg.forge_verbose == 0:
            print(".", end='')

        for x in ans:
            a, b = x
            world.srvmsg.append(b)

    else:
        address = world.f_cfg.srv_ipv6_addr_global if address is None else address
        world.tcpmsg = send_over_tcp(raw(world.climsg[0].getlayer(2)), address, port)
        if len(world.tcpmsg) > 0:
            world.srvmsg = world.tcpmsg.copy()
        unans = []

    if world.f_cfg.show_packets_from in ['both', 'server']:
        for msg in world.srvmsg:
            msg.show()

    if len(world.srvmsg) > 0:
        received_name = get_msg_type(world.srvmsg[0])

    if not world.loops["active"]:
        for msg in world.srvmsg:
            log.info("Received packet %s (code %s)" % (get_msg_type(msg), msg.msgtype))

    if exp_message is not None:
        for x in unans:
            log.error(("Unanswered packet type=%s" % get_msg_type(x)))

    if presence:
        assert len(world.srvmsg) != 0, "No response received."
        assert received_name == exp_message, f"Expected message {exp_message} not received (got {received_name})"
    elif not presence:
        assert len(world.srvmsg) == 0, f"Response received ({received_name}) was not expected!"

    return world.srvmsg


def get_last_response():
    assert len(world.srvmsg), "No response received."
    return world.srvmsg[-1].copy()

# ---------------------- SEND/RECEIVE MESSAGE BLOCK END ---------------------- #

# ---------------------- PARSING RECEIVED MESSAGE BLOCK START ----------------------


def get_msg_type(msg):
    msg_types = {2: "ADVERTISE",
                 3: "REQUEST",
                 7: "REPLY",
                 13: "RELAYREPLY",
                 15: "LEASEQUERY-REPLY",
                 17: "LEASEQUERY-DATA",
                 16: "LEASEQUERY-DONE"}

    if msg.msgtype in msg_types:
        return msg_types[msg.msgtype]
    return "UNKNOWN-TYPE"


def client_save_option(option_name, count=0):
    assert option_name in OPTIONS, "Unsupported option name " + option_name
    opt_code = OPTIONS.get(option_name)
    opt = get_option(get_last_response(), opt_code)

    assert opt, "Received message does not contain option " + option_name
    opt.payload = scapy.packet.NoPayload()

    if count not in world.savedmsg:
        world.savedmsg[count] = [opt]
    else:
        world.savedmsg[count].append(opt)


def client_copy_option(option_name, copy_all=False):
    """
    Copy options with given name from the last received message.

    :param option_name: the name of the option, as specified in {OPTIONS}
    :param copy_all: True if you all options are copied, False otherwise
    """
    assert world.srvmsg

    assert option_name in OPTIONS, "Unsupported option name " + option_name
    opt_code = OPTIONS.get(option_name)

    # find and copy option
    opt = get_option(world.srvmsg[0], opt_code, get_all=copy_all)

    assert opt, "Received message does not contain option " + option_name

    # payload need to be 'None' otherwise we copy all options from one we are
    # looking for till the end of the message
    # it would be nice to remove 'status code' sub-option
    # before sending it back to server
    if copy_all and isinstance(opt, list):
        for i in opt:
            i.payload = scapy.packet.NoPayload()
            add_client_option(i)
    else:
        opt.payload = scapy.packet.NoPayload()
        add_client_option(opt)


def get_option(msg, opt_code, get_all=False):
    '''
    Retrieve from scapy message {msg}, the DHCPv6 option having IANA code {opt_code}.
    :param msg: scapy message to retrieve the option from
    :param opt_code: option code or name
    :param get_all: True if it should return all options with given code,
                    False if a single option is required
    :return: scapy message representing the option or None if the option doesn't exist
             or list of options if there are multiple
    '''

    # Ensure the option code is an integer.
    opt_code = get_option_code(opt_code)

    # We need to iterate over all options and see
    # if there's one we're looking for

    # message needs to be copied, otherwise we changing original message
    # what makes sometimes multiple copy impossible.
    tmp_msg = msg.copy()

    # clear all opts/subopts
    world.opts = []
    world.subopts = []
    result = []

    if len(world.rlymsg) == 0 and len(world.tcpmsg) == 0:  # relay message is already cropped to exact layer
        tmp_msg = tmp_msg.getlayer(3)  # 0th is IPv6, 1st is UDP, 2nd is DHCP6, 3rd is the first option
    elif len(world.tcpmsg) != 0:
        tmp_msg = tmp_msg.getlayer(1)

    # check all message, for expected option and all suboptions in IA_NA/IA_PD
    check_suboptions = ["clientoptions",
                        "ianaopts",
                        "iapdopt",
                        "iaprefopts",
                        "relaysupplied",
                        "userclassdata",
                        "queryopts",
                        "vcdata",
                        "vso"]

    while tmp_msg:
        if tmp_msg.optcode == opt_code:
            opt = tmp_msg.copy()
            del opt.payload
            result.append(opt)
            world.opts.append(opt)

        for each in check_suboptions:
            if tmp_msg.fields.get(each):
                # there can be multiple suboptions, we need them all!
                for sub_option in tmp_msg.fields.get(each):
                    # and sometimes options are combined in two, I don't know why, so we have to loop over them again
                    # to get all options that are send as suboptions.
                    while sub_option:
                        t = sub_option.copy()
                        del t.payload
                        world.subopts.append([tmp_msg.optcode, t])
                        sub_option = sub_option.payload

        tmp_msg = tmp_msg.payload

    if len(result) > 0 and not get_all:
        result = result[-1]

    return result


def unknown_option_to_str(data_type, opt):
    if data_type == "uint8":
        assert len(opt.data) == 1, "Received option " + opt.optcode + " contains " + len(opt.data) + \
                                   " bytes, but expected exactly 1"
        return str(ord(opt.data[0:1]))
    else:
        assert False, "Parsing of option format " + str(data_type) + " not implemented."


def _get_opt_descr(opt_code):
    '''
    Get a textual description as provided by scapy, of option code or name {opt_code}.
    :param opt_code: the option code or name that is being described
    :return: the description
    '''

    # Ensure the option code is an integer.
    opt_code = get_option_code(opt_code)

    try:
        opt = dhcp6.dhcp6opts_by_code[opt_code]
    except KeyError:
        opt = 'unknown'
    opt_descr = "%s[%s]" % (opt, opt_code)
    return opt_descr


def response_check_include_option(must_include, opt_code):
    """
    Checking presence of expected option.
    """
    assert len(world.srvmsg) != 0, "No response received."

    opt = get_option(world.srvmsg[0], opt_code)

    opt_descr = _get_opt_descr(opt_code)
    if must_include:
        assert opt, "Expected option {opt_descr} not present in the message.".format(**locals()) + \
                    "\nPacket:" + str(world.srvmsg[0].show(dump=True))
    else:
        assert len(opt) == 0, "Unexpected option {opt_descr} found in the message.".format(**locals()) + \
                            "\nPacket:" + str(world.srvmsg[0].show(dump=True))

    return opt
# Returns text representation of the option, interpreted as specified by data_type


def get_subopt_from_option(exp_opt_code, exp_subopt_code):
    '''
    Get the list of {exp_subopt_code} suboptions which are inside option
    {exp_opt_code} that should have been previously retrieved through
    get_option().
    :param exp_opt_code: the option code or name that was previously retrieved through get_option()
    :param exp_subopt_code: the option code or name to be retrieved, nested inside the higher-level option
    :return: tuple(the list of suboptions, the suboption code)
    '''

    # Ensure option codes are integers.
    exp_opt_code = get_option_code(exp_opt_code)
    exp_subopt_code = get_option_code(exp_subopt_code)
    result = []
    received = ''
    list_fields = ["clientoptions",
                   "ianaopts",
                   "iapdopt",
                   "iaprefopts",
                   "message",
                   "relaysupplied",
                   "userclassdata",
                   "queryopts",
                   "vcdata",
                   "vso"]
    # firstly we go through all options that can include sub-options
    for opt_code, opt_data in world.subopts:
        # we need to be sure that option 13 is in 25 or 3
        # otherwise sub-option 13 from option 3 could be taken
        # as sub-option from option 25. And that's important!
        if opt_code != exp_opt_code:
            continue
        if opt_code == exp_opt_code:
            if opt_data.optcode == exp_subopt_code:
                result.append(opt_data)
                received = str(opt_data.optcode)
        # now we need to find specific sub-option list:
        for list_field in list_fields:
            # if we found list - we need to check every option on that list
            subopts = opt_data.fields.get(list_field)
            if not subopts:
                continue

            for option_in_the_list in subopts:
                # if on selected list there is option we are looking for, return it!
                if option_in_the_list.optcode == exp_subopt_code:
                    result.append(option_in_the_list)
                    received = str(option_in_the_list.optcode)
    return result, received


def get_suboption(opt_code, subopt_code):
    opt, _ = get_subopt_from_option(opt_code, subopt_code)
    return opt


def extract_duid(option):
    if option.type == 1:
        # DUID_LLT
        return "0001000" + str(option.hwtype) + str(hex(option.timeval))[2:] + str(option.lladdr).replace(":", "")
    elif option.type == 2:
        # DUID_EN
        return "0002" + str(option.enterprisenum) + str(option.id.decode())
    elif option.type == 3:
        # DUID_LL
        return "0003000" + str(option.hwtype) + str(option.lladdr).replace(":", "")


def response_check_include_suboption(opt_code, expect, expected_value):
    """
    Assert that suboption {expected_value} exists inside option {opt_code}
    if {expect} is True or doesn't exist if {expect} is False.
    :param opt_code: option code or name
    :param expect: whether the suboption should exist
    :param expected_value: suboption code or name
    :return: tuple(the list of suboptions, the suboption code)
    """
    x = []
    opt_code = get_option_code(opt_code)
    expected_value = get_option_code(expected_value)
    for option_code, option in world.subopts:
        if option_code == opt_code and option.optcode == int(expected_value):
            x.append(option)
    opt_descr = _get_opt_descr(opt_code)
    subopt_descr = _get_opt_descr(expected_value)
    if expect:
        assert len(x) > 0, "Expected sub-option {subopt_descr} not present in the option {opt_descr}".format(**locals())
    else:
        assert len(x) == 0, "NOT expected sub-option {subopt_descr} is present in the option {opt_descr}".format(**locals())
    return x


values_equivalent = {7: "prefval", 13: "statuscode", 21: "sipdomains", 22: "sipservers", 23: "dnsservers",
                     24: "dnsdomains", 27: "nisservers", 28: "nispservers", 29: "nisdomain", 30: "nispdomain",
                     31: "sntpservers", 32: "reftime"}


def response_check_suboption_content(subopt_code, opt_code, expect, data_type, expected_value):
    '''
    Assert that field {data_type} from option {subopt_code} nested inside option
    {opt_code} has {expected_value} if {expect} is True. Or check that it has a
    different value than {expected_value} if {expect} is False.
    :param subopt_code: suboption code or name
    :param opt_code: option code or name
    :param expect: whether the value is expected or not in the suboption
    :param data_type: the suboption field whose value is checked
    :param expected_value: the value that is checked
    '''

    # Ensure the option codes are integers.
    opt_code = get_option_code(opt_code)
    subopt_code = get_option_code(subopt_code)

    # first check if subotion exists and get suboption
    if opt_code == 17:
        data_type = "optdata"
    data_type = str(data_type)
    expected_value = str(expected_value)
    received = []
    opts = response_check_include_suboption(opt_code, True, subopt_code)
    # that is duplicated code but lets leave it for now
    for opt in opts:
        tmp_field = opt.fields.get(data_type)
        if tmp_field is None:
            if opt_code not in [17]:
                data_type = values_equivalent.get(opt_code)
            tmp_field = opt.fields.get(data_type)
        if type(tmp_field) is list:
            received.append(",".join(tmp_field))
        if data_type == 'duid':
            txt_duid = extract_duid(tmp_field)
            received.append(":".join([txt_duid[i:i+2] for i in range(0, len(txt_duid), 2)]))
        else:
            if isinstance(tmp_field, bytes):
                received.append(tmp_field.decode('utf-8'))
            else:
                received.append(str(tmp_field))

    opt_descr = _get_opt_descr(opt_code)

    if expect:
        assert expected_value in received, ("Invalid {opt_descr} option, received {data_type}: ".format(**locals()) +
                                            ",".join(received) + ", but expected " + str(expected_value))
    else:
        assert expected_value not in received, ("Received value of {data_type}: ".format(**locals()) + ",".join(received) +
                                                " should not be equal to value from client - " + str(expected_value))


def convert_relayed_message(relayed_option):
    world.rlymsg.append(relayed_option)
    world.srvmsg.pop()
    world.srvmsg.append(relayed_option.message)


def response_check_option_content(opt_code, expect, data_type, expected_value):
    '''
    Assert that field {data_type} of option with code or name {opt_code} has
    value {expected_value} if {expect} is True or has a different value if
    {expect} is False.
    :param opt_code: option code or name
    :param expect: whether the value is expected or not
    :param data_type: the option field whose value is checked
    :param expected_value: the value that is checked
    '''

    # Ensure the option code is an integer.
    opt_code = get_option_code(opt_code)

    data_type = str(data_type)
    expected_value = str(expected_value)
    initial_data_type = data_type
    # without any msg received, fail test
    assert len(world.srvmsg) != 0, "No response received."
    # get that one option, also fill world.opts (for multiple options same type, e.g. IA_NA)
    # and world.subopts for suboptions for e.g. IA Address or StatusCodes
    x = get_option(world.srvmsg[0], opt_code)
    received = []

    opt_descr = _get_opt_descr(opt_code)

    assert x, "Expected option {opt_descr} not present in the message.".format(**locals())
    # test all collected options,:
    # couple tweaks to make checking smoother

    if opt_code == 9:
        convert_relayed_message(x)
    else:
        if data_type == "iapd":
            data_type = "iaid"
        if data_type == "duid":
            expected_value = expected_value.replace(":", "")
            received.append(extract_duid(x.duid))
        else:
            for each in x:
                tmp_field = each.fields.get(data_type)
                if tmp_field is None:
                    data_type = values_equivalent.get(opt_code)
                    tmp_field = each.fields.get(data_type)
                if type(tmp_field) is list:
                    received.append(",".join(tmp_field))
                else:
                    if isinstance(tmp_field, bytes):
                        received.append(tmp_field.decode('utf-8'))
                    else:
                        received.append(str(tmp_field))
        # test if expected option/suboption/value is in all collected options/suboptions/values
        if received[0] == 'None':
            assert False, "Within option " + opt_descr + " there is no " + initial_data_type + \
                          " value. Probably that is test error"

        if expect:
            assert expected_value in received, "Invalid " + opt_descr + " option, received " + \
                                               data_type + ": " + ",".join(received) + ", but expected " + \
                                               str(expected_value)
        else:
            assert expected_value not in received, "Received value of " + data_type + ": " + ",".join(received) + \
                                                   " should not be equal to value from client - " + str(expected_value)
    return received


def save_value_from_option(value_name, option_name):

    assert world.srvmsg
    get_option(world.srvmsg[0], option_name)
    if len(world.opts) == 0:
        temp = world.subopts[0][1].payload
        world.savedvalue = getattr(temp, value_name)
        world.subopts = []
    else:
        world.savedvalue = getattr(world.opts[0], value_name)
        world.opts = []
        world.subopts = []


def compare_values(value_name, option_name):

    assert world.srvmsg
    get_option(world.srvmsg[0], option_name)
    if len(world.opts) == 0:
        subopt = world.subopts[0][1].payload
        to_cmp = getattr(subopt, value_name)
        assert world.savedvalue == to_cmp, \
            "Compared values %s and %s do not match" % (world.savedvalue, to_cmp)
        world.subopts = []
    else:
        to_cmp = getattr(world.opts[0], value_name)
        assert world.savedvalue == to_cmp, \
            "Compared values %s and %s do not match" % (world.savedvalue, to_cmp)
        world.opts = []
        world.subopts = []


def get_all_leases(decode_duid=True):

    assert world.srvmsg

    msg = get_last_response()
    if len(world.rlymsg) == 0:  # relay message is already cropped to exact layer
        msg = msg.getlayer(3)  # 0th is IPv6, 1st is UDP, 2nd is DHCP6, 3rd is the first option

    current_duid = ""
    all_addr = []
    while msg:
        if msg.optcode == 1:
            if decode_duid:
                txt_duid = extract_duid(msg.duid)
                current_duid = ":".join([txt_duid[i:i+2] for i in range(0, len(txt_duid), 2)])
            else:
                current_duid = msg.duid.copy()
        elif msg.optcode == 3:
            for ia_id in msg.ianaopts:
                if ia_id.optcode == 5:
                    all_addr.append({"duid": current_duid, "iaid": msg.iaid, "valid_lifetime": ia_id.validlft,
                                     "pref_lifetime": ia_id.preflft, "address": ia_id.addr, "prefix_len": 0})
        elif msg.optcode == 25:
            for ia_pd in msg.iapdopt:
                if ia_pd.optcode == 26:
                    all_addr.append({"duid": current_duid, "iaid": msg.iaid, "valid_lifetime": ia_pd.validlft,
                                     "pref_lifetime": ia_pd.preflft, "address": ia_pd.prefix, "prefix_len": ia_pd.plen})
        msg = msg.payload

    return all_addr


def response_get_content(*args):
    # only v4!
    pass


def tcp_messages_include(**kwargs):
    """
    Checks how many messages of each type are in received over tcp list
    :param kwargs: types of messages e.g. leasequery_reply=1, leasequery_data=199, leasequery_done=1
    """
    expected_msg_count = sum(list(kwargs.values()))
    assert expected_msg_count == len(world.tcpmsg),\
        f"Expected message count is {expected_msg_count} but number of received messages is {len(world.tcpmsg)}"
    received_msg_count = {}
    for msg in world.tcpmsg:
        m_type = get_msg_type(msg).lower().replace("-", "_")
        if m_type not in received_msg_count:
            received_msg_count.update({m_type: 1})
        else:
            received_msg_count[m_type] += 1

    assert kwargs == received_msg_count, f"Expected set of messages is {kwargs} but received was {received_msg_count}"


def tcp_get_message(**kwargs):
    """
    Find one message in the list of all received via TCP channel. Messages can be retrieved via its index in the list
    or using address/prefix to find one specific message e.g.
    * tcp_get_message(address=lease["address"])
    * tcp_get_message(prefix=lease["address"])
    * tcp_get_message(order=3)
    :param kwargs: define which type of search should be performed and with what value
    :return: DHCP6 message
    """
    # we can look for address or prefix, address in scapy is represented by addr and prefix is represented by prefix
    scapy_field = "addr"
    if "prefix" in kwargs:
        scapy_field = "prefix"

    if any(x in kwargs for x in ["address", "prefix"]):
        for msg in world.tcpmsg:
            if get_msg_type(msg) in ["LEASEQUERY-DONE", "UNKNOWN-TYPE"]:
                continue

            msg_opt = get_option(msg.copy(), 45)
            if hasattr(msg, "clientoptions"):
                msg_opt = msg_opt.clientoptions
            for x in msg_opt:
                while x:
                    # now we need address in addr or prefix in prefix:
                    if hasattr(x, scapy_field) and getattr(x, scapy_field) == kwargs["address" if "address" in kwargs else "prefix"]:
                        world.srvmsg = [msg.copy()]
                        return msg.copy()
                    x = x.payload

    elif "order" in kwargs:
        world.srvmsg = [world.tcpmsg[kwargs["order"]].copy()]
        return world.srvmsg[0]
    else:
        assert False, "You can choose particular message by its index or IP address that is suppose to have"
    assert False, f"Message with {scapy_field}={kwargs['address']} you are looking for couldn't be found."

# -------------------- PARSING RECEIVED MESSAGE BLOCK END -------------------- #


# ----------------------- TESTING IN LOOPS BLOCK START ----------------------- #


def loops_config_sld():
    world.loops["save_leases_details"] = True


def values_for_loops(value_name, file_flag, values):
    value_name = str(value_name)
    if value_name == "client-id":
        world.loops[value_name] = []
        for each in str(values).split(" "):
            world.cfg["values"]["DUID"] = each
            world.loops[value_name].append(convert_DUID())


def loops(message_type_1, message_type_2, repeat):
    import importlib
    testsetup = importlib.import_module("misc")
    repeat = int(repeat)
    testsetup.set_world()
    testsetup.test_procedure()

    if repeat < 1000:
        x_range = 10
    elif 1000 <= repeat < 10000:
        x_range = 250
    else:
        x_range = 1000

    world.loops["active"] = True

    if message_type_1 == "SOLICIT" and message_type_2 == "ADVERTISE":
        # short two message exchange without saving leases.
        for x in range(repeat):
            generate_new("client")
            client_does_include("Client", "client-id", None)
            client_does_include("Client", "IA-NA", None)
            client_send_msg(message_type_1, None, None)
            send_wait_for_message("MAY", True, message_type_2)

    elif message_type_1 == "SOLICIT" and message_type_2 == "REPLY":
        # first save server-id option
        client_does_include("Client", "client-id", None)
        client_does_include("Client", "IA-NA", None)
        client_send_msg(message_type_1, None, None)
        send_wait_for_message("MAY", True, "ADVERTISE")
        client_save_option("server-id")

        # long 4 message exchange with saving leases.
        for x in range(repeat):
            if x % x_range == 0:
                log.info("Message exchange no. %d", x)
            generate_new("client")
            client_does_include("Client", "client-id", None)
            client_does_include("Client", "IA-NA", None)
            client_send_msg(message_type_1, None, None)
            send_wait_for_message("MAY", True, "ADVERTISE")

            try:
                client_add_saved_option(False)
                client_copy_option("IA_NA")
            except AssertionError:
                pass
            client_does_include("Client", "client-id", None)
            client_send_msg("REQUEST", None, None)
            send_wait_for_message("MAY", True, message_type_2)

    elif message_type_1 == "REQUEST" and message_type_2 == "REPLY":
        # first save server-id option
        client_send_msg("SOLICIT", None, None)
        send_wait_for_message("MAY", True, "ADVERTISE")
        client_save_option("server-id")

        # long 4 message exchange with saving leases.
        for x in range(repeat):
            if x % x_range == 0:
                log.info("Message exchane no. %d", x)
            generate_new("client")
            client_add_saved_option(False)
            client_send_msg("REQUEST", None, None)
            send_wait_for_message("MAY", True, message_type_2)
            response_check_option_content(13, 3, "NOT", "statuscode", "2")

    elif message_type_1 == "RELEASE" and message_type_2 == "REPLY":
        # first save server-id option
        client_send_msg("SOLICIT", None, None)
        send_wait_for_message("MAY", True, "ADVERTISE")
        client_save_option("server-id")

        # long 4 message exchange with saving leases.
        for x in range(repeat):
            if x % x_range == 0:
                log.info("Message exchane no. %d", x)

            client_add_saved_option(False)
            client_send_msg("REQUEST", None, None)
            send_wait_for_message("MAY", True, message_type_2)

            client_add_saved_option(False)
            client_copy_option("IA_NA")
            client_send_msg("RELEASE", None, None)
            send_wait_for_message("MAY", True, message_type_2)
            # dhcpmsg.generate_new("client")

    elif message_type_1 == "RENEW" and message_type_2 == "REPLY":
        # first save server-id option
        client_send_msg("SOLICIT", None, None)
        send_wait_for_message("MAY", True, "ADVERTISE")
        client_save_option("server-id")

        # long 4 message exchange with saving leases.
        for x in range(repeat):
            if x % x_range == 0:
                log.info("Message exchane no. %d", x)

            client_add_saved_option(False)
            client_send_msg("REQUEST", None, None)
            send_wait_for_message("MAY", True, message_type_2)

            client_add_saved_option(False)
            client_copy_option("IA_NA")
            client_send_msg("RENEW", None, None)
            send_wait_for_message("MAY", True, message_type_2)

    else:
        pass
    for x in range(len(world.savedmsg)):
        world.savedmsg[x] = []


def save_info():
    pass


def check_IA_NA(address, status_code=DHCPv6_STATUS_CODES['Success'], expect=True):
    """
    Check that the latest received response has an IA_NA option containing
    an IA_Address suboption with the given address and containing the given
    status code.

    :param address: the expected address as value of the IA_Address suboption
    :param status_code: the expected status code (default: Success)
    :param expect: True if the address is expected to be found,
                   False if it is expected to be missing
    """

    response_check_include_option(True, 'IA_NA')
    # RFC 8415: If the Status Code option does not appear in a
    # message in which the option could appear, the status of the message
    # is assumed to be Success.
    if get_suboption('IA_NA', 'status-code'):
        response_check_suboption_content('status-code', 'IA_NA', expect, 'statuscode', status_code)
    else:
        assert status_code == DHCPv6_STATUS_CODES['Success'], \
            f'status code missing so it is Success by default, but expected {status_code}'

    if status_code == DHCPv6_STATUS_CODES['Success']:
        response_check_suboption_content('IA_address', 'IA_NA', expect, 'addr', address)


def check_IA_PD(prefix, prefix_length=None, status_code=DHCPv6_STATUS_CODES['Success'], expect=True):
    """
    Check that the latest received response has an IA_PD option containing
    an IA_Prefix suboption with the given address and containing the given
    status code.

    :param prefix: the expected prefix value inside the IA Prefix suboption
    :param prefix_length: the expected prefix length value inside the IA Prefix suboption.
                          If None, it is not checked.
    :param status_code: the expected status code (default: Success)
    :param expect: True if the prefix is expected to be found,
                   False if it is expected to be missing
    """

    response_check_include_option(True, 'IA_PD')
    # RFC 8415: If the Status Code option does not appear in a
    # message in which the option could appear, the status of the message
    # is assumed to be Success.
    if get_suboption('status-code', 'IA_PD'):
        response_check_suboption_content('status-code', 'IA_PD', 'statuscode', status_code)
    else:
        assert status_code == DHCPv6_STATUS_CODES['Success'], \
            f'status code missing so it is Success by default, but expected {status_code}'

    if status_code == DHCPv6_STATUS_CODES['Success']:
        response_check_suboption_content('IA-Prefix', 'IA_PD', expect, 'prefix', prefix)
        if prefix_length is not None:
            response_check_suboption_content('IA-Prefix', 'IA_PD', expect, 'plen', prefix_length)


def SARR(address=None, delegated_prefix=None, relay_information=False,
         status_code=DHCPv6_STATUS_CODES['Success'], exchange='full',
         duid='00:03:00:01:f6:f5:f4:f3:f2:01', iaid=None,
         linkaddr='2001:db8:1::1000', ifaceid='port1234'):
    """
    Sends and ensures receival of 6 packets part of a regular DHCPv6 exchange
    in the correct sequence: solicit, advertise, request, reply, renew, reply.
    Inserts options in the client packets based on given parameters and ensures
    that the right options are found in the server packets. A single option
    missing or having incorrect values renders the test failed.

    Args:
        address: the expected address as value of the IA_Address suboption.
            For multiple addresses, use additional check_IA_NA() calls.
        delegated_prefix: the expected prefix as value of the IA_Prefix suboption.
            For multiple prefixes, use additional check_IA_PD() calls.
        relay_information: whether client packets should be encapsulated in relay
            forward messages, and by extension whether server packets should be
            expected to be encapsulated in relay reply messages (default: False)
        status_code: the expected status code (default: Success)
        exchange: can have values "full" meaning SARR + renew-reply or
            "renew-reply". It is a string instead of a boolean for
            clearer recognition of test names because this value often comes from
            pytest parametrization. (default: "full")
        duid: the DUID to be used in client packets
            (default: '00:03:00:01:f6:f5:f4:f3:f2:01' - a value commonly used in tests)
        iaid: sets IAID for the client
        linkaddr: sets Link Address in Relayed message
        ifaceid: sets Interface ID in option 18 in Relayed message
    """

    if exchange == 'full':
        # Build and send Solicit and await Advertisement
        SA(address, delegated_prefix, relay_information, status_code, duid, iaid, linkaddr, ifaceid)

        if not relay_information:
            # Build and send a request.
            if address is not None:
                client_copy_option('IA_NA')
            if delegated_prefix is not None:
                client_copy_option('IA_PD')
            client_copy_option('server-id')
            client_sets_value('DUID', duid)
            client_does_include('Client', 'client-id')
            if status_code == DHCPv6_STATUS_CODES['NoAddrsAvail']:
                if address is not None:
                    client_sets_value('IA_Address', address)
                if delegated_prefix is not None:
                    client_sets_value('IA-Prefix', delegated_prefix)
            client_send_msg('REQUEST')

            # Expect a reply.
            misc.pass_criteria()
            send_wait_for_message('MUST', True, 'REPLY')
            if address is not None:
                check_IA_NA(address)
            if delegated_prefix is not None:
                check_IA_PD(delegated_prefix)

    # @todo: forge doesn't receive a reply on renews if the initial solicit was
    # encapsulated in a relay forward message. After an investigation is done,
    # if it is decided that it is normal behavior, you may remove this comment
    # block. If there was a bug in this function, then the following if
    # statement is a hack and should be removed and the code block within should
    # be bumped one scope level up at function level i.e. always executed.
    if not relay_information:
        misc.test_procedure()
        client_sets_value('DUID', duid)
        if iaid is not None:
            client_sets_value('ia_id', iaid)
            # Set the IAID for IAPDs as well.
            # It's handled under the different name 'ia_pd' in forge.
            client_sets_value('ia_pd', iaid)
        # Build and send a renew.
        if address is not None:
            client_copy_option('IA_NA')
        if delegated_prefix is not None:
            client_copy_option('IA_PD')
        client_copy_option('server-id')
        client_does_include('Client', 'client-id', None)
        client_add_saved_option(False)
        if status_code == DHCPv6_STATUS_CODES['NoAddrsAvail']:
            if address is not None:
                client_sets_value('IA_Address', address)
            if delegated_prefix is not None:
                client_sets_value('IA_Prefix', delegated_prefix)
        client_send_msg('RENEW')

        # Expect a reply.
        send_wait_for_message('MUST', True, 'REPLY')
        if address is not None:
            check_IA_NA(address)
        if delegated_prefix is not None:
            check_IA_PD(delegated_prefix)


def SA(address=None, delegated_prefix=None, relay_information=False,
       status_code=DHCPv6_STATUS_CODES['Success'], duid='00:03:00:01:f6:f5:f4:f3:f2:01', iaid=None,
       linkaddr='2001:db8:1::1000', ifaceid='port1234'):
    """
    Sends and ensures receival of 2 packets part of a regular DHCPv6 exchange
    in the correct sequence: solicit, advertise.
    Inserts options in the client packets based on given parameters and ensures
    that the right options are found in the server packets. A single option
    missing or having incorrect values renders the test failed.

    Args:
        address: the expected address as value of the IA_Address suboption.
            For multiple addresses, use additional check_IA_NA() calls.
        delegated_prefix: the expected prefix as value of the IA_Prefix suboption.
            For multiple prefixes, use additional check_IA_PD() calls.
        relay_information: whether client packets should be encapsulated in relay
            forward messages, and by extension whether server packets should be
            expected to be encapsulated in relay reply messages (default: False)
        status_code: the expected status code (default: Success)
        duid: the DUID to be used in client packets
            (default: '00:03:00:01:f6:f5:f4:f3:f2:01' - a value commonly used in tests)
        iaid: sets IAID for the client
        linkaddr: sets Link Address in Relayed message
        ifaceid: sets Interface ID in option 18 in Relayed message
        """

    misc.test_procedure()
    client_sets_value('DUID', duid)
    if iaid is not None:
        client_sets_value('ia_id', iaid)
        # Set the IAID for IAPDs as well.
        # It's handled under the different name 'ia_pd' in forge.
        client_sets_value('ia_pd', iaid)
    # Build and send a solicit.
    client_does_include('Client', 'client-id')
    if address is not None:
        client_does_include('Client', 'IA_Address')
        client_does_include('Client', 'IA-NA')
    if delegated_prefix is not None:
        client_does_include('Client', 'IA_Prefix')
        client_does_include('Client', 'IA-PD')
    client_send_msg('SOLICIT')

    if relay_information:
        # Encapsulate the solicit in a relay forward message.
        client_sets_value('linkaddr', linkaddr)
        client_sets_value('ifaceid', ifaceid)
        client_does_include('RelayAgent', 'interface-id')
        create_relay_forward()

        # Expect a relay reply.
        misc.pass_criteria()
        send_wait_for_message('MUST', True, 'RELAYREPLY')
        response_check_include_option(True, 'interface-id')
        response_check_include_option(True, 'relay-msg')
        response_check_option_content('relay-msg', True, 'Relayed', 'Message')
        response_check_include_option(True, 'client-id')
        response_check_include_option(True, 'server-id')
        if address is not None:
            check_IA_NA(address, status_code)
        if delegated_prefix is not None:
            check_IA_PD(delegated_prefix, status_code=status_code)
    else:
        # Expect an advertise.
        misc.pass_criteria()
        send_wait_for_message('MUST', True, 'ADVERTISE')
        response_check_include_option(True, 'client-id')
        response_check_include_option(True, 'server-id')
        if address is not None:
            check_IA_NA(address, status_code)
        if delegated_prefix is not None:
            check_IA_PD(delegated_prefix, status_code=status_code)
