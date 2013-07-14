# Copyright (C) 2013 Internet Systems Consortium.
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND INTERNET SYSTEMS CONSORTIUM
# DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL
# INTERNET SYSTEMS CONSORTIUM BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING
# FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
# NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION
# WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#
# author: Wlodzimierz Wencel

import datetime
import os
import sys

class TestHistory ():
    def __init__(self):
        self.date = self.present_time() 
        self.start_time = None
        self.stop_time = None
        self.time_elapsed = None
        self.passed = 0
        self.ran = 0
        self.failed = 0
        self.percent = 0.0
        self.tags = None
        self.path = None
        
        from features.init_all import SERVER_TYPE
        self.server_type = SERVER_TYPE
        
        #TODO: implement this
        self.bind10_version = "N/A"
        self.dibbler_version = "N/A"
        self.isc_dhcp_version = "N/A"
        #self.scenarios = {}

        self.check_file()

    def present_time(self):
        return datetime.datetime.now()

    def start(self):
        self.start_time = self.present_time() 

    def information(self, passed, ran, tags, path):
        self.stop_time = self.present_time()
        self.passed = passed
        self.ran = ran
        self.failed = ran - passed
        self.percent = (1.0 * passed/ran) * 100
        self.tags = tags
        self.path = path
        
    def check_file(self):
        if not os.path.exists('history.html'):
            new_file = open('history.html','w')
            new_file.close()
    
    def build_report(self):
        #it could be nice to add new line to first not to last line, but for now we keep it that way
        #also report should be extended, names of tests scenarios with results.
        report = open('history.html','a')
        self.time_elapsed = self.stop_time - self.start_time
        report.write('<table border = \'1\'><tr><td> DATE: </td><td>'+str(self.date.day)+'.'+str(self.date.month)+'.'+str(self.date.year)+'</td></tr><tr><td> SERVER TYPE: </td><td>'+self.server_type+'</td></tr><tr><td> TAGS: </td><td>'+str(self.tags)+' </td></tr><tr><td> PATH: </td><td>'+str(self.path)+' </td></tr><tr><td> PASSED: </td><td>'+str(self.passed)+' </td></tr><tr><td> FAILED: </td><td>'+str(self.failed)+' </td></tr><tr><td> %: </td><td>'+str(self.percent)+' </td></tr><tr><td> TIME ELAPSED: </td><td>'+str(self.time_elapsed)+' </td></tr></table><br/>\n')
        report.close()
        
class UserHelp ():
    def __init__(self):
        self.tags = ''
        self.all_tags = ''

    def check_tags(self, line):
        """
        Add only unique tags to list
        """
        tag_list = line.split('@')
        tag_list = [x.strip() for x in tag_list]
        for tag in tag_list:
            if tag is not None:
                if tag in self.tags or tag == 'v4' or tag == 'v6':
                    pass
                else:
                    self.tags += tag + ', '
        
    def test(self, ip_version, more):
        """
        Generate list of test sets, features, test names and all available tags
        """
        #make for each in number because it starts in two points: in run_test.py by using -l option, then it create list only for one IP version, 
        #and in help.py generating whole test list.
        print "Test tree schema:\nroot directory\n\ttest set (available by option -s in run_test.py)\n\t\ttest feature"
        if more: print "\t\t\ttest name (available by option -n in run_test.py)"
        for each_number in ip_version: 
            self.tags = ''
            sets_number = 0
            features_number = 0
            tests_number = 0
            print "\nIPv" + each_number + " Tests:"
            print "features/tests_v" + each_number + "/"
            for path, dirs, files in os.walk("features/tests_v" + each_number + "/"):
                if len(path[18:]) > 1: 
                    print "\t" + path[18:]
                    sets_number += 1 
                for each_file in files:
                    print "\t\t", each_file[:-8]
                    features_number += 1
                    names = open(path +'/'+ each_file, 'r')
                    for line in names:
                        line = line.strip()
                        if len(line) > 0:
                            if line[0] == '@':
                                self.check_tags(line)
                            elif "Scenario" in line and more:
                                print "\t\t\t" + line[10:]
                                tests_number += 1
                    names.close()
            print "Totally: \n\t",tests_number,"tests in",features_number,"features, grouped in ",sets_number,"sets.\n\nTest tags you can use: \n", self.tags[:-2], "\n"
            
    def steps(self):
        """
        Generate list of available steps in tests.
        """
        files = ['srv_control','msg'] #if you add file that help will be generated, add also description below.
        message = ['All steps available in preparing DHCP server configuration:', 'All steps available in building tests procedure:']
        
        for file_name, text in zip(files, message):
            steps = open ('features/'+file_name+'.py', 'r')
            print '\n',text,
            for line in steps:
                line = line.strip()
                if len(line) > 0:
                    if line[0] == '#' and line[1] == '#':
                        print '\n\t',line[2:]
                    elif line[0] == '@':
                        print "\t\t    ",line[7:-3]
            steps.close()
        print "\nFor definitions of (\d+) (\w+) (\S+) check Python regular expressions at http://docs.python.org/2/library/re.html"
    
if __name__ == '__main__':
    #orginal_stdout = sys.stdout
    help_file = file('UserHelp.txt', 'w')
    sys.stdout = help_file
    generate_help = UserHelp()
    print """
    This is User Help to Forge project. If you looking for installation guide, plz read documentation or visit Forge project web site.
    
    First part of help is guide how to use existing test and test steps.
    
    How to run specific tests:
        - all tests for IPv6
            run_test.py -6
        - all tests from specific set e.g. relay_agent (one test set is a whole directory e.g. test_v6/address_validation):
            run_test.py -6 -s relay_agent
        - all tests from specific set with specific tag:
            run_test.py -6 -s relay_agent -t basic
        - you can also use only tags:
            run_test.py -6 -t basic
        - or multiple tags (then you start tests with both of tags):
            run_test.py -6 -t basic, relay
        - you can start test with specific name:
            run_test.py -6 -n v6.basic.message.unicast.solicit (don't use it yet :D)
    
    Below there is automatically generated list of all tests. If you design new keeping the build procedure, 
    just start help.py again and you will see updated list (build procedure is described at the end of that document).
    
    AVAILABLE TESTS:  
    """
    generate_help.test(["4","6"], 1)
    help_file.flush()
    print "\tAVAILABLE STEPS:"
    generate_help.steps()
    help_file.flush()
    print """
    HOW TO DESIGN NEW SETPS?
    
    All the informations automatically generated and included in this file are result of parsing two files:
        msg.py 
        srv_control.py 
        in directory isc-forge/lettuce/features/
    As you can see there are test steps marked with '@step' and steps family marked with '##' (don't remove #, it's need to be double).
    When designing new step please put them in correct family. 
    
    Test example:
    
feature name >>                Feature: Standard DHCPv6 address validation
feature description >>         This feature is for checking respond on messages send on UNICAST address. Solicit, Confirm, Rebind, Info-Request should be discarded. Request should be answered with Reply message containing option StatusCode with code 5. 
        
tags >>                             @basic @v6 @unicast  
test name >>                        Scenario: v6.basic.message.unicast.solicit
    
configure server >>                 Test Setup:
                                    Server is configured with 3000::/64 subnet with 3000::1-3000::ff pool.
                                    Server is started.
    
Test steps >>                       Test Procedure:
           >>                       Client requests option 7.
           >>                       Client chooses UNICAST address.
           >>                       Client sends SOLICIT message.
                    
                                    Pass Criteria:
send/receive msg >>                 Server MUST NOT respond with ADVERTISE message.
                                
                                    Test Procedure:
                                    Client requests option 7.
                                    Client sends SOLICIT message.
                                
                                    Pass Criteria:
                                    Server MUST respond with ADVERTISE message.
    
Information about references >>     References: RFC3315 section 15

    Do NOT use 'Scenario' in tests in other places then test name, right below tags (e.g. @my_tag)
    For tags always use '@' before without white spaces:
        good tag: @basic 
        bad tag: @ basic
    
    You can use multiple parts like Test Procedure/ Pass Criteria but using Test Setup please be advised that remote server will be restarted,
    configuration removed, generated new configuration and start server with it.
    
    That's all what you should keep while designing new tests ;)
    
    If someone would redesign directory tree for test or files listed above, plz make sure that automatically generated help still working properly.
    """
    help_file.close()
    #sys.stdout = orginal_stdout