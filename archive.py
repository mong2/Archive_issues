#!/usr/bin/env python
import sys
import os
import json
import codecs
import dateutil.parser
import multiprocessing
import time
import math
import cpapi
import cputils

start_time = time.time()
class CmdLine:
    def __init__(self):
        self.authFilename = "archive.auth"
        self.starting = None
        self.ending = None
        self.reportModule = None
        self.url_base = "https://api.cloudpassage.com"
        self.allowedReportTypes = ["sva", "csm", "fim", "sam"]
        # self.directory = os.chdir(os.path.dirname(os.getcwd()))


    def processArgs(self, argv):
        allOK = True
        self.progdir = os.path.dirname(sys.argv[0])
        for arg in argv[1:]:
            if (arg.startswith("--auth=")):
                self.authFilename = arg.split("=")[1]
            elif (arg.startswith("--starting")):
                self.starting = arg.split("=")[1]
                (ok, error) = cputils.verifyISO8601(self.starting)
                if not ok:
                    print >> sys.stderr, error
                    allOk = False
            elif (arg.startswith("--ending")):
                self.ending = arg.split("=")[1]
                (ok, error) = cputils.verifyISO8601(self.ending)
                if not ok:
                    print >> sys.stderr, error
                    allOk = False
            elif (arg.startswith("--base=")):
                self.base = arg.split("=")[1]
            elif (arg.startswith("--reportModule")):
                self.reportModule = arg.split("=")[1]
            elif (arg == "-h") or (arg == "-?"):
                allOK = False
            else:
                print >>sys.stderr, "Unknown argument: %s" % arg
                allOK = False
        return allOK

    def usage(self, progname):
        print >> sys.stderr, "Usage: %s [flag] [...]" % os.path.basename(progname)
        print >> sys.stderr, "Where flag is one or more of the following options:"
        print >> sys.stderr, "--auth=<filename>\tSpecify name of file containing API credentials"
        print >> sys.stderr, "--base=<url>\t\tSpecify the URL of the Halo REST API"
        print >> sys.stderr, "--starting=<datetime>\tSpecify a no-earlier-than date for issues (ISO8601)"
        print >> sys.stderr, "--ending=<datetime>\tSpecify a no-later-than date for issues (ISO8601)"
        print >> sys.stderr, "--reportType=<type>\tSpecify type of report, allowed = %s" % self.allowedReportTypes

class ArchiveData:
    def __init__(self):
        self.api = cpapi.CPAPI()
        self.directory = os.getcwd()

    def listScan(self, reportModule):
        print reportModule
        if (cmd.starting == None) and (cmd.ending == None):
            url = "%s:%d/v1/scans" % (self.api.base_url, self.api.port)
        elif (cmd.starting != None):
            url = "%s:%d/v1/scans?since=%s" % (self.api.base_url, self.api.port, cmd.starting)
            if (cmd.ending != None):
                url += "&until=%s" %(cmd.ending)
        if (reportModule != None):
            url += "&module=" + reportModule
        return url

    def scanDetail(self, queue, scan_id):
        count = 1
        url = "%s:%d/v1/scans/%s" %(self.api.base_url, self.api.port, scan_id)
        (data, authError) = self.api.doGetRequest(url,self.api.authToken)

        while (data == None) and (count < 4):
            print "update token"
            resp = self.api.authenticateClient()
            (data, authError) = self.api.doGetRequest(url,self.api.authToken)
            print "retrying scan: ", scan_id
            print "%d try" % count
            if (data != None):
                print "Succefully archive scan: %s after retrying" % scan_id
            count += 1

        if (data != None):
            if ('scan' in data):
                scan_data = json.loads(data)
                scan_time = dateutil.parser.parse(scan_data['scan']['created_at'])
                filename = (self.directory + "/output/" + str(scan_time.year) + "/" + str(scan_time.month) + "/" + str(scan_time.day) +
                            "/" + scan_data['scan']['server_hostname'] + "/" + scan_data['scan']['module'] + "--" + scan_data['scan']['id'] + ".json")
                if not os.path.exists(os.path.dirname(filename)):
                    os.makedirs(os.path.dirname(filename))
                with open(filename, "w") as f:
                    json.dump(scan_data, f)
        else:
            print "failed to archive scan (scan id: %s)" % scan_id

    def getScanData(self):
        print "here"
        count = 1
        url = self.listScan(cmd.reportModule)
        (data, authError) = self.api.doGetRequest(url, self.api.authToken)

        while (data == None) and (count < 4):
            print "getScanData:"
            print "updating token"
            resp = self.api.authenticateClient()
            (data, authError) = self.api.doGetRequest(url,self.api.authToken)
            print "retrying scan url: %s" % url
            print "%d try" % count
            if (data != None):
                print "Succefully connect to url: ", url
            count +=1

        if (data != None):
           if ('scans' in data):
                listScans = json.loads(data)
                count = listScans['count']
                pages = int(math.ceil(count/20.0))
                for num in range(pages):
                    countPagination = 1
                    scan_ids = []
                    urlPlus = url
                    print "Scanning page ", str((num + 1))
                    urlPlus += "&per_page=20&page=" + str((num + 1))
                    (data, authError) = self.api.doGetRequest(urlPlus, self.api.authToken)
                    while (data == None) and (countPagination < 4):
                        print "getScanData - Pagination:"
                        print "updating token"
                        resp = self.api.authenticateClient()
                        (data, authError) = self.api.doGetRequest(urlPlus,self.api.authToken)
                        print "retrying scan pagination url: ", urlPlus
                        print "%d try" % countPagination
                        if (data != None):
                            print "Succefully connect to pagination url: ", urlPlus
                        countPagination +=1
                    if (data != None):
                        if ('scans' in data):
                            data = json.loads(data)
                            listScans = data['scans']
                            for scan in listScans:
                                scan_ids.append(scan['id'])
                            queue = multiprocessing.Queue()
                            res = [multiprocessing.Process(target=self.scanDetail, args=(queue, i)) for i in scan_ids]
                            for p in res:
                                p.start()
                            for p in res:
                                p.join()
                            print "Finish writing page", str((num+1)) 
                    else:
                        print "Failed to connect to pagination url: ", urlPlus
        else: 
            print "Failed to connect to url: ", url


    def run (self, cmd):
        (credentialList, errMsg) = cputils.processAuthFile(cmd.authFilename, cmd.progdir)
        if (errMsg != None):
            print >> sys.stderr, errMsg
            return False
        if len(credentialList) < 1:
            return False
        # print credentials
        credentials = credentialList[0]
        self.api.base_url = cmd.url_base
        self.api.key_id = credentials['id']
        self.api.secret = credentials['secret']
        resp = self.api.authenticateClient()
        if (not resp):
            return False
        self.getScanData()



if __name__ == "__main__":
    cmd = CmdLine()
    if not cmd.processArgs(sys.argv):
        cmd.usage(sys.argv[0])
    else:
        rep = ArchiveData()
        rep.run(cmd)
    print ("--- %s seconds ---" % (time.time() - start_time))
