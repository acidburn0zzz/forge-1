# Copyright (C) 2013-2022 Internet Systems Consortium, Inc. ("ISC")
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# pylint: disable=invalid-name,line-too-long,,unused-import

# Author: Wlodzimierz Wencel

import codecs
import logging
import os
import struct

from random import randint

from scapy.all import get_if_raw_hwaddr, Ether, srp
from scapy.config import conf
from scapy.fields import Field
from scapy.layers.dhcp import BOOTP, DHCP, DHCPOptions
from scapy.packet import Raw
from scapy.layers.inet import IP, UDP

from src.forge_cfg import world
from src.protosupport.v6.srv_msg import apply_message_fields_changes, change_message_field, client_add_saved_option

from src import misc

log = logging.getLogger('forge')

# DHCPv4 option codes indexed by name
OPTIONS = {
    "subnet-mask": 1,
}


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


def client_requests_option(opt_type):
    if not hasattr(world, 'prl'):
        world.prl = ""  # don't request anything by default
    world.prl += chr(int(opt_type))  # put a single byte there


def build_raw(msg, append):
    if msg == "":
        world.climsg.append(build_msg(opts="") / Raw(load=append))
    else:
        client_send_msg(msg)
        world.climsg[0] = world.climsg[0] / Raw(load=append)


def client_send_msg(msgname, iface=None, addr=None):
    """Sends specified message with defined options.

    Parameters:
    msgname: name of the message
    iface: interface to send onto (default: None, meaning configured interface)
    addr: address to send to (default: None)
    """
    # set different ethernet interface than default one.
    if iface is not None:
        world.cfg["iface"] = iface
        world.cfg["srv4_addr"] = addr

    world.climsg = []
    options = world.cliopts

    if hasattr(world, 'prl') and len(world.prl) > 0:
        if conf.version == '2.2.0-dev':
            options += [("param_req_list", str(world.prl))]
        else:
            options += [("param_req_list", [ord(o) for o in world.prl])]
#     else:
#         assert False, "No PRL defined"

    # What about messages: "force_renew","lease_query",
    # "lease_unassigned","lease_unknown","lease_active",
    # messages from server: offer, ack, nak

    if msgname == "DISCOVER":
        # msg code: 1
        # world.cfg["values"]["broadcastBit"] = True
        msg = build_msg([("message-type", "discover")] + options)

    elif msgname == "REQUEST":
        # msg code: 3
        msg = build_msg([("message-type", "request")] + options)

    elif msgname == "DECLINE":
        # msg code: 4
        msg = build_msg([("message-type", "decline")] + options)

    elif msgname == "RELEASE":
        # msg code: 7
        msg = build_msg([("message-type", "release")] + options)

    elif msgname == "INFORM":
        # msg code: 8
        msg = build_msg([("message-type", "inform")] + options)

    elif msgname == "LEASEQUERY":
        # msg code: 10
        msg = build_msg([("message-type", "lease_query")] + options)

    elif msgname == "BOOTP_REQUEST":
        world.cfg["values"]["broadcastBit"] = True
        # Gitlab issue kea#2361
        # Kea expects a four-byte sequence at the beginning of the options section and claims it
        # should be the magic cookie, but the magic cookie is right before it, placed by scapy, and
        # that's where Kea correctly ends up reading it from. So let's put some four-byte padding.
        padding = ['\x00\x00\x00\x00']
        msg = build_msg(padding + options)

    else:
        assert False, "Invalid message type: %s" % msgname

    assert msg, "Failed to create " + msgname

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


def convert_flags_fqdn():
    flag_filed = 0
    if 'N' in world.cfg["values"]["FQDN_flags"]:
        flag_filed += 8
    if 'E' in world.cfg["values"]["FQDN_flags"]:
        flag_filed += 4
    if 'O' in world.cfg["values"]["FQDN_flags"]:
        flag_filed += 2
    if 'S' in world.cfg["values"]["FQDN_flags"]:
        flag_filed += 1
    return flag_filed


options_formatted_by_forge = [
    "vendor_specific",  # code 43
    "pxe_client_machine_identifier",  # code 97
]


def client_does_include(sender_type, opt_type, value):
    if opt_type == 'client_id':
        # code - 61
        world.cliopts += [(opt_type, convert_to_hex(value))]
#     elif opt_type =='vendor_class_id':
#         world.cliopts += [(opt_type, str(value), "my-other-class")]
    elif opt_type == 'fqdn':
        # code - 81
        flags = chr(int(convert_flags_fqdn()))
        # flags, RCODE1, RCODE2, domain name
        # RCODE1 and RCODE2 are deprecated but we need to add them.
        if 'E' not in world.cfg["values"]["FQDN_flags"]:
            fqdn = (flags + '\x00\x00' + world.cfg["values"]["FQDN_domain_name"])
        else:
            domain = "".join(map(lambda z: chr(len(z))+z, world.cfg["values"]["FQDN_domain_name"].split('.')))
            fqdn = (flags + '\x00\x00' + domain)
        world.cliopts += [('client_FQDN', fqdn)]
    elif opt_type == 'pxe_client_architecture':
        # code - 93
        world.cliopts += [(opt_type, '\00' + chr(int(value)))]
    elif opt_type == 'pxe_client_network_interface':
        # code - 94
        world.cliopts += [(opt_type, chr(int(value[0])) + chr(int(value[1])) + chr(int(value[2])))]
    elif opt_type in options_formatted_by_forge:
        world.cliopts += [(opt_type, "".join(map(lambda z: chr(int(z, 16)), list(value))))]
    elif opt_type in [
        'relay_agent_information',
        'vendor_class',
        'vendor_specific_information',
    ]:
        world.cliopts += [(opt_type, convert_to_hex(value))]
    else:
        try:
            world.cliopts += [(opt_type, str(value))]
        except UnicodeEncodeError:
            world.cliopts += [(opt_type, unicode(value))]


def response_check_content(expect, data_type, expected):

    if data_type == 'yiaddr':
        received = world.srvmsg[0].yiaddr
    elif data_type == 'ciaddr':
        received = world.srvmsg[0].ciaddr
    elif data_type == 'siaddr':
        received = world.srvmsg[0].siaddr
    elif data_type == 'giaddr':
        received = world.srvmsg[0].giaddr
    elif data_type == 'src_address':
        received = world.srvmsg[0].src
    elif data_type == 'chaddr':
        tmp = struct.unpack('16B', world.srvmsg[0].chaddr)
        received = ':'.join("%.2x" % x for x in tmp[:6])
    elif data_type == 'sname':
        received = world.srvmsg[0].sname.decode('utf-8').rstrip('\x00')
    elif data_type == 'file':
        received = world.srvmsg[0].file.decode('utf-8').rstrip('\x00')

    else:
        assert False, "Value %s is not supported" % data_type

    outcome, received = test_option(0, received, expected)

    if expect:
        assert outcome, "Invalid {data_type} received {received}" \
                        " but expected: {expected}".format(**locals())
    else:
        assert not outcome, "Invalid {data_type} received {received}" \
                            " that value has been excluded from correct values.".format(**locals())
    return received


def client_save_option(opt_name, count=0):
    opt_code = world.kea_options4.get(opt_name)

    assert opt_name in world.kea_options4, "Unsupported option name " + opt_name

    if count not in world.savedmsg:
        world.savedmsg[count] = [get_option(world.srvmsg[0], opt_code)]
    else:
        world.savedmsg[count].append(get_option(world.srvmsg[0], opt_code))


def client_copy_option(opt_name):
    opt_code = world.kea_options4.get(opt_name)

    assert opt_name in world.kea_options4, "Unsupported option name " + opt_name

    received = get_option(world.srvmsg[0], opt_code)
    world.cliopts.append(received)


def convert_to_hex(mac):
    return codecs.decode(mac.replace(":", ""), 'hex')


def build_msg(opts):
    conf.checkIPaddr = False
    fam, hw = get_if_raw_hwaddr(str(world.cfg["iface"]))

    # we need to choose if we want to use chaddr, or client id.
    # also we can include both: client_id and chaddr
    if world.cfg["values"]["chaddr"] is None or world.cfg["values"]["chaddr"] == "default":
        tmp_hw = hw
    elif world.cfg["values"]["chaddr"] == "empty":
        tmp_hw = convert_to_hex("00:00:00:00:00:00")
    else:
        tmp_hw = convert_to_hex(world.cfg["values"]["chaddr"])

    if world.cfg["values"]["broadcastBit"]:
        # value for setting 1000 0000 0000 0000 in bootp message in field 'flags' for broadcast msg.
        msg_flag = 32768
    else:
        msg_flag = 0

    msg = Ether(dst="ff:ff:ff:ff:ff:ff",
                src=hw)
    msg /= IP(src=world.cfg["source_IP"],
              dst=world.cfg["destination_IP"],)
    msg /= UDP(sport=world.cfg["source_port"], dport=world.cfg["destination_port"])
    if opts == "":
        return msg

    msg /= BOOTP(chaddr=tmp_hw,
                 giaddr=world.cfg["values"]["giaddr"],
                 flags=msg_flag,
                 secs=world.cfg["values"]["secs"],
                 hops=world.cfg["values"]["hops"])

    # BOOTP requests can be optionless
    if len(opts) > 0:
        opts += ["end"]  # end option
        msg /= DHCP(options=opts)

    #transaction id
    if world.cfg["values"]["tr_id"] is None:
        msg.xid = randint(0, 256*256*256)
    else:
        msg.xid = int(world.cfg["values"]["tr_id"])
    world.cfg["values"]["tr_id"] = msg.xid

    msg.siaddr = world.cfg["values"]["siaddr"]
    msg.ciaddr = world.cfg["values"]["ciaddr"]
    msg.yiaddr = world.cfg["values"]["yiaddr"]
    msg.htype = world.cfg["values"]["htype"]
    msg.hlen = world.cfg["values"]["hlen"]
    return msg


def get_msg_type(msg):

    msg_types = {1: "DISCOVER",
                 2: "OFFER",
                 3: "REQUEST",
                 4: "DECLINE",
                 5: "ACK",
                 6: "NAK",
                 7: "RELEASE",
                 8: "INFORM",
                 10: "LEASEQUERY",
                 11: "LEASEUNASSIGNED",
                 12: "LEASEUNKNOWN",
                 13: "LEASEACTIVE"
                 }
    # option 53 it's message type
    opt = get_option(msg, 53)

    # BOOTP_REPLYs have no message type
    if opt is None:
        return "BOOTP_REPLY"

    # opt[1] it's value of message-type option
    for msg_code in msg_types.keys():
        if opt[1] == msg_code:
            return msg_types[msg_code]

    return "UNKNOWN-TYPE"


def send_wait_for_message(msgtype, presence, exp_message):
    """
    Block until the given message is (not) received.
    """
    # We need to use srp() here (send and receive on layer 2)
    factor = 1
    pytest_current_test = os.environ.get('PYTEST_CURRENT_TEST')
    if 'HA' in pytest_current_test.split('/'):
        factor = max(factor, world.f_cfg.ha_packet_wait_interval_factor)
    if '_radius' in pytest_current_test.lower():
        factor = max(factor, world.f_cfg.radius_packet_wait_interval_factor)
    apply_message_fields_changes()
    ans, unans = srp(world.climsg,
                     iface=world.cfg["iface"],
                     timeout=factor * world.cfg['wait_interval'],
                     multi=True,
                     verbose=99)

    if world.f_cfg.show_packets_from in ['both', 'client']:
        world.climsg[0].show()
        print('\n')

    expected_type_found = False

    received_names = ""
    world.cliopts = []
    world.srvmsg = []
    for x in ans:
        a, b = x
        world.srvmsg.append(b)
        if world.f_cfg.show_packets_from in ['both', 'server']:
            b.show()
            print('\n')

        received_names = get_msg_type(b) + " " + received_names
        if get_msg_type(b) == exp_message:
            expected_type_found = True
        received_names = received_names.strip()

    log.debug("Received traffic (answered/unanswered): %d/%d packet(s)."
                              % (len(ans), len(unans)))
    if exp_message != "None":
        for x in unans:
            log.error(("Unanswered packet type = %s" % get_msg_type(x)))

        if presence:
            assert len(world.srvmsg) != 0, "No response received."
            assert expected_type_found, "Expected message " + exp_message + " not received (got " + received_names + ")"
        elif not presence:
            assert len(world.srvmsg) == 0, "Response received (got " + received_names + "), not expected"
        assert presence == bool(world.srvmsg), "No response received."
    else:
        assert len(world.srvmsg) == 0, "Response message " + received_names + "received but none message expected."
        # TODO: make assertion for receiving message that not suppose to come!

    return world.srvmsg


def get_option(msg, opt_code):
    '''
    Retrieve from scapy message {msg}, the DHCPv6 option having IANA code {opt_code}.
    :param msg: scapy message to retrieve the option from
    :param opt_code: option code or name
    :return: scapy message representing the option or None if the option doesn't exist
    '''

    # Ensure the option code is an integer.
    opt_code = get_option_code(opt_code)

    # Returns option of specified type
    # We need to iterate over all options and see
    # if there's one we're looking for
    world.opts = []
    opt_name = DHCPOptions[opt_code]
    # dhcpv4 implementation in Scapy is a mess. The options array contains mix of
    # strings, IPField, ByteEnumField and who knows what else. In each case the
    # values are accessed differently
    if isinstance(opt_name, Field):
        opt_name = opt_name.name

    x = msg.getlayer(4)  # 0th is Ethernet, 1 is IPv4, 2 is UDP, 3 is BOOTP, 4 is DHCP options
    # BOOTP messages may be optionless, so check first
    if x is not None:
        for opt in x.options:
            if opt[0] is opt_name:
                world.opts.append(opt)
                return opt
    return None


def byte_to_hex(byte_str):
    return ''.join(["%02X " % ord(x) for x in byte_str]).replace(" ", "")


def test_option(opt_code, received, expected):
    """
    Make some adjustments to {received} and check if it is equal to {expected}.
    :param opt_code: option code
    :param received: option value received on the wire
    :param expected: option value expected in the test
    :return: tuple(boolean on whether the values are equal, the adjusted {received})
    """

    if isinstance(received, str):
        if received == str(expected):
            return True, received
        else:
            return False, received

    tmp = ""
    decode_opts_byte_to_hex = [43, 125]
    if opt_code in decode_opts_byte_to_hex or expected[:4] == "HEX:":
        expected = expected[4:]
        # for this option we need a bit magic, and proper formatting at the end
        tmp = struct.unpack('%dB' % len(received[1]), received[1])
        received = (received[0], "".join("%.2x" % x for x in tmp).upper())

    for each in received:
        if str(each) == str(expected):
            return True, each
        elif isinstance(each, bytes):
            if str(each.decode("utf-8")) == str(expected):
                return True, each
    return False, tmp


def _get_opt_descr(opt_code):
    '''
    Get a textual description as provided by scapy, of option code or name {opt_code}.
    :param opt_code: the option code or name that is being described
    :return: the description
    '''

    # Ensure the option code is an integer.
    opt_code = get_option_code(opt_code)

    opt = DHCPOptions[opt_code]
    if isinstance(opt, str):
        opt_descr = "%s[%s]" % (opt, opt_code)
    else:
        opt_descr = "%s[%s]" % (opt.name, opt_code)
    return opt_descr


def response_check_include_option(expected, opt_code):
    assert len(world.srvmsg) != 0, "No response received."

    opt = get_option(world.srvmsg[0], opt_code)

    opt_descr = _get_opt_descr(opt_code)

    if expected:
        assert opt, "Expected option {opt_descr} not present in the message.".format(**locals())
    else:
        assert opt is None, "Expected option {opt_descr} present in the message. But not expected!".format(**locals())


def response_check_option_content(opt_code, expect, data_type, expected):
    # expect == None when we want that content and NOT when we dont want! that's messy correct that!
    assert len(world.srvmsg) != 0, "No response received."

    received = get_option(world.srvmsg[0], opt_code)

    # FQDN is being parsed different way because of scapy imperfections
    if opt_code == 81:
        tmp = received[0]
        if data_type == 'flags':
            received = (tmp, received[1][0])
        elif data_type == 'fqdn':
            received = (tmp, received[1][3:])
        else:
            assert False, "In option 81 you can look only for: 'fqdn' or 'flags'."
    elif opt_code == 61:
        expected = convert_to_hex(expected)
    elif isinstance(received[1], bytes):
        received = (received[0], received[1])

    outcome, received = test_option(opt_code, received, expected)

    opt_descr = _get_opt_descr(opt_code)

    if expect:
        assert outcome, "Invalid {opt_descr} option received: {received} but expected {expected}".format(**locals())
    else:
        assert not outcome, "Invalid {opt_descr} option received: {received}" \
                            " that value has been excluded from correct values".format(**locals())


def get_all_leases(decode_duid=True):
    assert world.srvmsg
    mac = ""
    tmp = struct.unpack('16B', world.srvmsg[0].chaddr)
    mac += ':'.join("%.2x" % x for x in tmp[:6])

    lease = {"hwaddr": mac, "address": world.srvmsg[0].yiaddr}
    try:
        lease.update({"client_id": get_option(world.srvmsg[0], 61)[1]}.hex())
    except:
        pass
    try:
        lease.update({"valid_lifetime": get_option(world.srvmsg[0], 51)[1]})
    except:
        pass

    return lease


def DO(address=None, options=None, chaddr='ff:01:02:03:ff:04'):
    """
    Sends a discover and expects an offer. Inserts options in the client
    packets based on given parameters and ensures that the right options are
    found in the server packets. A single option missing or having incorrect
    values renders the test failed.

    :param address: the expected address as value of the requested_addr option.
        If None, no DHCPOFFER is expected.
    :param options: any additional options to be inserted in the client packets in
        dictionary form with option names as keys and option values as values.
        (default: {})
    :param chaddr: the client hardware address to be used in client packets
        (default: 'ff:01:02:03:ff:04' - a value commonly used in tests)
    """
    # Send a discover.
    client_sets_value('chaddr', chaddr)
    if options:
        for k, v in options.items():
            client_does_include(None, k, v)
    client_send_msg('DISCOVER')

    # If the test requires an address, expect it in the offer, otherwise expect
    # no message back.
    if address is None:
        send_wait_for_message('MUST', False, None)
    else:
        send_wait_for_message('MUST', True, 'OFFER')
        response_check_content(True, 'yiaddr', address)
        client_sets_value('chaddr', chaddr)


def RA(address, options=None, response_type='ACK', chaddr='ff:01:02:03:ff:04',
       init_reboot=False, subnet_mask='255.255.255.0', fqdn=None):
    """
    Sends a request and expects an advertise. Inserts options in the client
    packets based on given parameters and ensures that the right options are
    found in the server packets. A single option missing or having incorrect
    values renders the test failed.

    :param address: the address used in the requested_addr option in the DHCP request.
        If None, the yiaddr in the last message, supposedly a DHCPOFFER, is expected.
    :param options: any additional options to be inserted in the client packets in
        dictionary form with option names as keys and option values as values.
        (default: {})
    :param response_type: the type of response to be expected in the server packet.
        Can have values 'ACK', 'NAK' or None. None means no response.
        (default: 'ACK')
    :param chaddr: the client hardware address to be used in client packets
        (default: 'ff:01:02:03:ff:04' - a value commonly used in tests)
    :param subnet_mask: the value for option 1 subnet mask expected in a DHCPACK
    """
    client_sets_value('chaddr', chaddr)
    # Copy server ID if the client is not simulating an INIT-REBOOT state and if
    # there was a server response in the past to copy it from.
    if not init_reboot and len(world.srvmsg) > 0:
        client_copy_option('server_id')
    if options is None or 'requested_addr' not in options:
        if address is None:
            # Only request an address if there was a server response in the past.
            if len(world.srvmsg) > 0:
                client_does_include(None, 'requested_addr', world.srvmsg[0].yiaddr)
        else:
            client_does_include(None, 'requested_addr', address)
    if options:
        for k, v in options.items():
            client_does_include(None, k, v)
    if fqdn is not None:
        client_sets_value('FQDN_domain_name', fqdn)
        client_sets_value('FQDN_flags', 'S')
        client_does_include(None, 'fqdn', 'fqdn')
    client_send_msg('REQUEST')

    if response_type is None:
        send_wait_for_message('MUST', False, None)
    elif response_type == 'ACK':
        send_wait_for_message('MUST', True, 'ACK')
        response_check_content(True, 'yiaddr', address)
        response_check_include_option(True, 'subnet-mask')
        response_check_option_content('subnet-mask', True, 'value', subnet_mask)
        # if fqdn is not None:
        #     response_check_include_option(True, 81)
        #     response_check_option_content(81, True, 'fqdn', fqdn)
    elif response_type == 'NAK':
        send_wait_for_message('MUST', True, 'NAK')


def DORA(address=None, options=None, exchange='full', response_type='ACK', chaddr='ff:01:02:03:ff:04',
         init_reboot=False, subnet_mask='255.255.255.0', fqdn=None):
    """
    Sends and ensures receival of 6 packets part of a regular DHCPv4 exchange
    in the correct sequence: discover, offer, request,
    acknowledgement/negative-acknowledgement plus an additional
    request-reply for the renew scenario.
    Inserts options in the client packets and ensures that the right options
    are found in the server packets. A single option missing or having incorrect
    values renders the test failed.

    :param address: the expected address in the yiaddr field and then used in the
        requested_addr option in the DHCP request. If None, no packet is expected.
    :param options: any additional options to be inserted in the client packets in
        dictionary form with option names as keys and option values as values.
        (default: {})
    :param exchange: can have values 'full' meaning DORA plus an additional
        request-reply for the renew scenario or "renew-only". It is a string
        instead of a boolean for clearer test names because this value often
        comes from pytest parametrization. (default: 'full')
    :param response_type: the type of response to be expected in the server packet.
        Can have values 'ACK' or 'NAK'. (default: 'ACK')
    :param chaddr: the client hardware address to be used in client packets
        (default: 'ff:01:02:03:ff:04' - a value commonly used in tests)
    :param subnet_mask: the value for option 1 subnet mask expected in a DHCPACK
    """
    misc.test_procedure()
    client_sets_value('chaddr', chaddr)
    if exchange == 'full':
        # Send a discover and expect an offer.
        DO(address, options, chaddr)

        # Send a request and expect an acknowledgement.
        RA(address, options, response_type, chaddr, init_reboot, subnet_mask, fqdn)

    # Send a request and expect an acknowledgement.
    # This is supposed to be the renew scenario after DORA.
    RA(address, options, response_type, chaddr, init_reboot, subnet_mask, fqdn)


def BOOTP_REQUEST_and_BOOTP_REPLY(address: str,
                                  chaddr: str = 'ff:01:02:03:ff:04',
                                  client_id: str = None):
    """
    Send a BOOTP request and expect a BOOTP reply.

    :param address: the address expected in the reply. If None, address is not checked.
    :param chaddr: the value of the chaddr field in the BOOTP request packet
    :param client_id: the value of option 61 client identifier in the BOOTP request packet
    """

    # Send request.
    misc.test_procedure()
    client_sets_value('chaddr', chaddr)
    if client_id is not None:
        client_does_include(None, 'client_id', client_id)
    client_send_msg('BOOTP_REQUEST')

    # Wait for reply.
    misc.pass_criteria()
    send_wait_for_message('MUST', True, 'BOOTP_REPLY')

    # Make sure that the Message Type option added while converting
    # BOOTP_REQUEST to REQUEST is not mirrored in the BOOTP_REPLY.
    response_check_include_option(False, 53)

    # Make sure that the lease is given to the client forever.
    response_check_include_option(False, 58)
    response_check_include_option(False, 59)

    # Check received address.
    if address is not None:
        response_check_content(True, 'yiaddr', address)
